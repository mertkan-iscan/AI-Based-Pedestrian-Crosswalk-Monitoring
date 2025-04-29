# stream/DetectionThread.py
import queue
import time
import cv2
import numpy as np
from PyQt5 import QtCore

from detection.DetectedObject import DetectedObject
from stream.FrameProducerThread import wait_until
from detection.Inference import run_inference, calculate_foot_location
from detection.Deepsort.DeepsortTracker import DeepSortTracker
from region.RegionEditor import RegionEditor
from detection.GlobalState import GlobalState
from utils.ConfigManager import ConfigManager
from utils.benchmark.MetricSignals import signals


class DetectionThread(QtCore.QThread):
    detections_ready = QtCore.pyqtSignal(list, float)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(
        self,
        polygons_file: str,
        detection_queue: "queue.Queue",
        homography_matrix=None,
        delay: float = 1.0,
        parent=None,
    ):
        super().__init__(parent)
        self.queue   = detection_queue
        self.delay   = float(delay)
        self._run    = True

        cfg = ConfigManager().get_deepsort_config()
        self.tracker = DeepSortTracker(
            max_disappeared   = cfg.get("max_disappeared"),
            max_distance      = cfg.get("max_distance"),
            device            = cfg.get("device"),
            appearance_weight = cfg.get("appearance_weight"),
            motion_weight     = cfg.get("motion_weight"),
            homography_matrix = homography_matrix,
        )

        self.editor = RegionEditor(polygons_file)
        self.editor.load_polygons()

    # ------------------------------------------------------------------ #
    def _mask_blackout(self, frame):
        masked = frame.copy()
        for poly in self.editor.region_polygons:
            if poly.get("type") == "detection_blackout":
                pts = np.array(poly["points"], dtype=np.int32)
                cv2.fillPoly(masked, [pts], (0, 0, 0))
        return masked

    # ------------------------------------------------------------------ #
    def run(self):
        while self._run:
            try:
                frame, capture_time, display_time = self.queue.get(timeout=0.05)
            except queue.Empty:
                continue

            masked = self._mask_blackout(frame)

            t0 = time.time()
            detections = run_inference(masked)
            signals.detection_logged.emit(time.time() - t0)

            tracks = self.tracker.update(detections, frame=masked)

            detected_objects = []
            for tid, (centroid, bbox) in tracks.items():
                if len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    cls_idx = -1
                else:
                    x1, y1, x2, y2, cls_idx = bbox[:5]

                obj_type = DetectedObject.CLASS_NAMES.get(cls_idx, "unknown")

                foot = (
                    calculate_foot_location((x1, y1, x2, y2))
                    if obj_type == "person"
                    else None
                )
                loc = foot if foot is not None else centroid
                regions = self.editor.get_polygons_for_point((int(loc[0]), int(loc[1])))
                region  = regions[0] if regions else "unknown"

                detected_objects.append(
                    DetectedObject(
                        tid,
                        obj_type,
                        (x1, y1, x2, y2),
                        centroid,
                        foot,
                        region,
                    )
                )

            target = display_time + self.delay
            if time.time() > target:       # stale – drop detections
                continue

            wait_until(target)

            GlobalState.instance().update(detected_objects, capture_time)
            self.detections_ready.emit(detected_objects, capture_time)

    def stop(self):
        self._run = False
        self.quit()
        self.wait()
