import cv2
import numpy as np
from PyQt5 import QtCore
import time
import queue

from detection.Deepsort.DeepsortTracker import DeepSortTracker
from detection.Inference import run_inference, calculate_foot_location

from region import RegionEditor
from detection.DetectedObject import DetectedObject
from utils.ConfigManager import ConfigManager


class DetectionThread(QtCore.QThread):

    detections_ready = QtCore.pyqtSignal(list, float)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, polygons_file, frame_queue, parent=None):
        super().__init__(parent)
        self.polygons_file = polygons_file
        self.frame_queue = frame_queue
        self._is_running = True

        config_manager = ConfigManager()
        deepsort_config = config_manager.get_deepsort_config()

        max_disappeared = deepsort_config.get("max_disappeared", 40)
        max_distance = deepsort_config.get("max_distance", 100)
        device = deepsort_config.get("device", "cuda")
        appearance_weight = deepsort_config.get("appearance_weight", 0.5)
        motion_weight = deepsort_config.get("motion_weight", 0.5)

        self.tracker = DeepSortTracker(
            max_disappeared=max_disappeared,
            max_distance=max_distance,
            device=device,
            appearance_weight=appearance_weight,
            motion_weight=motion_weight
        )

        if RegionEditor.region_polygons is None or RegionEditor.region_json_file != self.polygons_file:
            RegionEditor.region_json_file = self.polygons_file
            RegionEditor.load_polygons()

    def apply_detection_blackout(self, frame):
        """
        Returns a copy of the frame where all regions defined with type
        'detection_blackout' in RegionEditor.region_polygons are filled with 0s.
        """
        # Copy the original frame.
        masked_frame = frame.copy()

        # Ensure that polygons are loaded.
        if RegionEditor.region_polygons is None:
            return masked_frame

        # Iterate over each polygon.
        for poly in RegionEditor.region_polygons:
            if poly.get("type") == "detection_blackout":
                pts = np.array(poly["points"], dtype=np.int32)
                # Fill the polygon with black (all 0's).
                cv2.fillPoly(masked_frame, [pts], (0, 0, 0))
        return masked_frame

    def run(self):
        while self._is_running:
            try:
                frame_tuple = self.frame_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            frame, capture_time = frame_tuple

            # Apply blackout masking based on polygon data.
            masked_frame = self.apply_detection_blackout(frame)

            try:
                # Run YOLO detection on the masked frame.
                detections = run_inference(masked_frame)
                rects_for_tracker = detections
                objects_dict = self.tracker.update(rects_for_tracker, frame=masked_frame)
                detected_objects_list = []

                for objectID, (centroid, bbox) in objects_dict.items():
                    if len(bbox) < 5:
                        continue

                    object_type = DetectedObject.CLASS_NAMES.get(bbox[4], "unknown")
                    foot = calculate_foot_location(bbox) if (object_type == "person" and bbox[4] == 0) else None
                    location = foot if foot is not None else centroid
                    region = RegionEditor.get_polygons_for_point(
                        (int(location[0]), int(location[1])), RegionEditor.region_polygons)
                    region = region[0] if region else "unknown"
                    detected_obj = DetectedObject(objectID, object_type, bbox[:4], centroid, foot, region)
                    detected_objects_list.append(detected_obj)

                self.detections_ready.emit(detected_objects_list, capture_time)

            except Exception as e:
                self.error_signal.emit(f"Error: {repr(e)}")

    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()
