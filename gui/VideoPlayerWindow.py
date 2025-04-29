import os
import queue
import time
import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

from detection.GlobalState import GlobalState
from gui.OverlayWidget import OverlayWidget
from stream.VideoStreamThread import VideoStreamThread
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
        self.setWindowTitle(f"Live Stream - {location['name']}")
        self.resize(800, 600)
        self.location = location
        self.current_pixmap = None

        # Load birds eye view image (if available)
        birds_eye_path = self.location.get("birds_eye_image", None)
        if birds_eye_path and os.path.exists(birds_eye_path):
            self.birds_eye_pixmap = QtGui.QPixmap(birds_eye_path)
        else:
            self.birds_eye_pixmap = None

        self.initUI()
        self.frame_queue = queue.Queue(maxsize=10)
        self.start_stream()
        self.start_detection()
        self.showMaximized()

    def initUI(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget)

        # Left side: container for video and overlay using a stacked layout.
        video_container = QtWidgets.QWidget()
        self.stack_layout = QtWidgets.QStackedLayout(video_container)
        self.stack_layout.setStackingMode(QtWidgets.QStackedLayout.StackAll)

        self.video_label = ScalableLabel()
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        self.video_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.stack_layout.addWidget(self.video_label)

        self.overlay = OverlayWidget(video_container)

        if self.location.get("homography_matrix") is not None:
            H_inv = np.linalg.inv(np.array(self.location["homography_matrix"]))
            self.overlay.set_inverse_homography(H_inv)

        self.overlay.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.overlay.setStyleSheet("background: transparent;")
        self.stack_layout.addWidget(self.overlay)

        main_layout.addWidget(video_container, stretch=1)

        # Right side: objects list, latency info, stop button, and birds eye view display.
        right_side_widget = QtWidgets.QWidget()
        right_side_widget.setFixedWidth(300)
        right_side_layout = QtWidgets.QVBoxLayout(right_side_widget)

        self.objects_list = QtWidgets.QListWidget()
        right_side_layout.addWidget(self.objects_list)

        self.latency_label = QtWidgets.QLabel("Delay: 0.00 sec")
        right_side_layout.addWidget(self.latency_label)

        button_layout = QtWidgets.QHBoxLayout()
        stop_btn = QtWidgets.QPushButton("Stop Stream")
        stop_btn.clicked.connect(self.stop_stream)
        button_layout.addWidget(stop_btn)
        right_side_layout.addLayout(button_layout)

        birds_eye_title = QtWidgets.QLabel("Bird's Eye View")
        birds_eye_title.setAlignment(QtCore.Qt.AlignCenter)
        right_side_layout.addWidget(birds_eye_title)

        self.birds_eye_view_label = QtWidgets.QLabel()
        right_side_widget.setFixedWidth(400)
        self.birds_eye_view_label.setAlignment(QtCore.Qt.AlignCenter)

        if self.birds_eye_pixmap:
            scaled = self.birds_eye_pixmap.scaled(self.birds_eye_view_label.size(),
                                                  QtCore.Qt.KeepAspectRatio,
                                                  QtCore.Qt.SmoothTransformation)
            self.birds_eye_view_label.setPixmap(scaled)
        else:
            self.birds_eye_view_label.setText("No Bird's Eye Image")
        right_side_layout.addWidget(self.birds_eye_view_label)

        main_layout.addWidget(right_side_widget, stretch=0)

    def start_stream(self):

        if "video_path" in self.location and self.location["video_path"]:
            stream_source = self.location["video_path"]
        else:
            stream_source = self.location["stream_url"]

        self.stream_thread = VideoStreamThread(stream_source, frame_queue=self.frame_queue)
        self.stream_thread.frame_ready.connect(self.update_frame)
        self.stream_thread.error_signal.connect(self.handle_error)
        self.stream_thread.finished.connect(self._on_stream_ended)
        self.stream_thread.start()

    def _on_stream_ended(self):
        # when the video file hits EOF we'll come here
        self.stop_stream()

    def start_detection(self):
        homography = self.location.get("homography_matrix", None)
        if homography is not None:
            homography = np.array(homography)
        self.detection_thread = DetectionThread(self.location["polygons_file"], self.frame_queue,
                                                homography_matrix=homography)
        self.detection_thread.detections_ready.connect(self.update_detected_objects)
        self.detection_thread.error_signal.connect(self.handle_error)
        self.detection_thread.start()

    def update_frame(self, q_img):
        #signal for benchmark
        signals.frame_logged.emit()

        pixmap = QtGui.QPixmap.fromImage(q_img)
        self.current_pixmap = pixmap
        scaled_pixmap = pixmap.scaled(self.video_label.size(),
                                      QtCore.Qt.KeepAspectRatio,
                                      QtCore.Qt.SmoothTransformation)
        self.video_label.setPixmap(scaled_pixmap)
        self.scaled_pixmap_size = (scaled_pixmap.width(), scaled_pixmap.height())
        self.original_frame_size = (pixmap.width(), pixmap.height())
        self.overlay.update()

    def update_detected_objects(self, *args):
        # Pull the latest global detected list and timestamp
        objects, capture_time = GlobalState.instance().get()

        # Update the QListWidget
        self.objects_list.clear()
        for obj in objects:
            text = f"ID: {obj.id}, Type: {obj.object_type}, Region: {obj.region}"
            self.objects_list.addItem(text)

        # Update overlay
        self.overlay.set_detections(
            objects,
            self.original_frame_size,
            self.scaled_pixmap_size
        )
        self.overlay.raise_()

        # Update latency label
        delay = time.time() - capture_time
        self.latency_label.setText(f"Delay: {delay:.2f} sec")

        #signal for benchmark
        signals.delay_logged.emit(delay)

        # Refresh birds-eye view
        self.update_birds_eye_view(objects)

    def update_birds_eye_view(self, objects):
        if self.birds_eye_pixmap is None:
            return

        label_w, label_h = self.birds_eye_view_label.width(), self.birds_eye_view_label.height()
        scale = min(label_w / self.birds_eye_pixmap.width(),
                    label_h / self.birds_eye_pixmap.height())
        scaled_bg = self.birds_eye_pixmap.scaled(
            self.birds_eye_pixmap.width() * scale,
            self.birds_eye_pixmap.height() * scale,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )

        painter = QtGui.QPainter(scaled_bg)
        painter.setPen(QtGui.QPen(QtCore.Qt.red, 6))

        H = np.array(self.location["homography_matrix"]) if self.location.get("homography_matrix") is not None else None

        for obj in objects:

            src_pt = None
            if getattr(obj, "foot_coordinate", None) is not None:
                src_pt = obj.foot_coordinate
                if H is not None:
                    pt = cv2.perspectiveTransform(np.array([[src_pt]], dtype=np.float32), H)[0, 0]
                else:
                    pt = src_pt
            elif getattr(obj, "centroid_coordinate", None) is not None:
                pt = obj.centroid_coordinate  # already calibrated
            else:
                continue

            x, y = pt[0] * scale, pt[1] * scale
            painter.drawEllipse(QtCore.QPointF(x, y), 1, 1)

        painter.end()

        self.birds_eye_view_label.setPixmap(scaled_bg)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.resize(self.video_label.size())
        self.overlay.raise_()

    def handle_error(self, error_msg):
        QtWidgets.QMessageBox.critical(self, "Stream Error", error_msg)
        self.stop_stream()

    def stop_stream(self):
        if hasattr(self, "stream_thread") and self.stream_thread:
            self.stream_thread.stop()
            self.stream_thread = None
        if hasattr(self, "detection_thread") and self.detection_thread:
            self.detection_thread.stop()
            self.detection_thread = None

        # --- NEW: emit the per-second report if we were playing a file ---
        video_file = self.location.get("video_path")
        if video_file:
            report_path = ReportManager(video_file).save_per_second_report()
            print(f"Per‐second report written to: {report_path}")
            # optionally pop up a message box:
            QtWidgets.QMessageBox.information(
                self, "Performance Report",
                f"Per‐second report saved to:\n{report_path}"
            )

        self.close()

    def closeEvent(self, event):
        self.stop_stream()
        event.accept()