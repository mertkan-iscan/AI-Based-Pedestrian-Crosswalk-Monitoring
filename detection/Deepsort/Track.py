# Track.py
from detection.Deepsort.KalmanFilter import KalmanFilter

class Track:
    def __init__(self, track_id, bbox, calibrated_centroid, feature=None):
        self.track_id = track_id
        self.bbox = bbox
        self.centroid = calibrated_centroid
        self.age = 1
        self.time_since_update = 0
        # initialize Kalman filter with zero velocity
        self.kalman_filter = KalmanFilter([
            calibrated_centroid[0],
            calibrated_centroid[1],
            0,
            0
        ])
        self.last_timestamp = None
        self.appearance_feature = feature if feature is not None else None

    def predict(self):

        state = self.kalman_filter.predict()
        self.centroid = (int(state[0, 0]), int(state[1, 0]))

        return self.centroid


    def predict_with_dt(self, timestamp: float = None):

        if timestamp is not None and self.last_timestamp is not None:
            dt = timestamp - self.last_timestamp
        else:
            dt = 1.0 / 20.0

        state = self.kalman_filter.predict_with_dt(dt)
        self.centroid = (int(state[0, 0]), int(state[1, 0]))
        self.last_timestamp = timestamp or self.last_timestamp

        return self.centroid

    def update(self, bbox, calibrated_centroid, feature=None, timestamp: float = None):
        self.bbox = bbox
        self.centroid = calibrated_centroid
        self.kalman_filter.update(calibrated_centroid)
        self.last_timestamp = timestamp or self.last_timestamp
        if feature is not None:
            self.appearance_feature = feature
        self.time_since_update = 0
        self.age += 1
