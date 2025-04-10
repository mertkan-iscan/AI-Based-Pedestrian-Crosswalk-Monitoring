import os
import cv2
import time
from PyQt5 import QtCore, QtGui
import queue

from stream.LiveStream import StreamContainer, VideoStreamProcessor

class VideoStreamThread(QtCore.QThread):

    frame_ready = QtCore.pyqtSignal(QtGui.QImage)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, stream_url, parent=None, frame_queue=None):
        super(VideoStreamThread, self).__init__(parent)
        self.stream_url = stream_url
        self._is_running = True
        self.frame_queue = frame_queue if frame_queue is not None else queue.Queue(maxsize=10)

    def wait_until(self, target_time):
        delay = max(0, target_time - time.time())
        if delay > 0:
            loop = QtCore.QEventLoop()
            timer = QtCore.QTimer()
            timer.setTimerType(QtCore.Qt.PreciseTimer)
            timer.setSingleShot(True)
            timer.timeout.connect(loop.quit)
            timer.start(int(delay * 1000))
            loop.exec_()

    def convert_frame_to_qimage(self, bgr_frame):
        """BGR formatındaki görüntüyü QImage (RGB) formatına dönüştürür."""
        rgb_image = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb_image.shape
        bytes_per_line = channels * width
        q_img = QtGui.QImage(rgb_image.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888).copy()
        return q_img

    def _process_video_file(self):
        cap = cv2.VideoCapture(self.stream_url)
        if not cap.isOpened():
            self.error_signal.emit("Cannot open video file: " + self.stream_url)
            return

        start_time = time.time()
        first_timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

        while self._is_running:
            ret, frame = cap.read()
            if not ret:
                break

            current_timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            display_time = start_time + (current_timestamp - first_timestamp)
            self.wait_until(display_time)
            capture_time = time.time()

            q_img = self.convert_frame_to_qimage(frame)
            self.frame_ready.emit(q_img)

            if not self.frame_queue.full():
                self.frame_queue.put((frame, capture_time))

        cap.release()

    def _process_live_stream(self):
        with StreamContainer.get_container_context(self.stream_url) as container:
            base_pts = None
            start_time = time.time()
            video_stream = container.streams.video[0]
            last_frame_time = time.time()

            for frame in container.decode(video=0):
                if not self._is_running:
                    break

                if base_pts is None:
                    base_pts = frame.pts

                frame_time, current_time, delay = VideoStreamProcessor.compute_frame_timing(
                    frame.pts, base_pts, video_stream, start_time
                )
                display_time = start_time + frame_time
                last_frame_time = time.time()

                self.wait_until(display_time)
                capture_time = time.time()

                img = frame.to_ndarray(format='bgr24')
                q_img = self.convert_frame_to_qimage(img)
                self.frame_ready.emit(q_img)

                if not self.frame_queue.full():
                    self.frame_queue.put((img, capture_time))

    def run(self):
        try:
            if os.path.isfile(self.stream_url):
                self._process_video_file()
            else:
                self._process_live_stream()
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()
