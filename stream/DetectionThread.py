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
    error_signal = pyqtSignal(str)

    def __init__(
        self,
        polygons_file: str,
        detection_queue: "queue.Queue",
        state: GlobalState,
        homography_matrix,
        detection_fps,
        delay,
        parent=None,
    ):
        super().__init__(parent)
        self.detection_fps = detection_fps
        self.queue = detection_queue
        self.delay = float(delay)
        self._run = True

        self.state = state

        cfg = ConfigManager().get_deepsort_config()
        self.tracker = DeepSortTracker(
            max_disappeared   = cfg.get("max_disappeared"),
            max_distance      = cfg.get("max_distance"),
            device            = cfg.get("device"),
            appearance_weight = cfg.get("appearance_weight"),
            motion_weight     = cfg.get("motion_weight"),
            homography_matrix = homography_matrix
        )

        self.editor = RegionManager(polygons_file)
        self.editor.load_polygons()

        self.H_inv = None
        if homography_matrix is not None:
            try:
                self.H_inv = np.linalg.inv(np.asarray(homography_matrix, dtype=np.float32))
            except np.linalg.LinAlgError:
                self.H_inv = None

    def _mask_blackout(self, frame):
        masked = frame.copy()
        for poly in self.editor.other_regions.get("detection_blackout", []):
            pts = np.array(poly["points"], dtype=np.int32)
            cv2.fillPoly(masked, [pts], (0, 0, 0))
        return masked

    def _bev_to_cam(self, pt):
        if self.H_inv is None:
            return pt
        vec = np.array([[pt[0], pt[1], 1]], dtype=np.float32).T
        res = self.H_inv @ vec
        res /= res[2, 0]
        return float(res[0, 0]), float(res[1, 0])

    def run(self):
        while self._run:
            try:
                frame, capture_time, display_time = self.queue.get(timeout=0.05)
            except queue.Empty:
                continue

            t_dequeue = time.time()

            signals.queue_wait_logged.emit(t_dequeue - capture_time)
            masked = self._mask_blackout(frame)

            t_inf_start = time.time()

            detections = run_inference(masked)

            t_inf_end = time.time()

            signals.detection_logged.emit(t_inf_end - t_inf_start)

            t_post_start = time.time()

            tracks_map = self.tracker.update(
                detections,
                frame=masked,
                timestamp=display_time,
                detection_fps=self.detection_fps
            )

            detected_objects = []
            for tid, (surface_point, bbox) in tracks_map.items():
                x1, y1, x2, y2, cls_idx, conf = bbox[:6]
                obj_type = DetectedObject.CLASS_NAMES.get(cls_idx, "unknown")

                obj = DetectedObject(
                    tid,
                    obj_type,
                    (int(x1), int(y1), int(x2), int(y2)),
                    surface_point,
                    surface_point
                )

                obj.confidence = float(conf)

                for t in self.tracker.tracks:
                    if t.track_id == tid:
                        obj.motion_distance = getattr(t, 'motion_distance', None)
                        obj.appearance_distance = getattr(t, 'appearance_distance', None)
                        break

                detected_objects.append(obj)

            signals.postproc_logged.emit(time.time() - t_post_start)

            emit_time = display_time + self.delay

            schedule_delay = emit_time - time.time()

            signals.scheduling_logged.emit(schedule_delay)

            timer = threading.Timer(
                schedule_delay,
                lambda objs=detected_objects, cap=capture_time: self._emit_detections(objs, cap)
            )

            timer.daemon = True
            timer.start()

    def _emit_detections(self, detected_objects, capture_time):
        self.state.update(detected_objects, time.time())
        self.detections_ready.emit(detected_objects, capture_time)

    def stop(self):
        self._run = False
        self.quit()
        self.wait()
