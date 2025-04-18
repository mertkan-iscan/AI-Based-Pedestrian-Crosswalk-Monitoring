import cv2
import time

from PyQt5 import QtCore

class VideoFrameReader(QtCore.QObject):

    frame_ready = QtCore.pyqtSignal(object, float)
    finished = QtCore.pyqtSignal()

    def __init__(self, video_path, parent=None):

        super().__init__(parent)

        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise Exception("Cannot open video file: " + video_path)

        self.first_timestamp = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

        self.system_start = time.perf_counter()
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.read_next_frame)

    def start(self):
        self.read_next_frame()

    def read_next_frame(self):

        ret, frame = self.cap.read()

        if not ret:
            self.finished.emit()
            return

        current_timestamp = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

        target_time = self.system_start + (current_timestamp - self.first_timestamp)
        self.frame_ready.emit(frame, target_time)

        now = time.perf_counter()
        delay_ms = max(0, int((target_time - now) * 1000))
        self.timer.start(delay_ms)


    def stop(self):
        self.timer.stop()
        self.cap.release()