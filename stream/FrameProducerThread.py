# stream/FrameProducerThread.py
import cv2
import time
import queue
from PyQt5 import QtCore


def wait_until(target: float):
    """Sleep until `target` (epoch-seconds) without freezing the thread."""
    delta = max(0.0, target - time.time())
    if delta > 0:
        loop = QtCore.QEventLoop()
        timer = QtCore.QTimer()
        timer.setTimerType(QtCore.Qt.PreciseTimer)
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(int(delta * 1000))
        loop.exec_()


def _drop_old_and_put(q: "queue.Queue", item, limit: int):
    while q.qsize() >= limit:
        try:
            q.get_nowait()
        except queue.Empty:
            break
    q.put_nowait(item)


def _produce_frames(
    stream_url: str,
    video_q: "queue.Queue",
    det_q: "queue.Queue",
    is_running,
    skip_for_det: int,
):
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video source: {stream_url}")

    wall_start    = time.time()
    video_ts0     = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
    idx           = 0
    v_limit       = video_q.maxsize or 0
    d_limit       = det_q.maxsize or 0

    while is_running() and cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break

        vid_ts     = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        sched_time = wall_start + (vid_ts - video_ts0)

        wait_until(sched_time)

        item = (frame.copy(), time.time(), sched_time)

        if v_limit:
            _drop_old_and_put(video_q, item, v_limit)
        else:
            video_q.put(item)

        if idx % skip_for_det == 0:
            if d_limit:
                _drop_old_and_put(det_q, item, d_limit)
            else:
                det_q.put(item)

        idx += 1

    cap.release()


class FrameProducerThread(QtCore.QThread):
    error_signal = QtCore.pyqtSignal(str)

    def __init__(
        self,
        stream_url: str,
        video_queue: "queue.Queue",
        detection_queue: "queue.Queue",
        skip_frames: int = 2,
        parent=None,
    ):
        super().__init__(parent)
        self.url          = stream_url
        self.video_q      = video_queue
        self.detection_q  = detection_queue
        self.skip_frames  = max(1, int(skip_frames))
        self._run         = True

    def run(self):
        try:
            _produce_frames(
                self.url,
                self.video_q,
                self.detection_q,
                lambda: self._run,
                self.skip_frames,
            )
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._run = False
        self.quit()
        self.wait()
