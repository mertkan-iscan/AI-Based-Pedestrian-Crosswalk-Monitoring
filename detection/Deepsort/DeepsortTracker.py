import numpy as np
from scipy.optimize import linear_sum_assignment
from concurrent.futures import ThreadPoolExecutor

from detection.Deepsort.CNNFeatureExtractor import CNNFeatureExtractor
from detection.Deepsort.Track import Track

class DeepSortTracker:
    def __init__(self, max_disappeared=50, max_distance=100, device='cuda',
                 appearance_weight=0.5, motion_weight=0.5, homography_matrix=None):

        self.next_track_id = 0
        self.tracks = []
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.appearance_weight = appearance_weight
        self.motion_weight = motion_weight
        self.homography_matrix = homography_matrix
        self.feature_extractor = CNNFeatureExtractor(device=device)
        self.executor = ThreadPoolExecutor(max_workers=1)# will be benchmarked

    def calibrate_point(self, point, homography_matrix):

        pt = np.array([point[0], point[1], 1.0], dtype=np.float32)
        transformed = np.dot(homography_matrix, pt)

        if transformed[2] != 0:
            return (transformed[0] / transformed[2], transformed[1] / transformed[2])
        else:
            return (transformed[0], transformed[1])

    def _compute_cost(self, detections):

        if len(self.tracks) == 0:
            return np.empty((0, len(detections)))
        cost_matrix = np.zeros((len(self.tracks), len(detections)), dtype=float)

        for i, track in enumerate(self.tracks):

            predicted_centroid = track.predict()
            track_feature = track.appearance_feature

            for j, (calibrated_centroid, bbox, detection_feature) in enumerate(detections):

                motion_distance = np.linalg.norm(np.array(predicted_centroid) - np.array(calibrated_centroid))

                if track_feature is not None and detection_feature is not None:
                    dot_product = np.dot(track_feature, detection_feature)
                    norm_track = np.linalg.norm(track_feature) + 1e-6
                    norm_detection = np.linalg.norm(detection_feature) + 1e-6
                    cosine_similarity = dot_product / (norm_track * norm_detection)
                    appearance_distance = 1 - cosine_similarity
                else:
                    appearance_distance = 1.0
                cost_matrix[i, j] = (self.motion_weight * motion_distance +
                                     self.appearance_weight * appearance_distance)
        return cost_matrix

    def update(self, rects, frame=None, features=None):

        if len(rects) == 0:
            for track in self.tracks:
                track.time_since_update += 1
            self.tracks = [t for t in self.tracks if t.time_since_update <= self.max_disappeared]
            return {track.track_id: (track.centroid, track.bbox) for track in self.tracks}

        detections = []
        if features is None and frame is not None:

            bboxes_list = []
            calibrated_centroids = []

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
                centroid_pixel = (cX, cY)

                if self.homography_matrix is not None:
                    calibrated = self.calibrate_point(centroid_pixel, self.homography_matrix)
                else:
                    calibrated = centroid_pixel

                calibrated_centroids.append(calibrated)
                bboxes_list.append((x1, y1, x2, y2))

            future = self.executor.submit(self.feature_extractor.extract_features_batch, frame, bboxes_list)
            batch_features = future.result()

            for i, rect in enumerate(rects):
                if len(rect) == 6:
                    x1, y1, x2, y2, cls, conf = rect
                else:
                    x1, y1, x2, y2, cls = rect

                detections.append((calibrated_centroids[i], (x1, y1, x2, y2, cls), batch_features[i]))
        else:
            # Fallback: process sequentially.

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
                centroid_pixel = (cX, cY)
                if self.homography_matrix is not None:
                    calibrated = self.calibrate_point(centroid_pixel, self.homography_matrix)
                else:
                    calibrated = centroid_pixel
                if features is not None:
                    detection_feature = features[i]
                elif frame is not None:
                    detection_feature = self.feature_extractor.extract_features(frame, (x1, y1, x2, y2))
                else:
                    detection_feature = None
                detections.append((calibrated, (x1, y1, x2, y2, cls), detection_feature))

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
            # Use the calibrated centroid for updating.
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
