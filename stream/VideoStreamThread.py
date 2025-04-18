import os
import cv2
import time
import queue
from PyQt5 import QtCore, QtGui

from stream.StreamContainer import StreamContainer


def wait_until(target_time):
    """Wait until a target timestamp using a Qt event loop."""
    delay = max(0, target_time - time.time())
    if delay > 0:
        loop = QtCore.QEventLoop()
        timer = QtCore.QTimer()
        timer.setTimerType(QtCore.Qt.PreciseTimer)
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(int(delay * 1000))
        loop.exec_()


def process_video_file(stream_url, wait_func, convert_frame_to_qimage, frame_ready_callback, frame_queue, error_callback, is_running):
    """Process a video file by reading frames and synchronizing their display.

    The loop now checks the `is_running` callback to allow termination.
    """
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        error_callback("Cannot open video file: " + stream_url)
        return

    start_time = time.time()
    first_timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

    while is_running() and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        current_timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        display_time = start_time + (current_timestamp - first_timestamp)
        wait_func(display_time)

        # Check again after waiting
        if not is_running():
            break

        capture_time = time.time()
        q_img = convert_frame_to_qimage(frame)
        frame_ready_callback(q_img)

        if not frame_queue.full():
            frame_queue.put((frame, capture_time))

    cap.release()


def process_live_stream(stream_url, wait_func, convert_frame_to_qimage, frame_ready_callback, frame_queue, error_callback, is_running):
    """Process a live stream using the provided container and synchronization logic."""
    with StreamContainer.get_container_context(stream_url) as container:
        base_pts = None
        start_time = time.time()
        video_stream = container.streams.video[0]

        for frame in container.decode(video=0):
            if not is_running():
                break

            if base_pts is None:
                base_pts = frame.pts

            frame_time, current_time, delay = compute_frame_timing(
                frame.pts, base_pts, video_stream, start_time
            )
            display_time = start_time + frame_time
            wait_func(display_time)

            # Check again after waiting
            if not is_running():
                break

            img = frame.to_ndarray(format='bgr24')
            q_img = convert_frame_to_qimage(img)
            frame_ready_callback(q_img)

            if not frame_queue.full():
                frame_queue.put((img, display_time))

def compute_frame_timing(frame_pts, base_pts, video_stream, start_time):
    relative_pts = frame_pts - base_pts if frame_pts is not None else 0
    frame_time = float(relative_pts * video_stream.time_base)
    current_time = time.time() - start_time
    delay = frame_time - current_time
    return frame_time, current_time, delay

class VideoStreamThread(QtCore.QThread):

    frame_ready = QtCore.pyqtSignal(QtGui.QImage)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, stream_url, parent=None, frame_queue=None):
        super(VideoStreamThread, self).__init__(parent)
        self.stream_url = stream_url
        self._is_running = True
        self.frame_queue = frame_queue if frame_queue is not None else queue.Queue(maxsize=10)

    def convert_frame_to_qimage(self, bgr_frame):
        rgb_image = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb_image.shape
        bytes_per_line = channels * width
        q_img = QtGui.QImage(rgb_image.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888).copy()
        return q_img

    def run(self):
        try:
            if os.path.isfile(self.stream_url):
                process_video_file(
                    self.stream_url,
                    wait_until,
                    self.convert_frame_to_qimage,
                    self.frame_ready.emit,
                    self.frame_queue,
                    self.error_signal.emit,
                    lambda: self._is_running
                )
            else:
                process_live_stream(
                    self.stream_url,
                    wait_until,
                    self.convert_frame_to_qimage,
                    self.frame_ready.emit,
                    self.frame_queue,
                    self.error_signal.emit,
                    lambda: self._is_running
                )
        except Exception as e:
            self.error_signal.emit(f"Error: {repr(e)}")

    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()
