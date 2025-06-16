import time
from threading import Lock

class Benchmark:
    _instance = None

    def __init__(self):
        self._lock = Lock()
        self.reset()

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = Benchmark()
        return cls._instance

    def reset(self):
        with self._lock:
            self.start_ts            = time.time()
            self.frame_count         = 0
            self.detection_times     = []
            self.inspection_times    = []
            self.queue_waits         = []
            self.postproc_times      = []
            self.scheduling_delays   = []
            self.total_latencies     = []
            self.consumer_latencies  = []
            self.per_second          = {}

    def log_frame(self):
        now = time.time()
        sec = int(now - self.start_ts)
        with self._lock:
            self.frame_count += 1
            stats = self.per_second.setdefault(sec, {'frames': 0, 'delays': []})
            stats['frames'] += 1

    def log_detection(self, dt: float):
        with self._lock:
            self.detection_times.append(dt)

    def log_inspection(self, dt: float):
        with self._lock:
            self.inspection_times.append(dt)

    def log_delay(self, dt: float):
        now = time.time()
        sec = int(now - self.start_ts)
        with self._lock:
            self.per_second.setdefault(sec, {'frames': 0, 'delays': []})['delays'].append(dt)

    def log_queue_wait(self, dt: float):
        with self._lock:
            self.queue_waits.append(dt)

    def log_postproc(self, dt: float):
        with self._lock:
            self.postproc_times.append(dt)

    def log_scheduling_delay(self, dt: float):
        with self._lock:
            self.scheduling_delays.append(dt)

    def log_total_latency(self, dt: float):
        with self._lock:
            self.total_latencies.append(dt)

    def log_consumer_latency(self, dt: float):
        with self._lock:
            self.consumer_latencies.append(dt)

    def get_per_second(self):
        """Return data for each second since start (sec_idx, {'frames':…, 'delays':…})."""
        with self._lock:
            return sorted(self.per_second.items())