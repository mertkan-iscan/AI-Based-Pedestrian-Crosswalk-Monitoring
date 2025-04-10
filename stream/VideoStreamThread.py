import os
import cv2
import time
from PyQt5 import QtCore, QtGui
import queue

from stream.LiveStream import StreamContainer, VideoStreamProcessor

class VideoStreamThread(QtCore.QThread):
    # Emits a QImage when the frame is ready.
    frame_ready = QtCore.pyqtSignal(QtGui.QImage)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, stream_url, parent=None, frame_queue=None):
        super(VideoStreamThread, self).__init__(parent)
        self.stream_url = stream_url
        self._is_running = True
        self.frame_queue = frame_queue if frame_queue is not None else queue.Queue(maxsize=10)

    def wait_until(self, target_time):
        """Wait until target_time using QTimer and a temporary QEventLoop for a non-blocking delay."""
        delay = max(0, target_time - time.time())
        if delay > 0:
            loop = QtCore.QEventLoop()
            timer = QtCore.QTimer()
            timer.setTimerType(QtCore.Qt.PreciseTimer)
            timer.setSingleShot(True)
            timer.timeout.connect(loop.quit)
            timer.start(int(delay * 1000))  # delay in milliseconds
            loop.exec_()

    def run(self):
        try:
            if os.path.isfile(self.stream_url):
                # --- Video File Branch ---
                cap = cv2.VideoCapture(self.stream_url)
                if not cap.isOpened():
                    self.error_signal.emit("Cannot open video file: " + self.stream_url)
                    return

                # Define start_time as the wall clock time when the first frame is processed.
                start_time = time.time()
                # Get timestamp (in sec) of the first frame (using CAP_PROP_POS_MSEC).
                first_timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                last_frame_time = time.time()

                while self._is_running:
                    ret, frame = cap.read()
                    if not ret:
                        break  # End-of-file reached.

                    # Get current frame timestamp from video file.
                    current_timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                    # Compute the target display time based on the file's internal timestamps.
                    display_time = start_time + (current_timestamp - first_timestamp)

                    # (Optional) You can check stream health here if desired.
                    last_frame_time = time.time()

                    # Wait nonblockingly until display_time.
                    self.wait_until(display_time)
                    capture_time = time.time()

                    # Convert the BGR image (from cv2) to an RGB QImage.
                    rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    height, width, channels = rgb_image.shape
                    bytes_per_line = channels * width
                    q_img = QtGui.QImage(rgb_image.data, width, height, bytes_per_line,
                                         QtGui.QImage.Format_RGB888).copy()

                    # Emit the frame.
                    self.frame_ready.emit(q_img)

                    # Enqueue the raw frame (and its capture time) for detection if there's room.
                    if not self.frame_queue.full():
                        self.frame_queue.put((frame, capture_time))

                cap.release()

            else:
                # --- Live Stream Branch ---
                with StreamContainer.get_container_context(self.stream_url) as container:
                    base_pts = None
                    start_time = time.time()
                    video_stream = container.streams.video[0]
                    max_latency = 0.5  # maximum allowed lateness (in seconds)
                    last_frame_time = time.time()

                    for frame in container.decode(video=0):
                        if not self._is_running:
                            break

                        if base_pts is None:
                            base_pts = frame.pts

                        # Compute frame timing using VideoStreamProcessor.
                        frame_time, current_time, delay = VideoStreamProcessor.compute_frame_timing(
                            frame.pts, base_pts, video_stream, start_time
                        )
                        # Compute absolute display time.
                        display_time = start_time + frame_time

                        # Check stream health (if desired).
                        # VideoStreamProcessor.check_stream_health(last_frame_time, 5.0)
                        last_frame_time = time.time()

                        # Wait nonblockingly until the display time.
                        self.wait_until(display_time)
                        capture_time = time.time()

                        # Convert the frame to a BGR ndarray.
                        img = frame.to_ndarray(format='bgr24')
                        rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        height, width, channels = rgb_image.shape
                        bytes_per_line = channels * width
                        q_img = QtGui.QImage(rgb_image.data, width, height, bytes_per_line,
                                             QtGui.QImage.Format_RGB888).copy()

                        self.frame_ready.emit(q_img)

                        if not self.frame_queue.full():
                            self.frame_queue.put((img, capture_time))
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()
