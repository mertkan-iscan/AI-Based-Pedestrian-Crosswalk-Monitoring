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
        homography_matrix=None,
        delay: float = 1.0,
        parent=None,
    ):
        super().__init__(parent)
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

    def run(self):
        while self._run:
            try:
                frame, capture_time, display_time = self.queue.get(timeout=0.05)
                orig_capture = capture_time
            except queue.Empty:
                continue

            # queue wait
            t_dequeue = time.time()
            signals.queue_wait_logged.emit(t_dequeue - orig_capture)

            # mask blackout
            masked = self._mask_blackout(frame)

            # inference timing
            t_inf_start = time.time()
            detections = run_inference(masked)
            t_inf_end = time.time()
            inference_time = t_inf_end - t_inf_start
            signals.detection_logged.emit(inference_time)


            # post-processing (tracking + object list)
            t_post_start = time.time()

            # compute desired emit timestamp (video timestamp + delay)
            emit_time = display_time + self.delay

            tracks_map = self.tracker.update(
                detections,
                frame=masked,
                timestamp=emit_time,
            )

            detected_objects = []
            for tid, (centroid, bbox) in tracks_map.items():
                x1, y1, x2, y2, cls_idx = bbox[:5]
                obj_type = DetectedObject.CLASS_NAMES.get(cls_idx, "unknown")

                obj = DetectedObject(tid, obj_type, (x1, y1, x2, y2), centroid)

                # attach the two distances from the matching Track
                for t in self.tracker.tracks:
                    if t.track_id == tid:
                        obj.motion_distance = getattr(t, 'motion_distance', None)
                        obj.appearance_distance = getattr(t, 'appearance_distance', None)
                        break

                detected_objects.append(obj)

            t_post_end = time.time()
            signals.postproc_logged.emit(t_post_end - t_post_start)



            # schedule emission (non-blocking)
            schedule_delay = emit_time - time.time()
            signals.scheduling_logged.emit(schedule_delay)

            timer = threading.Timer(
                schedule_delay,
                lambda objs=detected_objects, cap=orig_capture: self._emit_detections(objs, cap)
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
