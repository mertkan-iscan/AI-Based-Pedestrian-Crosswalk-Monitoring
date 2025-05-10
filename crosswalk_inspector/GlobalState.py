import time
from threading import Lock

class GlobalState:

    def __init__(self, expiry_seconds: float = 5.0):
        self._lock            = Lock()
        self._objects         = {}     # track_id → DetectedObject
        self._last_seen       = {}     # track_id → timestamp
        self._last_capture    = 0.0    # remember the original capture_time
        self.expiry_seconds   = expiry_seconds


    def update(self, objects_list, capture_time: float):
        with self._lock:
            for obj in objects_list:
                self._objects[obj.id]   = obj
                self._last_seen[obj.id] = capture_time

            # purge expired
            expired = [
                tid for tid, ts in self._last_seen.items()
                if capture_time - ts > self.expiry_seconds
            ]
            for tid in expired:
                del self._last_seen[tid]
                del self._objects[tid]

            # **store** the real frame timestamp
            self._last_capture = capture_time

    def get(self):
        now = time.time()
        with self._lock:
            # purge any that just went stale against now
            expired = [
                tid for tid, ts in self._last_seen.items()
                if now - ts > self.expiry_seconds
            ]
            for tid in expired:
                del self._last_seen[tid]
                del self._objects[tid]

            # return the objects *and* the actual capture time
            return list(self._objects.values()), self._last_capture
