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
            self.start_ts         = time.time()
            self.frame_count      = 0
            self.detection_times  = []
            self.inspection_times = []
            self.per_second       = {}   # { second_idx: {'frames':int, 'delays':[]} }

    def log_frame(self):
        now = time.time()
        sec = int(now - self.start_ts)
        with self._lock:
            self.frame_count += 1
            stats = self.per_second.setdefault(sec, {'frames': 0, 'delays': []})
            stats['frames'] += 1

    def log_detection(self, dt: float):
        """Call this in DetectionThread after inference."""
        with self._lock:
            self.detection_times.append(dt)

    def log_inspection(self, dt: float):
        """Call this in CrosswalkInspectThread after region tests."""
        with self._lock:
            self.inspection_times.append(dt)

    def log_delay(self, dt: float):
        """Call this in the GUI after computing display-delay."""
        now = time.time()
        sec = int(now - self.start_ts)
        with self._lock:
            stats = self.per_second.setdefault(sec, {'frames': 0, 'delays': []})
            stats['delays'].append(dt)

    def get_per_second(self):
        with self._lock:
            return sorted(self.per_second.items())

    def get_avg_detection(self):
        with self._lock:
            return sum(self.detection_times) / len(self.detection_times) if self.detection_times else 0.0

    def get_avg_inspection(self):
        with self._lock:
            return sum(self.inspection_times) / len(self.inspection_times) if self.inspection_times else 0.0
