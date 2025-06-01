# stream/VideoConsumerThread.py
import queue
import time
import cv2
from PyQt5 import QtCore, QtGui


from utils.benchmark.MetricSignals import signals

def wait_until(target: float):
    delta = max(0.0, target - time.time())
    if delta > 0:
        loop = QtCore.QEventLoop()
        timer = QtCore.QTimer()
        timer.setTimerType(QtCore.Qt.PreciseTimer)
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(int(delta * 1000))
        loop.exec_()

class VideoConsumerThread(QtCore.QThread):
    frame_ready = QtCore.pyqtSignal(QtGui.QImage)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, video_queue: "queue.Queue", delay, parent=None):
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
                t_consume_start = time.time()
            except queue.Empty:
                continue

            target = display_time + self.delay
            if time.time() > target:
                print("Video frame timed out")
                continue

            wait_until(target)

            # measure QImage conversion + emit
            try:
                qimg = self._to_qimage(frame)
                self.frame_ready.emit(qimg)
                t_consume_end = time.time()
                signals.consumer_logged.emit(t_consume_end - t_consume_start)
            except Exception as e:
                self.error_signal.emit(str(e))

    def stop(self):
        self._running = False
        self.quit()
        self.wait()
