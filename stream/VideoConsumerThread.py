# stream/VideoConsumerThread.py
import queue
import time
import cv2
from PyQt5 import QtCore, QtGui

from stream.FrameProducerThread import wait_until


class VideoConsumerThread(QtCore.QThread):
    frame_ready = QtCore.pyqtSignal(QtGui.QImage)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, video_queue: "queue.Queue", delay: float = 1.0, parent=None):
        super().__init__(parent)
        self.queue = video_queue
        self.delay = float(delay)
        self._running = True

    @staticmethod
    def _to_qimage(bgr):
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w, c = rgb.shape
        return QtGui.QImage(rgb.data, w, h, c * w, QtGui.QImage.Format_RGB888).copy()

    def run(self):
        while self._running:
            try:
                frame, _, display_time = self.queue.get(timeout=0.05)
            except queue.Empty:
                continue

            target = display_time + self.delay

            # drop if we’re already too late
            if time.time() > target:
                print("Video frame timed out")
                continue

            wait_until(target)

            try:
                self.frame_ready.emit(self._to_qimage(frame))
            except Exception as e:
                self.error_signal.emit(str(e))

    def stop(self):
        self._running = False
        self.quit()
        self.wait()
