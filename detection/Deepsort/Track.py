from detection.Deepsort.KalmanFilter import KalmanFilter

class Track:
    def __init__(self, track_id, bbox, centroid, feature=None):
        self.track_id = track_id
        self.bbox = bbox
        self.centroid = centroid
        self.age = 1
        self.time_since_update = 0
        self.kalman_filter = KalmanFilter([centroid[0], centroid[1], 0, 0])
        # Store the latest appearance feature vector.
        self.appearance_feature = feature if feature is not None else None

    def predict(self):
        state = self.kalman_filter.predict()
        self.centroid = (int(state[0, 0]), int(state[1, 0]))
        return self.centroid

    def update(self, bbox, centroid, feature=None):
        self.bbox = bbox
        self.centroid = centroid
        self.kalman_filter.update(centroid)
        if feature is not None:
            self.appearance_feature = feature
        self.time_since_update = 0
        self.age += 1