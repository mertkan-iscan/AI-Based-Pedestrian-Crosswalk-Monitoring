import os
import av
import streamlink
import cv2
import time
from contextlib import contextmanager

from PyQt5 import QtCore

from utils.ConfigManager import ConfigManager
from region import RegionEditor
from detection.DetectedObject import DetectedObject
from detection.Inference import run_inference
from detection.Tracker import DeepSortTracker
from detection.Inference import calculate_foot_location
from utils.PathUpdater import task_queue
from stream.VideoFrameReader import VideoFrameReader

# Load configuration
config_manager = ConfigManager()
infer_cfg = config_manager.get_inference_config()


class StreamContainer:

    @staticmethod
    def get_container(url):
        streams = streamlink.streams(url)
        if "best" not in streams:
            raise Exception("No suitable stream found.")
        stream_obj = streams["best"]
        raw_stream = stream_obj.open()

        class StreamWrapper:
            def read(self, size=-1):
                return raw_stream.read(size)

            def readable(self):
                return True

        wrapped = StreamWrapper()
        container = av.open(wrapped)
        return container

    @staticmethod
    @contextmanager
    def get_container_context(url):
        container = StreamContainer.get_container(url)
        try:
            yield container
        finally:
            container.close()


class FrameExtractor:

    @staticmethod
    def frame_generator(container):
        for frame in container.decode(video=0):
            yield frame.to_ndarray(format='bgr24')

    @staticmethod
    def get_single_frame(stream_url):
        try:
            with StreamContainer.get_container_context(stream_url) as container:
                for frame in container.decode(video=0):
                    return frame.to_ndarray(format='bgr24')
        except Exception as e:
            print("Error capturing frame:", e)
        return None

    @staticmethod
    def get_single_frame_file(video_file_path):
        cap = cv2.VideoCapture(video_file_path)
        if not cap.isOpened():
            print(f"Error: Could not open video file: {video_file_path}")
            return None

        ret, frame = cap.read()
        cap.release()

        if not ret:
            print(f"Error: Could not read a frame from: {video_file_path}")
            return None

        return frame


