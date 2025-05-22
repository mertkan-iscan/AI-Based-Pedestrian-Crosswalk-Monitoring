import time
from threading import Lock

class GlobalState:

    def __init__(self):
        self._lock            = Lock()
        self._objects         = {}     # track_id → DetectedObject
        self._last_seen       = {}     # track_id → timestamp
        self._last_capture    = 0.0    # remember the original capture_time

    def update(self, objects_list, capture_time: float):
        with self._lock:
            for obj in objects_list:
                self._objects[obj.id]   = obj
                self._last_seen[obj.id] = capture_time
            self._last_capture = capture_time

    def remove(self, ids):
        with self._lock:
            for tid in ids:
                self._objects.pop(tid, None)
                self._last_seen.pop(tid, None)

    def get(self):
        with self._lock:
            return list(self._objects.values()), self._last_capture