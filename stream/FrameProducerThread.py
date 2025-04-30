import cv2
import time
import queue
from PyQt5 import QtCore
from stream.StreamContainer import StreamContainer

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

def _drop_old_and_put(q: "queue.Queue", item, limit: int):
    while q.qsize() >= limit:
        try:
            q.get_nowait()
        except queue.Empty:
            break
    q.put_nowait(item)

def _produce_frames(
    source: str,
    video_q: "queue.Queue",
    det_q: "queue.Queue",
    is_running,
    detection_fps: float,
    use_av: bool = False,
):
    if detection_fps is None or detection_fps <= 0:
        raise ValueError("detection_fps must be > 0")
    det_interval = 1.0 / detection_fps
    last_det = time.time()

    if use_av:
        with StreamContainer.get_container_context(source) as container:
            base_pts = None
            wall_start = None

            for packet in container.demux(video=0):
                for frame in packet.decode():
                    if frame.pts is None or frame.time_base is None:
                        continue
                    if base_pts is None:
                        base_pts = frame.pts
                        wall_start = time.time()
                    frame_time = (frame.pts - base_pts) * float(frame.time_base)
                    sched_time = wall_start + frame_time
                    capture_time = time.time()
                    img = frame.to_ndarray(format='bgr24')
                    item = (img, capture_time, sched_time)
                    if video_q.maxsize:
                        _drop_old_and_put(video_q, item, video_q.maxsize)
                    else:
                        video_q.put(item)
                if (capture_time - last_det) >= det_interval:
                    if det_q.maxsize:
                        _drop_old_and_put(det_q, item, det_q.maxsize)
                    else:
                        det_q.put(item)
                    last_det += det_interval
        return

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video source: {source}")

    wall_start = time.time()
    video_ts0 = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

    while is_running() and cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        vid_ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        sched_time = wall_start + (vid_ts - video_ts0)
        wait_until(sched_time)
        capture_time = time.time()
        item = (frame.copy(), capture_time, sched_time)
        if video_q.maxsize:
            _drop_old_and_put(video_q, item, video_q.maxsize)
        else:
            video_q.put(item)
        if (capture_time - last_det) >= det_interval:
            if det_q.maxsize:
                _drop_old_and_put(det_q, item, det_q.maxsize)
            else:
                det_q.put(item)
            last_det += det_interval

class FrameProducerThread(QtCore.QThread):
    error_signal = QtCore.pyqtSignal(str)

    def __init__(
        self,
        source: str,
        video_queue: "queue.Queue",
        detection_queue: "queue.Queue",
        detection_fps: float,
        use_av: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        if detection_fps is None or detection_fps <= 0:
            raise ValueError("detection_fps must be > 0")
        self.source = source
        self.video_q = video_queue
        self.detection_q = detection_queue
        self.detection_fps = detection_fps
        self.use_av = use_av
        self._run = True

    def run(self):
        try:
            _produce_frames(
                self.source,
                self.video_q,
                self.detection_q,
                lambda: self._run,
                self.detection_fps,
                self.use_av,
            )
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._run = False
        self.quit()
        self.wait()
