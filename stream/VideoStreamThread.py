import cv2
from PyQt5 import QtCore, QtGui
import queue
import time

class VideoStreamThread(QtCore.QThread):
    frame_ready = QtCore.pyqtSignal(QtGui.QImage)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, stream_url, parent=None, frame_queue=None):
        super(VideoStreamThread, self).__init__(parent)
        self.stream_url = stream_url
        self._is_running = True
        self.frame_queue = frame_queue if frame_queue is not None else queue.Queue(maxsize=10)

    def run(self):
        try:
            cap = cv2.VideoCapture(self.stream_url)
            if not cap.isOpened():
                raise Exception("Cannot open video stream")
            while self._is_running:
                ret, frame = cap.read()
                if not ret:
                    break
                capture_time = time.time()  # record the frame capture time
                # Convert frame for display
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width, channels = rgb_image.shape
                bytes_per_line = channels * width
                q_img = QtGui.QImage(rgb_image.data, width, height, bytes_per_line,
                                     QtGui.QImage.Format_RGB888).copy()
                self.frame_ready.emit(q_img)
                # Push (frame, capture_time) to the shared queue if not full.
                if not self.frame_queue.full():
                    self.frame_queue.put((frame, capture_time))
                # Sleep a bit to roughly control frame rate.
                time.sleep(0.03)
            cap.release()
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()
