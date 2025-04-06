
from PyQt5 import QtCore, QtGui, QtWidgets


from stream.VideoStreamThread import VideoStreamThread

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
        self.start_stream()
        self.showMaximized()

    def initUI(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        # Create a splitter to show the video and detected objects side by side.
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # Left side: Video display and Stop button
        video_widget = QtWidgets.QWidget()
        video_layout = QtWidgets.QVBoxLayout(video_widget)

        self.video_label = ScalableLabel()
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        self.video_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        video_layout.addWidget(self.video_label)

        stop_btn = QtWidgets.QPushButton("Stop Stream")
        stop_btn.clicked.connect(self.stop_stream)
        video_layout.addWidget(stop_btn)

        splitter.addWidget(video_widget)

        # Right side: Detected objects list
        self.objects_list = QtWidgets.QListWidget()
        splitter.addWidget(self.objects_list)
        splitter.setSizes([600, 200])  # Adjust initial sizes

        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.addWidget(splitter)

    def start_stream(self):
        if "video_path" in self.location and self.location["video_path"]:
            stream_source = self.location["video_path"]
        else:
            stream_source = self.location["stream_url"]

        self.stream_thread = VideoStreamThread(stream_source, self.location["polygons_file"])
        self.stream_thread.frame_ready.connect(self.update_frame)
        self.stream_thread.objects_ready.connect(self.update_detected_objects)
        self.stream_thread.error_signal.connect(self.handle_error)
        self.stream_thread.start()

    def update_frame(self, q_img):
        pixmap = QtGui.QPixmap.fromImage(q_img)
        self.current_pixmap = pixmap
        scaled_pixmap = pixmap.scaled(self.video_label.size(),
                                      QtCore.Qt.KeepAspectRatio,
                                      QtCore.Qt.SmoothTransformation)
        self.video_label.setPixmap(scaled_pixmap)

    def update_detected_objects(self, objects):

        self.objects_list.clear()
        for obj in objects:
            item_text = f"ID: {obj.id}, Type: {obj.object_type}, Region: {obj.region}"
            self.objects_list.addItem(item_text)

    def resizeEvent(self, event):
        if self.current_pixmap:
            scaled_pixmap = self.current_pixmap.scaled(self.video_label.size(),
                                                       QtCore.Qt.KeepAspectRatio,
                                                       QtCore.Qt.SmoothTransformation)
            self.video_label.setPixmap(scaled_pixmap)
        super().resizeEvent(event)

    def handle_error(self, error_msg):
        QtWidgets.QMessageBox.critical(self, "Stream Error", error_msg)
        self.stop_stream()

    def stop_stream(self):
        if hasattr(self, "stream_thread") and self.stream_thread is not None:
            self.stream_thread.stop()
            self.stream_thread = None
        self.close()

    def closeEvent(self, event):
        self.stop_stream()
        event.accept()