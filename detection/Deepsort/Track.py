from collections import deque
from typing import List, Tuple, Optional
import numpy as np
from detection.Deepsort.KalmanFilter import KalmanFilter

class Track:
    def __init__(
        self,
        track_id: int,
        bbox: Tuple[int, int, int, int, int],
        calibrated_centroid: Tuple[float, float],
        feature: Optional[np.ndarray] = None,
        nn_budget: int = 50,
        velocity_history_size: int = 5,
    ):
        self.track_id = track_id
        self.bbox = bbox
        self.centroid = calibrated_centroid
        self.age = 1
        self.time_since_update = 0
        self.kalman_filter = KalmanFilter(
            [calibrated_centroid[0], calibrated_centroid[1], 0.0, 0.0]
        )
        self.last_timestamp: Optional[float] = None
        self.feature_gallery: deque[np.ndarray] = deque(maxlen=nn_budget)
        if feature is not None:
            self.feature_gallery.append(feature.astype(np.float32))
        self.motion_distance: Optional[float] = None
        self.appearance_distance: Optional[float] = None
        self.velocity_history: deque[Tuple[float, float]] = deque(maxlen=velocity_history_size)
        self.prev_measured_centroid: Tuple[float, float] = calibrated_centroid
        self.prev_measure_timestamp: Optional[float] = None

    def predict(self) -> Tuple[float, float]:
        state = self.kalman_filter.predict()
        self.centroid = (state[0, 0], state[1, 0])
        return self.centroid

    def predict_with_dt(self, timestamp: Optional[float] = None) -> Tuple[float, float]:
        if self.last_timestamp is not None and timestamp is not None:
            dt = timestamp - self.last_timestamp
        else:
            dt = 1.0 / 10.0
        state = self.kalman_filter.predict_with_dt(dt)
        self.centroid = (state[0, 0], state[1, 0])
        if timestamp is not None:
            self.last_timestamp = timestamp
        return self.centroid

    def update(
        self,
        bbox: Tuple[int, int, int, int, int],
        calibrated_centroid: Tuple[float, float],
        feature: Optional[np.ndarray] = None,
        timestamp: Optional[float] = None,
    ):
        if self.prev_measure_timestamp is not None and timestamp is not None:
            dt = timestamp - self.prev_measure_timestamp
            if dt > 0:
                vx = (calibrated_centroid[0] - self.prev_measured_centroid[0]) / dt
                vy = (calibrated_centroid[1] - self.prev_measured_centroid[1]) / dt
                self.velocity_history.append((vx, vy))

        self.bbox = bbox
        self.centroid = calibrated_centroid
        self.kalman_filter.update(calibrated_centroid)

        if self.velocity_history:
            avg_vx = sum(v[0] for v in self.velocity_history) / len(self.velocity_history)
            avg_vy = sum(v[1] for v in self.velocity_history) / len(self.velocity_history)
            self.kalman_filter.x[2, 0] = avg_vx
            self.kalman_filter.x[3, 0] = avg_vy

        if feature is not None:
            self.feature_gallery.append(feature.astype(np.float32))

        self.time_since_update = 0
        self.age += 1

        if timestamp is not None:
            self.prev_measure_timestamp = timestamp
            self.prev_measured_centroid = calibrated_centroid
            self.last_timestamp = timestamp

    def get_gallery(self) -> List[np.ndarray]:
        return list(self.feature_gallery)
