import numpy as np
from scipy.optimize import linear_sum_assignment
from utils.PathUpdater import task_queue

class KalmanFilter:
    def __init__(self, initial_state):
        self.x = np.array(initial_state, dtype=float).reshape((4, 1))
        self.P = np.eye(4) * 10.0
        self.F = np.array([[1, 0, 1, 0],
                           [0, 1, 0, 1],
                           [0, 0, 1, 0],
                           [0, 0, 0, 1]], dtype=float)
        self.H = np.array([[1, 0, 0, 0],
                           [0, 1, 0, 0]], dtype=float)
        self.R = np.eye(2) * 1.0
        self.Q = np.eye(4) * 0.01

    def predict(self):
        self.x = np.dot(self.F, self.x)
        self.P = np.dot(self.F, np.dot(self.P, self.F.T)) + self.Q
        return self.x

    def update(self, measurement):
        z = np.array(measurement, dtype=float).reshape((2, 1))
        y = z - np.dot(self.H, self.x)
        S = np.dot(self.H, np.dot(self.P, self.H.T)) + self.R
        K = np.dot(self.P, np.dot(self.H.T, np.linalg.inv(S)))
        self.x = self.x + np.dot(K, y)
        I = np.eye(self.F.shape[0])
        self.P = np.dot(I - np.dot(K, self.H), self.P)
        return self.x

class Track:
    def __init__(self, track_id, bbox, centroid, feature=None):
        self.track_id = track_id
        self.bbox = bbox          # [x1, y1, x2, y2]
        self.centroid = centroid  # (x, y)
        self.features = []
        if feature is not None:
            self.features.append(feature)
        self.age = 1
        self.time_since_update = 0
        self.kalman_filter = KalmanFilter([centroid[0], centroid[1], 0, 0])

    def predict(self):
        state = self.kalman_filter.predict()
        self.centroid = (int(state[0, 0]), int(state[1, 0]))
        return self.centroid

    def update(self, bbox, centroid, feature=None):
        self.bbox = bbox
        self.centroid = centroid
        self.kalman_filter.update(centroid)
        if feature is not None:
            self.features.append(feature)
        self.time_since_update = 0
        self.age += 1

class DeepSortTracker:
    def __init__(self, max_disappeared=50, max_distance=100):
        self.next_track_id = 0
        self.tracks = []  # List of Track objects
        self.max_disappeared = max_disappeared  # Maximum allowed missed updates
        self.max_distance = max_distance        # Maximum distance for association

    def _compute_cost(self, detections):
        # detections: list of tuples ((cx, cy), bbox)
        if len(self.tracks) == 0:
            return np.empty((0, len(detections)))
        cost_matrix = np.zeros((len(self.tracks), len(detections)), dtype=float)
        for i, track in enumerate(self.tracks):
            predicted_centroid = track.predict()
            for j, (centroid, bbox) in enumerate(detections):
                cost_matrix[i, j] = np.linalg.norm(np.array(predicted_centroid) - np.array(centroid))
        return cost_matrix

    def update(self, rects, features=None):
        """
        rects: list of detections, each detection is either:
               (x1, y1, x2, y2, cls, conf) OR (x1, y1, x2, y2, cls)
        features: optional list of appearance features for each detection
        Returns a dictionary mapping track_id -> (centroid, bbox)
        """
        # If there are no detections, update tracks and remove old ones.
        if len(rects) == 0:
            for track in self.tracks:
                track.time_since_update += 1
            self.tracks = [t for t in self.tracks if t.time_since_update <= self.max_disappeared]
            return {track.track_id: (track.centroid, track.bbox) for track in self.tracks}

        input_centroids = []
        detections = []
        for rect in rects:
            if len(rect) == 6:
                x1, y1, x2, y2, cls, conf = rect
            elif len(rect) == 5:
                x1, y1, x2, y2, cls = rect
                conf = 1.0  # Default confidence value.
            else:
                raise ValueError("Detection tuple must have length 5 or 6.")
            cX = int((x1 + x2) / 2.0)
            cY = int((y1 + y2) / 2.0)
            input_centroids.append((cX, cY))
            # Include the class in the bounding box tuple.
            detections.append(((cX, cY), (x1, y1, x2, y2, cls)))

        cost_matrix = self._compute_cost(detections)
        if cost_matrix.size > 0:
            rows, cols = linear_sum_assignment(cost_matrix)
        else:
            rows, cols = np.array([]), np.array([])

        assigned_tracks = set()
        assigned_detections = set()

        for row, col in zip(rows, cols):
            if cost_matrix[row, col] > self.max_distance:
                continue
            self.tracks[row].update(detections[col][1], detections[col][0],
                                    feature=features[col] if features is not None else None)
            assigned_tracks.add(row)
            assigned_detections.add(col)

        for i, track in enumerate(self.tracks):
            if i not in assigned_tracks:
                track.time_since_update += 1

        self.tracks = [t for t in self.tracks if t.time_since_update <= self.max_disappeared]

        for j in range(len(detections)):
            if j not in assigned_detections:
                new_track = Track(self.next_track_id, detections[j][1], detections[j][0],
                                  feature=features[j] if features is not None else None)
                self.tracks.append(new_track)
                self.next_track_id += 1

        result = {}
        for track in self.tracks:
            result[track.track_id] = (track.centroid, track.bbox)
        return result
