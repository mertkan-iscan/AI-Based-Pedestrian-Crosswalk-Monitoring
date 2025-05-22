import queue
import time
import threading
import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from crosswalk_inspector.objects.DetectedObject import DetectedObject
from detection.Inference import run_inference
from detection.Deepsort.DeepsortTracker import DeepSortTracker
from utils.RegionManager import RegionManager
from crosswalk_inspector.GlobalState import GlobalState
from utils.ConfigManager import ConfigManager
from utils.benchmark.MetricSignals import signals

class DetectionThread(QThread):
    detections_ready = pyqtSignal(list, float)
    error_signal     = pyqtSignal(str)

    def __init__(
        self,
        polygons_file: str,
        detection_queue: queue.Queue,
        state: GlobalState,
        homography_matrix=None,
        delay: float = 1.0,
        parent=None,
    ):
        super().__init__(parent)
        self.queue           = detection_queue
        self.delay           = float(delay)
        self._run            = True
        self.state           = state

        cfg = ConfigManager().get_deepsort_config()
        self.tracker = DeepSortTracker(
            max_disappeared   = cfg.get("max_disappeared"),
            max_distance      = cfg.get("max_distance"),
            device            = cfg.get("device"),
            appearance_weight = cfg.get("appearance_weight"),
            motion_weight     = cfg.get("motion_weight"),
            homography_matrix = homography_matrix,
        )

        self.editor = RegionManager(polygons_file)
        self.editor.load_polygons()

    def _mask_blackout(self, frame):
        masked = frame.copy()
        for poly in self.editor.region_polygons:
            if poly.get("type") == "detection_blackout":
                pts = np.array(poly["points"], dtype=np.int32)
                cv2.fillPoly(masked, [pts], (0, 0, 0))
        return masked

    def _in_blackout(self, bbox):
        x1, y1, x2, y2 = bbox[:4]
        corners = [(x1, y1), (x1, y2), (x2, y1), (x2, y2)]
        for poly in self.editor.other_regions.get("detection_blackout", []):
            pts = np.array(poly["points"], dtype=np.int32)
            for corner in corners:
                if cv2.pointPolygonTest(pts, corner, False) >= 0:
                    return True
        return False

    def run(self):
        while self._run:
            try:
                frame, capture_time, display_time = self.queue.get(timeout=0.05)
                orig_capture = capture_time
            except queue.Empty:
                continue

            signals.queue_wait_logged.emit(time.time() - orig_capture)
            masked = self._mask_blackout(frame)

            t_inf_start = time.time()
            detections = run_inference(masked)
            signals.detection_logged.emit(time.time() - t_inf_start)

            tracks_map = self.tracker.update(
                detections,
                frame=masked,
                timestamp=display_time,
            )

            # remove deepsort tracks immediately if they intersect blackout
            for tid, (_, bbox) in tracks_map.items():
                if self._in_blackout(bbox):
                    self.tracker.tracks = [
                        t for t in self.tracker.tracks
                        if t.track_id != tid
                    ]

            detected_objects = []
            for tid, (surface_point, bbox) in tracks_map.items():
                x1, y1, x2, y2, cls_idx, conf = bbox[:6]
                obj = DetectedObject(
                    tid,
                    DetectedObject.CLASS_NAMES.get(cls_idx, "unknown"),
                    (int(x1), int(y1), int(x2), int(y2)),
                    surface_point,
                    surface_point
                )
                obj.confidence = float(conf)
                for t in self.tracker.tracks:
                    if t.track_id == tid:
                        obj.motion_distance     = getattr(t, "motion_distance", None)
                        obj.appearance_distance = getattr(t, "appearance_distance", None)
                        break
                detected_objects.append(obj)

            emit_time     = display_time + self.delay
            delay_seconds = max(0, emit_time - time.time())

            timer = threading.Timer(
                delay_seconds,
                lambda objs=detected_objects[:], cap=orig_capture:
                    self._emit_detections(objs, cap)
            )
            timer.daemon = True
            timer.start()

    def _emit_detections(self, detected_objects, capture_time):
        ids_to_remove   = []
        objects_to_emit = []

        for obj in detected_objects:
            if self._in_blackout(obj.bbox):
                ids_to_remove.append(obj.id)
            else:
                objects_to_emit.append(obj)

        if ids_to_remove:
            print(f"Detected objects intersect blackout: {ids_to_remove}")
            self.state.remove(ids_to_remove)

        if objects_to_emit:
            self.state.update(objects_to_emit, time.time())
            self.detections_ready.emit(objects_to_emit, capture_time)

    def stop(self):
        self._run = False
        self.quit()
        self.wait()
