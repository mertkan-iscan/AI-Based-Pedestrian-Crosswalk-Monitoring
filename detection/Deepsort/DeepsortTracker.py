# DeepsortTracker.py
from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment
from concurrent.futures import ThreadPoolExecutor
from detection.Deepsort.CNNFeatureExtractor import CNNFeatureExtractor
from detection.Deepsort.Track import Track


class DeepSortTracker:
    def __init__(
        self,
        max_disappeared: int = 50,
        max_distance: float = 0.9,
        device: str = "cuda",
        appearance_weight: float = 0.5,
        motion_weight: float = 0.5,
        nn_budget: int = 50,
        homography_matrix=None,
    ):
        self.next_track_id = 0
        self.tracks: list[Track] = []
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.appearance_weight = appearance_weight
        self.motion_weight = motion_weight
        self.homography_matrix = homography_matrix
        self.nn_budget = nn_budget
        self.feature_extractor = CNNFeatureExtractor(device=device)
        self.executor = ThreadPoolExecutor(max_workers=1)

    @staticmethod
    def calibrate_point(point, homography_matrix):
        pt = np.array([point[0], point[1], 1.0], dtype=np.float32)
        transformed = homography_matrix @ pt
        if transformed[2] != 0.0:
            return transformed[0] / transformed[2], transformed[1] / transformed[2]
        return transformed[0], transformed[1]

    def _compute_cost(self, detections, timestamp: float):
        n_tracks = len(self.tracks)
        n_dets = len(detections)
        if n_tracks == 0:
            empty = np.empty((0, n_dets), dtype=float)
            return empty, empty, empty

        diag_norm = 848.528
        cost_matrix = np.zeros((n_tracks, n_dets), dtype=float)
        motion_matrix = np.zeros_like(cost_matrix)
        appearance_matrix = np.zeros_like(cost_matrix)

        for i, track in enumerate(self.tracks):
            pred_centroid = track.predict_with_dt(timestamp)
            gallery = track.get_gallery()
            if gallery:
                gallery_arr = np.stack(gallery, axis=0)
                gallery_norms = np.linalg.norm(gallery_arr, axis=1) + 1e-6
            else:
                gallery_arr = None

            for j, (det_centroid, _, det_feat) in enumerate(detections):
                m_dist = (
                    np.linalg.norm(np.asarray(pred_centroid) - np.asarray(det_centroid))
                    / diag_norm
                )
                motion_matrix[i, j] = m_dist

                if det_feat is not None and gallery_arr is not None:
                    sims = gallery_arr @ det_feat / (gallery_norms * (np.linalg.norm(det_feat) + 1e-6))
                    a_dist = 1.0 - float(np.max(sims))
                else:
                    a_dist = 1.0
                appearance_matrix[i, j] = a_dist

                cost_matrix[i, j] = self.motion_weight * m_dist + self.appearance_weight * a_dist

        return cost_matrix, motion_matrix, appearance_matrix

    def update(
        self,
        rects,
        frame=None,
        features=None,
        timestamp: float | None = None,
    ):
        if len(rects) == 0:
            for track in self.tracks:
                track.time_since_update += 1
            self.tracks = [t for t in self.tracks if t.time_since_update <= self.max_disappeared]
            return {t.track_id: (t.centroid, t.bbox) for t in self.tracks}

        detections = []
        if features is None and frame is not None:
            bboxes, cents = [], []
            for rect in rects:
                if len(rect) == 6:
                    x1, y1, x2, y2, cls, _ = rect
                else:
                    x1, y1, x2, y2, cls = rect
                cX, cY = int((x1 + x2) / 2.0), int((y1 + y2) / 2.0)
                pixel_centroid = (cX, cY)
                if self.homography_matrix is not None:
                    calibrated = self.calibrate_point(pixel_centroid, self.homography_matrix)
                else:
                    calibrated = pixel_centroid
                cents.append(calibrated)
                bboxes.append((x1, y1, x2, y2))

            future = self.executor.submit(
                self.feature_extractor.extract_features_batch, frame, bboxes
            )
            batch_features = future.result()

            for i, rect in enumerate(rects):
                if len(rect) == 6:
                    x1, y1, x2, y2, cls, _ = rect
                else:
                    x1, y1, x2, y2, cls = rect
                detections.append((cents[i], (x1, y1, x2, y2, cls), batch_features[i]))
        else:
            for i, rect in enumerate(rects):
                if len(rect) == 6:
                    x1, y1, x2, y2, cls, _ = rect
                else:
                    x1, y1, x2, y2, cls = rect
                cX, cY = int((x1 + x2) / 2.0), int((y1 + y2) / 2.0)
                pixel_centroid = (cX, cY)
                if self.homography_matrix is not None:
                    calibrated = self.calibrate_point(pixel_centroid, self.homography_matrix)
                else:
                    calibrated = pixel_centroid
                if features is not None:
                    det_feature = features[i]
                else:
                    det_feature = self.feature_extractor.extract_features([frame[y1:y2, x1:x2]])[0]
                detections.append((calibrated, (x1, y1, x2, y2, cls), det_feature))

        cost_matrix, motion_matrix, appearance_matrix = self._compute_cost(detections, timestamp)

        if cost_matrix.size > 0:
            rows, cols = linear_sum_assignment(cost_matrix)
        else:
            rows, cols = np.array([]), np.array([])

        assigned_tracks, assigned_dets = set(), set()
        for row, col in zip(rows, cols):
            if cost_matrix[row, col] > self.max_distance:
                continue
            track = self.tracks[row]
            track.motion_distance = motion_matrix[row, col]
            track.appearance_distance = appearance_matrix[row, col]
            track.update(
                detections[col][1],
                detections[col][0],
                feature=detections[col][2],
                timestamp=timestamp,
            )
            assigned_tracks.add(row)
            assigned_dets.add(col)

        for i, track in enumerate(self.tracks):
            if i not in assigned_tracks:
                track.time_since_update += 1

        self.tracks = [t for t in self.tracks if t.time_since_update <= self.max_disappeared]

        for j in range(len(detections)):
            if j not in assigned_dets:
                new_track = Track(
                    self.next_track_id,
                    detections[j][1],
                    detections[j][0],
                    feature=detections[j][2],
                    nn_budget=self.nn_budget,
                )
                new_track.last_timestamp = timestamp
                self.tracks.append(new_track)
                self.next_track_id += 1

        return {t.track_id: (t.centroid, t.bbox) for t in self.tracks}
