import numpy as np
from scipy.optimize import linear_sum_assignment
from concurrent.futures import ThreadPoolExecutor

from detection.Deepsort.CNNFeatureExtractor import CNNFeatureExtractor
from detection.Deepsort.Track import Track

class DeepSortTracker:
    def __init__(
        self,
        max_disappeared=50,
        max_distance=100,
        device='cuda',
        appearance_weight=0.5,
        motion_weight=0.5,
        homography_matrix=None
    ):
        self.next_track_id      = 0
        self.tracks             = []
        self.max_disappeared    = max_disappeared
        self.max_distance       = max_distance
        self.appearance_weight  = appearance_weight
        self.motion_weight      = motion_weight
        self.homography_matrix  = homography_matrix
        self.feature_extractor  = CNNFeatureExtractor(device=device)
        self.executor           = ThreadPoolExecutor(max_workers=1)

    def calibrate_point(self, point, homography_matrix):
        pt = np.array([point[0], point[1], 1.0], dtype=np.float32)
        transformed = homography_matrix @ pt
        if transformed[2] != 0:
            return (transformed[0] / transformed[2], transformed[1] / transformed[2])
        else:
            return (transformed[0], transformed[1])

    def _compute_cost(self, detections, timestamp: float):
        """
        Build the cost matrix using motion + appearance distances.
        We first predict each track’s new centroid at `timestamp`.
        """
        if len(self.tracks) == 0:
            return np.empty((0, len(detections)))

        cost_matrix = np.zeros((len(self.tracks), len(detections)), dtype=float)

        for i, track in enumerate(self.tracks):
            # predict to the given time
            predicted_centroid = track.predict(timestamp)
            track_feature      = track.appearance_feature

            for j, (cal_centroid, bbox, det_feature) in enumerate(detections):
                # motion cost
                motion_distance = np.linalg.norm(
                    np.array(predicted_centroid) - np.array(cal_centroid)
                )

                # appearance cost (cosine distance)
                if track_feature is not None and det_feature is not None:
                    dot = np.dot(track_feature, det_feature)
                    norm_track = np.linalg.norm(track_feature) + 1e-6
                    norm_det   = np.linalg.norm(det_feature)  + 1e-6
                    cosine_sim = dot / (norm_track * norm_det)
                    appearance_distance = 1.0 - cosine_sim
                else:
                    appearance_distance = 1.0

                cost_matrix[i, j] = (
                    self.motion_weight     * motion_distance +
                    self.appearance_weight * appearance_distance
                )

        return cost_matrix

    def update(self,
               rects,
               frame=None,
               features=None,
               timestamp: float = None
    ):
        """
        rects: list of detections, each [x1, y1, x2, y2, cls[, conf]]
        timestamp: the capture_time of this batch (in seconds since epoch)
        """
        # 1) no detections → age all tracks and purge expired
        if len(rects) == 0:
            for track in self.tracks:
                track.time_since_update += 1
            self.tracks = [
                t for t in self.tracks
                if t.time_since_update <= self.max_disappeared
            ]
            return {t.track_id: (t.centroid, t.bbox) for t in self.tracks}

        # 2) build detection list: (calibrated_centroid, bbox_with_cls, feature)
        detections = []
        if features is None and frame is not None:
            bboxes = []
            cents  = []
            for rect in rects:
                # unpack
                if len(rect) == 6:
                    x1, y1, x2, y2, cls, _ = rect
                else:
                    x1, y1, x2, y2, cls = rect
                cX = int((x1 + x2) / 2.0)
                cY = int((y1 + y2) / 2.0)
                pixel_centroid = (cX, cY)

                if self.homography_matrix is not None:
                    calibrated = self.calibrate_point(
                        pixel_centroid,
                        self.homography_matrix
                    )
                else:
                    calibrated = pixel_centroid

                cents.append(calibrated)
                bboxes.append((x1, y1, x2, y2))

            future = self.executor.submit(
                self.feature_extractor.extract_features_batch,
                frame,
                bboxes
            )
            batch_features = future.result()

            for i, rect in enumerate(rects):
                if len(rect) == 6:
                    x1, y1, x2, y2, cls, _ = rect
                else:
                    x1, y1, x2, y2, cls = rect

                detections.append((
                    cents[i],
                    (x1, y1, x2, y2, cls),
                    batch_features[i]
                ))

        else:
            # fallback: sequential feature extraction or provided features
            for i, rect in enumerate(rects):
                if len(rect) == 6:
                    x1, y1, x2, y2, cls, _ = rect
                else:
                    x1, y1, x2, y2, cls = rect

                cX = int((x1 + x2) / 2.0)
                cY = int((y1 + y2) / 2.0)
                pixel_centroid = (cX, cY)

                if self.homography_matrix is not None:
                    calibrated = self.calibrate_point(
                        pixel_centroid,
                        self.homography_matrix
                    )
                else:
                    calibrated = pixel_centroid

                if features is not None:
                    det_feature = features[i]
                else:
                    det_feature = self.feature_extractor.extract_features(
                        frame, (x1, y1, x2, y2)
                    )

                detections.append((
                    calibrated,
                    (x1, y1, x2, y2, cls),
                    det_feature
                ))

        # 3) compute cost matrix with proper Δt
        cost_matrix = self._compute_cost(detections, timestamp)

        # 4) solve assignment
        if cost_matrix.size > 0:
            rows, cols = linear_sum_assignment(cost_matrix)
        else:
            rows, cols = np.array([]), np.array([])

        assigned_tracks     = set()
        assigned_detections = set()

        # 5) update matched tracks
        for row, col in zip(rows, cols):
            if cost_matrix[row, col] > self.max_distance:
                continue
            self.tracks[row].update(
                detections[col][1],
                detections[col][0],
                feature=detections[col][2],
                timestamp=timestamp
            )
            assigned_tracks.add(row)
            assigned_detections.add(col)

        # 6) age unmatched tracks
        for i, track in enumerate(self.tracks):
            if i not in assigned_tracks:
                track.time_since_update += 1

        # 7) purge expired
        self.tracks = [
            t for t in self.tracks
            if t.time_since_update <= self.max_disappeared
        ]

        # 8) create new tracks for unmatched detections
        for j in range(len(detections)):
            if j not in assigned_detections:
                new_t = Track(
                    self.next_track_id,
                    detections[j][1],
                    detections[j][0],
                    feature=detections[j][2]
                )
                # seed its timestamp for future dt computation
                new_t.last_timestamp = timestamp
                self.tracks.append(new_t)
                self.next_track_id += 1

        # 9) return the updated track map
        return {t.track_id: (t.centroid, t.bbox) for t in self.tracks}
