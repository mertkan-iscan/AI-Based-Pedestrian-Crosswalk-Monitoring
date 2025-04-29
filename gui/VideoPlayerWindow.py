# gui/VideoPlayerWindow.py
import os
import queue
import time
import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

from detection.GlobalState import GlobalState
from gui.OverlayWidget import OverlayWidget
from stream.FrameProducerThread import FrameProducerThread
from stream.VideoConsumerThread import VideoConsumerThread
from stream.DetectionThread import DetectionThread
from utils.benchmark.MetricSignals import signals
from utils.benchmark.ReportManager import ReportManager


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
        self.location             = location
        self.current_pixmap       = None
        self.original_frame_size  = (1, 1)   # <- defined early
        self.scaled_pixmap_size   = (1, 1)
        self._report_shown        = False

        birds_eye_path = self.location.get("birds_eye_image")
        self.birds_eye_pixmap = QtGui.QPixmap(birds_eye_path) if birds_eye_path and os.path.exists(birds_eye_path) else None

        self._build_ui()

        # bounded queues apply back-pressure
        self.video_queue     = queue.Queue(maxsize=0)
        self.detection_queue = queue.Queue(maxsize=0)
        self.delay_seconds   = 5

        self._start_threads()
        self.showMaximized()

    # ------------------------------------------------------------------ #
    def _build_ui(self):
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        layout  = QtWidgets.QHBoxLayout(central)

        # -------- video & overlay stack -------------------------------
        video_container = QtWidgets.QWidget()
        self.stack      = QtWidgets.QStackedLayout(video_container)
        self.stack.setStackingMode(QtWidgets.QStackedLayout.StackAll)

        self.video_label = ScalableLabel()
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        self.video_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.stack.addWidget(self.video_label)

        self.overlay = OverlayWidget(video_container)
        if self.location.get("homography_matrix") is not None:
            H_inv = np.linalg.inv(np.array(self.location["homography_matrix"]))
            self.overlay.set_inverse_homography(H_inv)

        self.stack.addWidget(self.overlay)
        layout.addWidget(video_container, stretch=1)

        # -------- right-side panel ------------------------------------
        side            = QtWidgets.QWidget()
        side.setFixedWidth(300)
        side_layout     = QtWidgets.QVBoxLayout(side)

        self.objects_list = QtWidgets.QListWidget()
        side_layout.addWidget(self.objects_list)

        self.latency_label = QtWidgets.QLabel("Delay: 0.00 s")
        side_layout.addWidget(self.latency_label)

        stop_btn = QtWidgets.QPushButton("Stop Stream")
        stop_btn.clicked.connect(self.stop_stream)
        side_layout.addWidget(stop_btn)

        side_layout.addWidget(QtWidgets.QLabel("Bird's Eye View", alignment=QtCore.Qt.AlignCenter))

        self.birds_eye_view = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.birds_eye_view.setFixedWidth(400)
        if self.birds_eye_pixmap:
            self.birds_eye_view.setPixmap(self.birds_eye_pixmap.scaled(self.birds_eye_view.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        else:
            self.birds_eye_view.setText("No Bird's-Eye Image")
        side_layout.addWidget(self.birds_eye_view)

        layout.addWidget(side, stretch=0)

    # ------------------------------------------------------------------ #
    def _start_threads(self):
        source = self.location.get("video_path") or self.location["stream_url"]

        self.producer = FrameProducerThread(source, self.video_queue, self.detection_queue, skip_frames=2)
        self.producer.error_signal.connect(self._handle_error)
        self.producer.start()

        self.video_consumer = VideoConsumerThread(self.video_queue, delay=self.delay_seconds)
        self.video_consumer.frame_ready.connect(self._update_frame)
        self.video_consumer.error_signal.connect(self._handle_error)
        self.video_consumer.start()

        homography = np.array(self.location["homography_matrix"]) if self.location.get("homography_matrix") is not None else None
        self.detection_thread = DetectionThread(self.location["polygons_file"], self.detection_queue, homography_matrix=homography, delay=self.delay_seconds)
        self.detection_thread.detections_ready.connect(self._update_detections)
        self.detection_thread.error_signal.connect(self._handle_error)
        self.detection_thread.start()

    # ------------------------------------------------------------------ #
    def _update_frame(self, q_img):
        signals.frame_logged.emit()

        pixmap = QtGui.QPixmap.fromImage(q_img)
        self.current_pixmap = pixmap

        scaled = pixmap.scaled(self.video_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.video_label.setPixmap(scaled)

        self.scaled_pixmap_size  = (scaled.width(), scaled.height())
        self.original_frame_size = (pixmap.width(), pixmap.height())

        self.overlay.update()

    # ------------------------------------------------------------------ #
    def _update_detections(self, *_):
        objects, capture_time = GlobalState.instance().get()

        # if first video frame hasn’t arrived yet, skip this batch
        if self.original_frame_size == (1, 1):
            return

        self.objects_list.clear()
        for obj in objects:
            self.objects_list.addItem(f"ID:{obj.id}  {obj.object_type}  {obj.region}")

        self.overlay.set_detections(objects, self.original_frame_size, self.scaled_pixmap_size)
        self.overlay.raise_()

        self.latency_label.setText(f"Delay: {time.time() - capture_time:.2f} s")
        signals.delay_logged.emit(time.time() - capture_time)

        self._update_birds_eye(objects)

    # ------------------------------------------------------------------ #
    def _update_birds_eye(self, objects):
        if not self.birds_eye_pixmap:
            return

        lw, lh   = self.birds_eye_view.width(), self.birds_eye_view.height()
        scale    = min(lw / self.birds_eye_pixmap.width(), lh / self.birds_eye_pixmap.height())
        bg_scaled = self.birds_eye_pixmap.scaled(self.birds_eye_pixmap.width()*scale, self.birds_eye_pixmap.height()*scale, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

        painter = QtGui.QPainter(bg_scaled)
        painter.setPen(QtGui.QPen(QtCore.Qt.red, 6))
        H = np.array(self.location["homography_matrix"]) if self.location.get("homography_matrix") is not None else None

        for obj in objects:
            pt_src = obj.foot_coordinate or obj.centroid_coordinate
            if pt_src is None:
                continue
            pt = cv2.perspectiveTransform(np.array([[pt_src]], dtype=np.float32), H)[0,0] if H is not None else pt_src
            painter.drawEllipse(QtCore.QPointF(pt[0]*scale, pt[1]*scale), 1, 1)

        painter.end()
        self.birds_eye_view.setPixmap(bg_scaled)

    # ------------------------------------------------------------------ #
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.overlay.resize(self.video_label.size())
        self.overlay.raise_()

    # ------------------------------------------------------------------ #
    def _handle_error(self, msg):
        QtWidgets.QMessageBox.critical(self, "Stream Error", msg)
        self.stop_stream()

    # ------------------------------------------------------------------ #
    def stop_stream(self):
        for attr in ("video_consumer", "detection_thread", "producer"):
            t = getattr(self, attr, None)
            if t:
                t.stop()
                setattr(self, attr, None)
        self.close()

    # ------------------------------------------------------------------ #
    def closeEvent(self, event):
        if self.location.get("video_path") and not self._report_shown:
            self._report_shown = True
            report = ReportManager(self.location["video_path"]).save_per_second_report()
            QtWidgets.QMessageBox.information(self, "Performance Report", f"Per-second report saved to:\n{report}")
        event.accept()
