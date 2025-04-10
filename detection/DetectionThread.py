from PyQt5 import QtCore
import time
import queue
from detection.Inference import run_inference, calculate_foot_location
from detection.Tracker import DeepSortTracker
from region import RegionEditor
from detection.DetectedObject import DetectedObject
from utils.PathUpdater import task_queue

class DetectionThread(QtCore.QThread):
    # Now emits detections along with the capture time of the frame used for inference.
    detections_ready = QtCore.pyqtSignal(list, float)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, polygons_file, frame_queue, parent=None):
        super().__init__(parent)
        self.polygons_file = polygons_file
        self.frame_queue = frame_queue
        self._is_running = True
        self.tracker = DeepSortTracker(max_disappeared=40)
        if RegionEditor.region_polygons is None or RegionEditor.region_json_file != self.polygons_file:
            RegionEditor.region_json_file = self.polygons_file
            RegionEditor.load_polygons()

    def run(self):
        while self._is_running:
            try:
                frame_tuple = self.frame_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            frame, capture_time = frame_tuple

            try:
                detections = run_inference(frame)
                rects_for_tracker = detections
                objects_dict = self.tracker.update(rects_for_tracker)
                detected_objects_list = []

                for objectID, (centroid, bbox) in objects_dict.items():

                    if len(bbox) < 5:
                        continue
                    object_type = DetectedObject.CLASS_NAMES.get(bbox[4], "unknown")
                    foot = calculate_foot_location(bbox) if (object_type == "person" and bbox[4] == 0) else None
                    location = foot if foot is not None else centroid
                    region = RegionEditor.get_polygons_for_point((int(location[0]), int(location[1])),
                                                                 RegionEditor.region_polygons)
                    region = region[0] if region else "unknown"
                    detected_obj = DetectedObject(objectID, object_type, bbox[:4], centroid, foot, region)
                    detected_objects_list.append(detected_obj)

                # Emit detections along with the capture time of the frame used.
                self.detections_ready.emit(detected_objects_list, capture_time)

            except Exception as e:
                self.error_signal.emit(f"Error: {repr(e)}")

    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()
