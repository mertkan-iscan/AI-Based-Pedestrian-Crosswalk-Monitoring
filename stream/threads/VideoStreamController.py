import os
import queue

import numpy as np
from PyQt5 import QtCore

from crosswalk_inspector.CrosswalkInspectThread import CrosswalkInspectThread
from crosswalk_inspector.TrafficLightMonitorThread import TrafficLightMonitorThread
from stream.threads.MotWriterThread import MotWriterThread
from stream.threads.FrameProducerThread import FrameProducerThread
from stream.threads.VideoConsumerThread import VideoConsumerThread
from stream.threads.DetectionThread import DetectionThread
from utils.ConfigManager import ConfigManager


class VideoStreamController(QtCore.QObject):
    frame_ready = QtCore.pyqtSignal(object)
    detection_update = QtCore.pyqtSignal()
    error_occurred = QtCore.pyqtSignal(str)

    def __init__(self, location, state, editor):
        super().__init__()
        self.location = location
        self.state = state
        self.editor = editor

        self.video_queue = queue.Queue()
        self.detection_queue = queue.Queue()

        cfg = ConfigManager()
        self.detection_fps = cfg.get_detection_fps()
        self.delay_seconds = cfg.get_delay_seconds()
        self.traffic_light_fps = cfg.get_traffic_light_fps()

        self.mot_writer = None
        self.tl_monitor = None
        self.producer = None
        self.crosswalk_monitor = None
        self.video_consumer = None
        self.detection_thread = None
        self.H_inv = None

        self._setup()

    def _setup(self):
        source, source_name, mot_filename = self._setup_video_source(self.location)
        self.mot_writer = MotWriterThread(mot_filename)
        self.mot_writer.start()

        homography, H_inv = self._compute_homography_and_inverse(self.location)
        self.H_inv = H_inv

        self.tl_monitor = TrafficLightMonitorThread(delay=self.delay_seconds)
        self.tl_monitor.error_signal.connect(self._on_error)
        self.tl_monitor.start()

        use_av = "stream_url" in self.location
        self.producer = FrameProducerThread(
            source,
            self.video_queue,
            self.detection_queue,
            detection_fps=self.detection_fps,
            use_av=use_av,
            traffic_light_fps=self.traffic_light_fps,
            editor=self.editor
        )

        self.producer.traffic_light_crops.connect(
            self.tl_monitor.on_new_crops, QtCore.Qt.QueuedConnection
        )
        self.producer.error_signal.connect(self._on_error)
        self.producer.start()

        self.crosswalk_monitor = CrosswalkInspectThread(
            editor=self.editor,
            global_state=self.state,
            tl_objects=self.producer.tl_objects,
            check_period=0.2,
            homography_inv=H_inv
        )
        self.crosswalk_monitor.error_signal.connect(self._on_error)
        self.crosswalk_monitor.start()

        self.video_consumer = VideoConsumerThread(self.video_queue, delay=self.delay_seconds)
        self.video_consumer.frame_ready.connect(self._on_frame_ready)
        self.video_consumer.error_signal.connect(self._on_error)
        self.video_consumer.start()

        self.detection_thread = DetectionThread(
            self.location["polygons_file"],
            self.detection_queue,
            state=self.state,
            homography_matrix=homography,
            detection_fps=self.detection_fps,
            delay=self.delay_seconds,
            mot_writer=self.mot_writer
        )
        self.detection_thread.detections_ready.connect(self._on_detection_ready)
        self.detection_thread.error_signal.connect(self._on_error)
        self.detection_thread.start()

    def _setup_video_source(self, location):
        source = location.get("video_path") or location.get("stream_url")
        if not source:
            self._on_error("Location must provide either 'video_path' or 'stream_url'.")
            return None, None, None
        source_name = location.get("name", "unknown_source")
        base = os.path.basename(source_name)
        name, _ = os.path.splitext(base)
        mot_filename = f"{name}_MOT.txt"
        return source, source_name, mot_filename

    def _compute_homography_and_inverse(self, location):
        homography = None
        H_inv = None
        if location.get("homography_matrix") is not None:
            homography = np.array(location["homography_matrix"], dtype=np.float32)
            try:
                H_inv = np.linalg.inv(homography)
            except np.linalg.LinAlgError:
                H_inv = None
        return homography, H_inv

    def _on_frame_ready(self, q_img):
        self.frame_ready.emit(q_img)

    def _on_detection_ready(self, *args):
        self.detection_update.emit()

    def _on_error(self, msg):
        self.error_occurred.emit(msg)

    def stop(self):
        for thread in (
                self.video_consumer,
                self.detection_thread,
                self.producer,
                self.crosswalk_monitor,
                self.tl_monitor,
        ):
            if thread:
                thread.stop()
        if self.mot_writer:
            self.mot_writer.stop()

        self.video_consumer = None
        self.detection_thread = None
        self.producer = None
        self.crosswalk_monitor = None
        self.tl_monitor = None
        self.mot_writer = None
