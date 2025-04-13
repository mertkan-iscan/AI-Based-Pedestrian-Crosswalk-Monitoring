from PyQt5 import QtCore, QtGui, QtWidgets
from gui.OverlayWidget import OverlayWidget
from stream.VideoStreamThread import VideoStreamThread
from stream.DetectionThread import DetectionThread
import queue
import time

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
        self.overlay.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.overlay.setStyleSheet("background: transparent;")
        self.stack_layout.addWidget(self.overlay)

        main_layout.addWidget(video_container, stretch=1)

        # Right side: objects list, latency (delay) info, and buttons.
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

        main_layout.addWidget(right_side_widget, stretch=0)

    def start_stream(self):
        if "video_path" in self.location and self.location["video_path"]:
            stream_source = self.location["video_path"]
        else:
            stream_source = self.location["stream_url"]
        self.stream_thread = VideoStreamThread(stream_source, frame_queue=self.frame_queue)
        self.stream_thread.frame_ready.connect(self.update_frame)
        self.stream_thread.error_signal.connect(self.handle_error)
        self.stream_thread.start()

    def start_detection(self):
        self.detection_thread = DetectionThread(self.location["polygons_file"], self.frame_queue)
        self.detection_thread.detections_ready.connect(self.update_detected_objects)
        self.detection_thread.error_signal.connect(self.handle_error)
        self.detection_thread.start()

    def update_frame(self, q_img):
        pixmap = QtGui.QPixmap.fromImage(q_img)
        self.current_pixmap = pixmap
        scaled_pixmap = pixmap.scaled(self.video_label.size(),
                                      QtCore.Qt.KeepAspectRatio,
                                      QtCore.Qt.SmoothTransformation)
        self.video_label.setPixmap(scaled_pixmap)
        self.scaled_pixmap_size = (scaled_pixmap.width(), scaled_pixmap.height())
        self.original_frame_size = (pixmap.width(), pixmap.height())
        self.overlay.update()

    def update_detected_objects(self, objects, bbox_capture_time):
        self.objects_list.clear()
        for obj in objects:
            item_text = f"ID: {obj.id}, Type: {obj.object_type}, Region: {obj.region}"
            self.objects_list.addItem(item_text)
        self.overlay.set_detections(objects, self.original_frame_size, self.scaled_pixmap_size)
        self.overlay.raise_()
        # Compute and display the delay between the frame used for inference and now.
        delay = time.time() - bbox_capture_time
        self.latency_label.setText(f"Delay: {delay:.2f} sec")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.resize(self.video_label.size())
        self.overlay.raise_()

    def handle_error(self, error_msg):
        QtWidgets.QMessageBox.critical(self, "Stream Error", error_msg)
        self.stop_stream()

    def stop_stream(self):
        if hasattr(self, "stream_thread") and self.stream_thread is not None:
            self.stream_thread.stop()
            self.stream_thread = None
        if hasattr(self, "detection_thread") and self.detection_thread is not None:
            self.detection_thread.stop()
            self.detection_thread = None
        self.close()

    def closeEvent(self, event):
        self.stop_stream()
        event.accept()
