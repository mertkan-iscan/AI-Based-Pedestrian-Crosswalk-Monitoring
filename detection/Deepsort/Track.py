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

    def predict(self) -> Tuple[float, float]:
        state = self.kalman_filter.predict()
        self.centroid = (state[0, 0], state[1, 0])
        return self.centroid

    def predict_with_dt(self, timestamp: Optional[float] = None) -> Tuple[float, float]:
        if timestamp is not None and self.last_timestamp is not None:
            dt = timestamp - self.last_timestamp
        else:
            dt = 1.0 / 20.0
        state = self.kalman_filter.predict_with_dt(dt)
        self.centroid = (state[0, 0], state[1, 0])
        self.last_timestamp = timestamp or self.last_timestamp
        return self.centroid

    def update(
        self,
        bbox: Tuple[int, int, int, int, int],
        calibrated_centroid: Tuple[float, float],
        feature: Optional[np.ndarray] = None,
        timestamp: Optional[float] = None,
    ):
        self.bbox = bbox
        self.centroid = calibrated_centroid
        self.kalman_filter.update(calibrated_centroid)
        self.last_timestamp = timestamp or self.last_timestamp
        if feature is not None:
            self.feature_gallery.append(feature.astype(np.float32))
        self.time_since_update = 0
        self.age += 1

    def get_gallery(self) -> List[np.ndarray]:
        return list(self.feature_gallery)