class VideoStreamProcessor:

    def __init__(self, source_url, polygons_file):
        self.source_url = source_url
        self.polygons_file = polygons_file
        self.skip_frames = infer_cfg.get("skip_frames", 0)
        self.max_latency = infer_cfg.get("max_latency", 0.5)
        self.max_frame_gap = infer_cfg.get("max_frame_gap", 5.0)
        self.persistent_objects = {}
        self.tracker = DeepSortTracker(max_disappeared=40)
        self.frame_count = 0
        self.prev_detections = []

        # Cache region polygons if not already loaded or if file changed.
        if RegionEditor.region_polygons is None or RegionEditor.region_json_file != polygons_file:
            RegionEditor.region_json_file = polygons_file
            RegionEditor.load_polygons()

    @staticmethod
    def compute_frame_timing(frame_pts, base_pts, video_stream, start_time):
        relative_pts = frame_pts - base_pts if frame_pts is not None else 0
        frame_time = float(relative_pts * video_stream.time_base)
        current_time = time.time() - start_time
        delay = frame_time - current_time
        return frame_time, current_time, delay

    @staticmethod
    def check_stream_health(last_frame_time, max_frame_gap):
        current_time = time.time()
        gap = current_time - last_frame_time
        if gap > max_frame_gap:
            print(f"WARNING: No frames received for {gap:.1f}s (exceeds {max_frame_gap}s). Slow or stalled stream?")
        return gap

    @staticmethod
    def draw_latency_info(img, delay):
        latency_text = f"Latency: {abs(delay):.2f} sec"
        cv2.putText(img, latency_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
        return img

    @staticmethod
    def get_region_info(coord):
        loc = (int(coord[0]), int(coord[1]))
        regions = RegionEditor.get_polygons_for_point(loc, RegionEditor.region_polygons)
        return regions[0] if regions else "unknown"

    def process_inference_for_frame(self, img, processing_allowed):
        # Increase the frame counter.
        self.frame_count += 1
        # Use previous detections if frame skipping is enabled.
        if self.skip_frames and self.frame_count % self.skip_frames != 0:
            detections = self.prev_detections
        else:
            if processing_allowed:
                detections = run_inference(img)
                self.prev_detections = detections.copy()
            else:
                detections = self.prev_detections
        return detections

    def update_tracker_objects(self, detections):
        rects_for_tracker = detections
        objects = self.tracker.update(rects_for_tracker)
        detected_objects_list = []

        for objectID, (centroid, bbox) in objects.items():
            if len(bbox) < 5:
                continue

            object_type = DetectedObject.CLASS_NAMES.get(bbox[4], "unknown")
            foot = calculate_foot_location(bbox) if (object_type == "person" and bbox[4] == 0) else None
            location = foot if foot is not None else centroid
            region = VideoStreamProcessor.get_region_info(location)

            if objectID in self.persistent_objects:
                detected_obj = self.persistent_objects[objectID]
                detected_obj.update_centroid(centroid)
                detected_obj.update_bbox(bbox[:4])  # Keep bbox updated.
                if foot is not None:
                    task_queue.put(('update', objectID, foot))
                    detected_obj.update_foot(foot)
                detected_obj.region = region
            else:
                detected_obj = DetectedObject(objectID, object_type, bbox[:4], centroid, foot, region)
                self.persistent_objects[objectID] = detected_obj
                if foot is not None:
                    task_queue.put(('update', objectID, foot))

            detected_objects_list.append(detected_obj)
        return detected_objects_list

    def stream_generator(self):

        if os.path.isfile(self.source_url):
            # File-based stream branch.
            reader = VideoFrameReader(self.source_url)
            loop = QtCore.QEventLoop()
            frames = []

            def handle_frame(frame, target_time):
                processing_allowed = True
                start_inference = time.perf_counter()
                detections = self.process_inference_for_frame(frame, processing_allowed)
                inference_latency = time.perf_counter() - start_inference
                objects = self.update_tracker_objects(detections)
                frame_latency = abs(target_time - time.perf_counter())
                frames.append((frame, objects, frame_latency, inference_latency))
                loop.quit()

            reader.frame_ready.connect(handle_frame)
            reader.finished.connect(loop.quit)
            reader.start()

            while True:
                loop.exec_()
                if not frames:
                    break
                raw_frame, objects, frame_latency, inference_latency = frames.pop(0)
                yield raw_frame, objects, frame_latency, inference_latency

            reader.stop()

        else:
            # Live stream branch using av/streamlink.
            try:
                with StreamContainer.get_container_context(self.source_url) as container:
                    base_pts = None
                    start_time = time.time()
                    video_stream = container.streams.video[0]
                    last_frame_time = time.time()

                    for frame in container.decode(video=0):
                        gap = VideoStreamProcessor.check_stream_health(last_frame_time, self.max_frame_gap)
                        last_frame_time = time.time()

                        if base_pts is None:
                            base_pts = frame.pts

                        frame_time, current_time, delay = VideoStreamProcessor.compute_frame_timing(
                            frame.pts, base_pts, video_stream, start_time
                        )
                        processing_allowed = True

                        if delay > 0:
                            wait_loop = QtCore.QEventLoop()
                            QtCore.QTimer.singleShot(int(delay * 1000), wait_loop.quit)
                            wait_loop.exec_()
                        else:
                            if abs(delay) > self.max_latency:
                                processing_allowed = False
                                print("Skipping frame, max latency exceeded")

                        img = frame.to_ndarray(format='bgr24')
                        start_inference = time.perf_counter()
                        detections = self.process_inference_for_frame(img, processing_allowed)
                        inference_latency = time.perf_counter() - start_inference
                        objects = self.update_tracker_objects(detections)
                        yield img, objects, delay, inference_latency
            except Exception as e:
                raise Exception(f"Error during streaming: {e}")