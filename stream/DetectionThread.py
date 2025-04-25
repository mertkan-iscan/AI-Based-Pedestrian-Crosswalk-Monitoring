# stream/DetectionThread.py

import cv2
import numpy as np
from PyQt5 import QtCore
import queue

from detection.Deepsort.DeepsortTracker import DeepSortTracker
from detection.Inference import run_inference, calculate_foot_location
from region.RegionEditor import RegionEditor
from detection.DetectedObject import DetectedObject
from utils.ConfigManager import ConfigManager
from detection.GlobalState import GlobalState


class DetectionThread(QtCore.QThread):
    detections_ready = QtCore.pyqtSignal(list, float)
    error_signal     = QtCore.pyqtSignal(str)

    def __init__(self, polygons_file, frame_queue, homography_matrix=None, parent=None):
        super().__init__(parent)
        self.frame_queue   = frame_queue
        self._is_running   = True

        cfg = ConfigManager().get_deepsort_config()
        self.tracker = DeepSortTracker(
            max_disappeared   = cfg.get("max_disappeared"),
            max_distance      = cfg.get("max_distance"),
            device            = cfg.get("device"),
            appearance_weight = cfg.get("appearance_weight"),
            motion_weight     = cfg.get("motion_weight"),
            homography_matrix = homography_matrix
        )

        self.editor = RegionEditor(polygons_file)
        self.editor.load_polygons()

    def apply_detection_blackout(self, frame):
        masked = frame.copy()
        for poly in self.editor.region_polygons:
            if poly.get("type") == "detection_blackout":
                pts = np.array(poly["points"], dtype=np.int32)
                cv2.fillPoly(masked, [pts], (0, 0, 0))
        return masked

    def run(self):
        while self._is_running:
            try:
                frame, capture_time = self.frame_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            masked = self.apply_detection_blackout(frame)

            try:
                detections = run_inference(masked)
                objects_dict = self.tracker.update(detections, frame=masked)
                detected_objects = []

                for objectID, (centroid, bbox) in objects_dict.items():
                    if len(bbox) < 5:
                        continue

                    obj_type = DetectedObject.CLASS_NAMES.get(bbox[4], "unknown")
                    foot = (
                        calculate_foot_location(bbox)
                        if obj_type == "person" and bbox[4] == 0
                        else None
                    )
                    location = foot if foot is not None else centroid

                    regions = self.editor.get_polygons_for_point(
                        (int(location[0]), int(location[1]))
                    )
                    region = regions[0] if regions else "unknown"

                    detected_objects.append(
                        DetectedObject(objectID, obj_type, bbox[:4], centroid, foot, region)
                    )

                # update global state (with aging)
                GlobalState.instance().update(detected_objects, capture_time)
                # emit for GUI or other listeners
                self.detections_ready.emit(detected_objects, capture_time)

            except Exception as e:
                self.error_signal.emit(f"Error: {repr(e)}")

    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()
