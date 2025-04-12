import numpy as np
from scipy.optimize import linear_sum_assignment
from concurrent.futures import ThreadPoolExecutor

from detection.Deepsort.CNNFeatureExtractor import CNNFeatureExtractor
from detection.Deepsort.Track import Track


class DeepSortTracker:
    def __init__(self, max_disappeared=50, max_distance=100, device='cuda',
                 appearance_weight=0.5, motion_weight=0.5):
        self.next_track_id = 0
        self.tracks = []  # List of Track objects.
        self.max_disappeared = max_disappeared  # Maximum allowed missed updates.
        self.max_distance = max_distance  # Threshold for association.
        self.appearance_weight = appearance_weight  # Weight for appearance cost.
        self.motion_weight = motion_weight  # Weight for motion cost.
        self.feature_extractor = CNNFeatureExtractor(device=device)
        # Initialize a thread pool to allow concurrent feature extraction.
        self.executor = ThreadPoolExecutor(max_workers=2)

    def _compute_cost(self, detections):
        """
        Compute a cost matrix that combines motion and appearance distances.
        detections: list of tuples (centroid, bbox, feature)
        """
        if len(self.tracks) == 0:
            return np.empty((0, len(detections)))
        cost_matrix = np.zeros((len(self.tracks), len(detections)), dtype=float)
        for i, track in enumerate(self.tracks):
            predicted_centroid = track.predict()
            track_feature = track.appearance_feature
            for j, (centroid, bbox, detection_feature) in enumerate(detections):
                # Motion cost: Euclidean distance.
                motion_distance = np.linalg.norm(np.array(predicted_centroid) - np.array(centroid))
                # Appearance cost: cosine distance.
                if track_feature is not None and detection_feature is not None:
                    dot_product = np.dot(track_feature, detection_feature)
                    norm_track = np.linalg.norm(track_feature) + 1e-6
                    norm_detection = np.linalg.norm(detection_feature) + 1e-6
                    cosine_similarity = dot_product / (norm_track * norm_detection)
                    appearance_distance = 1 - cosine_similarity
                else:
                    appearance_distance = 1.0  # Maximum cost when appearance info is missing.
                cost_matrix[i, j] = (self.motion_weight * motion_distance +
                                     self.appearance_weight * appearance_distance)
        return cost_matrix

    def update(self, rects, frame=None, features=None):
        """
        Update tracks with new detections.
        rects: list of detections, each detection is either:
               (x1, y1, x2, y2, cls, conf) or (x1, y1, x2, y2, cls)
        frame: the current image frame (numpy array) used to compute features if features are not provided.
        features: optional list of precomputed appearance features.
        Returns a dictionary mapping track_id -> (centroid, bbox)
        """
        # If no detections, update tracks’ missed counts.
        if len(rects) == 0:
            for track in self.tracks:
                track.time_since_update += 1
            self.tracks = [t for t in self.tracks if t.time_since_update <= self.max_disappeared]
            return {track.track_id: (track.centroid, track.bbox) for track in self.tracks}

        detections = []
        if features is None and frame is not None:
            bboxes_list = []
            centroids = []
            for rect in rects:
                if len(rect) == 6:
                    x1, y1, x2, y2, cls, conf = rect
                elif len(rect) == 5:
                    x1, y1, x2, y2, cls = rect
                    conf = 1.0
                else:
                    raise ValueError("Detection tuple must have length 5 or 6.")
                cX = int((x1 + x2) / 2.0)
                cY = int((y1 + y2) / 2.0)
                centroids.append((cX, cY))
                bboxes_list.append((x1, y1, x2, y2))
            # Submit the batch extraction job asynchronously.
            future = self.executor.submit(self.feature_extractor.extract_features_batch, frame, bboxes_list)
            batch_features = future.result()
            for i, rect in enumerate(rects):
                if len(rect) == 6:
                    x1, y1, x2, y2, cls, conf = rect
                else:
                    x1, y1, x2, y2, cls = rect
                detections.append((centroids[i], (x1, y1, x2, y2, cls), batch_features[i]))
        else:
            # Fallback to sequential processing (or using provided features).
            for i, rect in enumerate(rects):
                if len(rect) == 6:
                    x1, y1, x2, y2, cls, conf = rect
                elif len(rect) == 5:
                    x1, y1, x2, y2, cls = rect
                    conf = 1.0
                else:
                    raise ValueError("Detection tuple must have length 5 or 6.")
                cX = int((x1 + x2) / 2.0)
                cY = int((y1 + y2) / 2.0)
                centroid = (cX, cY)
                if features is not None:
                    detection_feature = features[i]
                elif frame is not None:
                    detection_feature = self.feature_extractor.extract_features(frame, (x1, y1, x2, y2))
                else:
                    detection_feature = None
                detections.append((centroid, (x1, y1, x2, y2, cls), detection_feature))

        # Compute cost matrix and assign detections to tracks.
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
                                    feature=detections[col][2])
            assigned_tracks.add(row)
            assigned_detections.add(col)

        for i, track in enumerate(self.tracks):
            if i not in assigned_tracks:
                track.time_since_update += 1

        self.tracks = [t for t in self.tracks if t.time_since_update <= self.max_disappeared]

        for j in range(len(detections)):
            if j not in assigned_detections:
                new_track = Track(self.next_track_id, detections[j][1], detections[j][0],
                                  feature=detections[j][2])
                self.tracks.append(new_track)
                self.next_track_id += 1

        result = {track.track_id: (track.centroid, track.bbox) for track in self.tracks}
        return result
