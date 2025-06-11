import collections

import cv2
import time
import queue

from PyQt5 import QtCore
from stream.StreamContainer import StreamContainer
from utils.RegionManager import RegionManager
from stream.crosswalk_inspector.TrafficLight import TrafficLight
from concurrent.futures import ThreadPoolExecutor

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

def _drop_old_and_put(q: queue.Queue, item, limit: int):
    print(">>> Dropping old items")
    while q.qsize() >= limit:
        try:
            q.get_nowait()
        except queue.Empty:
            break
    q.put_nowait(item)

class FrameProducerThread(QtCore.QThread):

    error_signal = QtCore.pyqtSignal(str)
    traffic_light_crops = QtCore.pyqtSignal(list)

    def __init__(
        self,
        source: str,
        video_queue: queue.Queue,
        detection_queue: queue.Queue,
        detection_fps: float,
        traffic_light_fps: float,
        use_av: bool,
        editor: RegionManager,
        max_resolution: tuple = (1920, 1080),
        parent=None
    ):
        super().__init__(parent)

        if detection_fps is None or detection_fps <= 0:
            raise ValueError("detection_fps must be > 0")
        if traffic_light_fps is None or traffic_light_fps <= 0:
            raise ValueError("traffic_light_fps must be > 0")

        self.source            = source
        self.video_q           = video_queue
        self.detection_q       = detection_queue
        self.detection_fps     = detection_fps
        self.traffic_light_fps = traffic_light_fps
        self._tl_interval      = 1.0 / traffic_light_fps
        self._last_tl_emit     = 0.0
        self.use_av            = use_av
        self._run              = True
        self.editor            = editor
        self.max_resolution    = max_resolution

        self.tl_objects        = []
        if self.editor:
            for pack in self.editor.crosswalk_packs:
                groups = {}
                for cfg in pack.traffic_light:
                    gid = cfg['id']
                    groups.setdefault(gid, {'type': cfg['light_type'], 'lights': {}})
                    groups[gid]['lights'][cfg['signal_color']] = {
                        'center': cfg['center'],
                        'radius': cfg['radius']
                    }
                for gid, gcfg in groups.items():
                    self.tl_objects.append(
                        TrafficLight(pack.id, gid, gcfg['type'], gcfg['lights'])
                    )

        self._crop_executor = ThreadPoolExecutor(max_workers=5)

    def run(self):
        try:
            #if self.use_av:
            #    print(">>> Using av")
            #    self._run_av()
            #else:
                print(">>> Using opencv")
                self._run_opencv()

        except Exception as e:
            self.error_signal.emit(str(e))

    def _produce_crop(self, frame, capture_time):
        batch = [(tl, tl.crop_regions(frame), capture_time) for tl in self.tl_objects]
        self.traffic_light_crops.emit(batch)


    @staticmethod
    def _downscale_if_needed(frame, max_res):
        h, w = frame.shape[:2]
        max_w, max_h = max_res
        if w > max_w or h > max_h:
            scale = min(max_w / w, max_h / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return frame

    def _run_opencv(self):
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {self.source}")
        wall_start = time.time()
        video_ts0 = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        last_det = time.time()
        det_interval = 1.0 / self.detection_fps

        while self._run and cap.isOpened():
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.01)
                continue

            # frame = self._downscale_if_needed(frame, self.max_resolution)
            vid_ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            sched_time = wall_start + (vid_ts - video_ts0)
            wait_until(sched_time)
            capture_time = time.time()
            item = (frame.copy(), capture_time, sched_time)

            now = capture_time
            if self.tl_objects and (now - self._last_tl_emit) >= self._tl_interval:
                frame_for_crop = frame.copy()
                self._crop_executor.submit(self._produce_crop, frame_for_crop, capture_time)
                self._last_tl_emit = now

            if self.video_q.maxsize:
                _drop_old_and_put(self.video_q, item, self.video_q.maxsize)
            else:
                self.video_q.put(item)

            if (capture_time - last_det) >= det_interval:
                if self.detection_q.maxsize:
                    _drop_old_and_put(self.detection_q, item, self.detection_q.maxsize)
                else:
                    self.detection_q.put(item)
                last_det += det_interval

    def _run_av(self):
        base_pts = None
        wall_start = None
        last_det = time.time()
        det_interval = 1.0 / self.detection_fps

        frame_buffer = collections.deque()
        buffer_delay = 3.0

        with StreamContainer.get_container_context(self.source) as container:
            for packet in container.demux(video=0):
                for frame_pkt in packet.decode():
                    if frame_pkt.pts is None or frame_pkt.time_base is None:
                        continue
                    if base_pts is None:
                        base_pts = frame_pkt.pts
                        wall_start = time.time()
                    frame_time = (frame_pkt.pts - base_pts) * float(frame_pkt.time_base)
                    sched_time = wall_start + frame_time
                    capture_time = time.time()
                    img = frame_pkt.to_ndarray(format='bgr24')

                    #img = self._downscale_if_needed(img, self.max_resolution)

                    frame_buffer.append((img.copy(), capture_time, sched_time))

                    now = capture_time
                    while frame_buffer and (now - frame_buffer[0][1]) >= buffer_delay:
                        buffered_img, buffered_capture_time, buffered_sched_time = frame_buffer.popleft()

                        item = (buffered_img, buffered_capture_time, buffered_sched_time)

                        if self.video_q.maxsize:
                            _drop_old_and_put(self.video_q, item, self.video_q.maxsize)
                        else:
                            self.video_q.put(item)

                        if (buffered_capture_time - last_det) >= det_interval:
                            if self.detection_q.maxsize:
                                _drop_old_and_put(self.detection_q, item, self.detection_q.maxsize)
                            else:
                                self.detection_q.put(item)
                            last_det = buffered_capture_time

                        if self.tl_objects and (now - self._last_tl_emit) >= self._tl_interval:
                            img_for_crop = buffered_img.copy()
                            self._crop_executor.submit(self._produce_crop, img_for_crop, buffered_capture_time)
                            self._last_tl_emit = now

    def stop(self):
        self._run = False
        self._crop_executor.shutdown(wait=False)
        self.quit()
        self.wait()
