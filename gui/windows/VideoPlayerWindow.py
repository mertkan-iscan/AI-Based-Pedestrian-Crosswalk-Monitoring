import os
import queue
import time

import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

from crosswalk_inspector.CrosswalkInspectThread import CrosswalkInspectThread
from stream.threads.MotWriterThread import MotWriterThread
from utils.GlobalState import GlobalState
from crosswalk_inspector.TrafficLightMonitorThread import TrafficLightMonitorThread
from gui.windows.DetectionLayerWidget import DetectionLayerWidget
from stream.threads.FrameProducerThread import FrameProducerThread
from stream.threads.VideoConsumerThread import VideoConsumerThread
from stream.threads.DetectionThread import DetectionThread
from utils.ConfigManager import ConfigManager
from utils.benchmark.MetricReporter import MetricReporter
from utils.benchmark.MetricSignals import signals
from utils.RegionManager import RegionManager


class ScalableLabel(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(0, 0)

    def sizeHint(self):
        return QtCore.QSize(100, 100)

    def minimumSizeHint(self):
        return QtCore.QSize(0, 0)

class VideoPlayerWindow(QtWidgets.QMainWindow):
    def __init__(self, location, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Live Stream – {location['name']}")
        self.location = location

        self.editor = RegionManager(self.location.get('polygons_file'))

        self.current_pixmap = None
        self.original_frame_size = (1, 1)
        self.scaled_pixmap_size = (1, 1)
        self._report_shown = False
        self.state = GlobalState()

        cfg = ConfigManager()
        self.detection_fps = cfg.get_detection_fps()
        self.delay_seconds = cfg.get_delay_seconds()
        self.traffic_light_fps = cfg.get_traffic_light_fps()

        birds_eye_path = self.location.get("birds_eye_image")
        self.birds_eye_pixmap = QtGui.QPixmap(birds_eye_path) if birds_eye_path and os.path.exists(birds_eye_path) else None
        self._build_ui()
        self._metric_reporter = MetricReporter()

        signals.frame_logged.connect(self._metric_reporter.on_frame)
        signals.detection_logged.connect(self._metric_reporter.on_detection)
        signals.inspection_logged.connect(self._metric_reporter.on_inspection)
        signals.delay_logged.connect(self._metric_reporter.on_delay)
        signals.queue_wait_logged.connect(self._update_queue_wait_label)
        signals.detection_logged.connect(self._update_inference_label)
        signals.postproc_logged.connect(self._update_postproc_label)
        signals.scheduling_logged.connect(self._update_scheduling_label)
        signals.total_latency_logged.connect(self._update_total_latency_label)
        signals.consumer_logged.connect(self._update_consumer_label)
        self.video_queue = queue.Queue()
        self.detection_queue = queue.Queue()
        self._start_threads()
        self.showMaximized()

    def _build_ui(self):
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        video_container = QtWidgets.QWidget()
        self.stack = QtWidgets.QStackedLayout(video_container)
        self.stack.setStackingMode(QtWidgets.QStackedLayout.StackAll)
        self.video_label = ScalableLabel()
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        self.stack.addWidget(self.video_label)

        self.overlay = DetectionLayerWidget(video_container)

        if self.location.get("homography_matrix") is not None:
            H_inv = np.linalg.inv(np.array(self.location["homography_matrix"]))
            self.overlay.set_inverse_homography(H_inv)
        self.stack.addWidget(self.overlay)
        layout.addWidget(video_container, 1)
        side = QtWidgets.QWidget()
        side.setFixedWidth(300)
        side_layout = QtWidgets.QVBoxLayout(side)
        self.objects_list = QtWidgets.QListWidget()
        side_layout.addWidget(self.objects_list)

        self.latency_label = QtWidgets.QLabel("Delay: 0.00 s")
        side_layout.addWidget(self.latency_label)
        self.queue_wait_label = QtWidgets.QLabel("Queue wait: 0.00 s")
        side_layout.addWidget(self.queue_wait_label)
        self.inference_label = QtWidgets.QLabel("Inference: 0.00 s")
        side_layout.addWidget(self.inference_label)
        self.postproc_label = QtWidgets.QLabel("Post-process: 0.00 s")
        side_layout.addWidget(self.postproc_label)
        self.scheduling_label = QtWidgets.QLabel("Scheduling delay: 0.00 s")
        side_layout.addWidget(self.scheduling_label)
        self.total_latency_label = QtWidgets.QLabel("Total latency: 0.00 s")
        side_layout.addWidget(self.total_latency_label)
        self.consumer_label = QtWidgets.QLabel("Consumer latency: 0.00 s")
        side_layout.addWidget(self.consumer_label)
        stop_btn = QtWidgets.QPushButton("Stop Stream")
        stop_btn.clicked.connect(self.stop_stream)

        side_layout.addWidget(stop_btn)
        side_layout.addWidget(QtWidgets.QLabel("Bird's Eye View", alignment=QtCore.Qt.AlignCenter))
        self.birds_eye_view = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.birds_eye_view.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        if self.birds_eye_pixmap:
            pix = self.birds_eye_pixmap.scaledToWidth(280, QtCore.Qt.SmoothTransformation)
            self.birds_eye_view.setPixmap(pix)
            self.birds_eye_view.setFixedHeight(pix.height())
        else:
            self.birds_eye_view.setText("No Bird's-Eye Image")
        side_layout.addWidget(self.birds_eye_view)
        layout.addWidget(side, 0)

    def _update_queue_wait_label(self, dt):
        self.queue_wait_label.setText(f"Queue wait: {dt:.2f} s")

    def _update_inference_label(self, dt):
        self.inference_label.setText(f"Inference: {dt:.2f} s")

    def _update_postproc_label(self, dt):
        self.postproc_label.setText(f"Post-process: {dt:.2f} s")

    def _update_scheduling_label(self, dt):
        self.scheduling_label.setText(f"Scheduling delay: {dt:.2f} s")

    def _update_total_latency_label(self, dt):
        self.total_latency_label.setText(f"Total latency: {dt:.2f} s")

    def _update_consumer_label(self, dt):
        self.consumer_label.setText(f"Consumer latency: {dt:.2f} s")

    def _start_threads(self):
        # 1) Source setup
        source = self.location.get("video_path") or self.location["stream_url"]

        source_name = self.location["name"]
        import os
        base = os.path.basename(source_name)
        name, _ = os.path.splitext(base)
        mot_filename = f"{name}_MOT.txt"

        # 3) MotWriterThread başlat
        self.mot_writer = MotWriterThread(mot_filename)
        self.mot_writer.start()

        # 2) Compute homography and its inverse
        homography = None
        H_inv = None
        if self.location.get("homography_matrix") is not None:
            homography = np.array(self.location["homography_matrix"], dtype=np.float32)
            try:
                H_inv = np.linalg.inv(homography)
            except np.linalg.LinAlgError:
                H_inv = None

        # 3) Start the traffic‐light monitor
        self.tl_monitor = TrafficLightMonitorThread(delay=self.delay_seconds)
        self.tl_monitor.error_signal.connect(self._handle_error)
        self.tl_monitor.start()

        # 4) Start the frame producer (also emits TL crops)
        self.producer = FrameProducerThread(
            source,
            self.video_queue,
            self.detection_queue,
            detection_fps=self.detection_fps,
            traffic_light_fps=self.traffic_light_fps,
            editor=self.editor
        )

        self.producer.traffic_light_crops.connect(
            self.tl_monitor.on_new_crops, QtCore.Qt.QueuedConnection
        )

        self.producer.error_signal.connect(self._handle_error)
        self.producer.start()

        # 5) Start the crosswalk inspector, now passing H_inv
        self.crosswalk_monitor = CrosswalkInspectThread(
            editor=self.editor,
            global_state=self.state,
            tl_objects=self.producer.tl_objects,
            check_period=0.2,
            homography_inv=H_inv
        )
        self.crosswalk_monitor.error_signal.connect(self._handle_error)
        self.crosswalk_monitor.start()

        # 6) Start the video consumer
        self.video_consumer = VideoConsumerThread(self.video_queue, delay=self.delay_seconds)
        self.video_consumer.frame_ready.connect(self._update_frame)
        self.video_consumer.error_signal.connect(self._handle_error)
        self.video_consumer.start()

        # 7) Finally, start the detection thread (uses homography forward)
        self.detection_thread = DetectionThread(
            self.location["polygons_file"],
            self.detection_queue,
            state=self.state,
            homography_matrix=homography,
            detection_fps=self.detection_fps,
            delay=self.delay_seconds,
            mot_writer=self.mot_writer
        )
        self.detection_thread.detections_ready.connect(self._update_detection_list_panel)
        self.detection_thread.error_signal.connect(self._handle_error)
        self.detection_thread.start()

    def _update_frame(self, q_img):
        signals.frame_logged.emit()
        pixmap = QtGui.QPixmap.fromImage(q_img)
        self.current_pixmap = pixmap
        scaled = pixmap.scaled(self.video_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.video_label.setPixmap(scaled)
        self.scaled_pixmap_size = (scaled.width(), scaled.height())
        self.original_frame_size = (pixmap.width(), pixmap.height())
        self.overlay.resize(self.video_label.size())
        self.overlay.update()

    def _update_detection_list_panel(self, *_):

        if self.crosswalk_monitor is None or self.producer is None:
            return

        objects, capture_time = self.state.get()
        if self.original_frame_size == (1, 1):
            return
        self.objects_list.clear()
        for obj in objects:
            self.objects_list.addItem(f"ID:{obj.id}  {obj.object_type}  {obj.region}")
        self.overlay.set_detections(objects, self.original_frame_size, self.scaled_pixmap_size)
        self.overlay.raise_()
        delay = time.time() - capture_time
        self.latency_label.setText(f"Delay: {delay:.2f} s")
        signals.delay_logged.emit(delay)
        self._update_birds_eye(objects)

        from collections import defaultdict

        tl_overlay_groups = defaultdict(lambda: {"centers": [], "red_center": None})
        if self.crosswalk_monitor is not None and self.producer is not None:
            for pack in self.editor.crosswalk_packs:
                for tl in pack.traffic_light:
                    pack_id = pack.id
                    light_type = tl.get("light_type")
                    center = tl.get("center")
                    signal_color = tl.get("signal_color")
                    key = (pack_id, light_type)
                    if center is not None:
                        tl_overlay_groups[key]["centers"].append(center)
                        if signal_color == "red":
                            tl_overlay_groups[key]["red_center"] = center

        tl_overlays = []
        for (pack_id, light_type), group in tl_overlay_groups.items():
            # Use red center if it exists, otherwise average all
            if group["red_center"] is not None:
                chosen_center = group["red_center"]
            elif group["centers"]:
                chosen_center = (
                    int(sum(c[0] for c in group["centers"]) / len(group["centers"])),
                    int(sum(c[1] for c in group["centers"]) / len(group["centers"]))
                )
            else:
                continue
            status = self.crosswalk_monitor.get_effective_traffic_light_status(
                pack_id, self.producer.tl_objects, light_type
            )
            tl_overlays.append({
                "center": chosen_center,
                "status": status,
                "light_type": light_type,
            })
        self.overlay.set_traffic_light_overlays(tl_overlays)

    def _update_birds_eye(self, objects):
        if not self.birds_eye_pixmap:
            return
        orig = self.birds_eye_pixmap
        label_width = self.birds_eye_view.width()
        scaled_bg = orig.scaled(
            label_width,
            orig.height(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
        scale_x = scaled_bg.width() / orig.width()
        scale_y = scaled_bg.height() / orig.height()

        painter = QtGui.QPainter(scaled_bg)
        H = (
            np.array(self.location["homography_matrix"])
            if self.location.get("homography_matrix") is not None
            else None
        )

        for obj in objects:
            if getattr(obj, "surface_point", None) is not None:
                pt = obj.surface_point
            elif getattr(obj, "centroid_coordinate", None) is not None:
                pt = obj.raw_surface_point
            else:
                continue

            x = pt[0] * scale_x
            y = pt[1] * scale_y

            if obj.object_type == "person":
                painter.setPen(QtGui.QPen(QtGui.QColor("yellow"), 6))
            else:
                painter.setPen(QtGui.QPen(QtGui.QColor("lightblue"), 6))

            painter.drawEllipse(QtCore.QPointF(x, y), 1, 1)

        painter.end()
        self.birds_eye_view.setPixmap(scaled_bg)

    def _handle_error(self, msg):
        QtWidgets.QMessageBox.critical(self, "Stream Error", msg)
        self.stop_stream()

    def stop_stream(self):
        for attr in ("video_consumer", "detection_thread", "producer", "crosswalk_monitor", "tl_monitor"):
            t = getattr(self, attr, None)
            if t:
                t.stop()
                setattr(self, attr, None)
        if self.mot_writer:
            self.mot_writer.stop()
            self.mot_writer = None
        self.close()

    def closeEvent(self, event):
        event.accept()