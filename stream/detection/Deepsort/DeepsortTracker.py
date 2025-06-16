from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment
from concurrent.futures import ThreadPoolExecutor

from stream.detection.Deepsort.CNNFeatureExtractor import CNNFeatureExtractor
from stream.detection.Deepsort.Track import Track

PERSON_CLASS_IDX = 0
VEHICLE_CLASSES = [1,2,3,5,7]

class DeepSortTracker:
    def __init__(
        self,
        max_disappeared: int,
        max_distance: float,
        device: str,
        appearance_weight: float,
        motion_weight: float,
        iou_weight: float,
        nn_budget: int,
        homography_matrix,
        person_reid_path: str,
        vehicle_reid_path: str,
    ):

        self.next_track_id = 0
        self.tracks: list[Track] = []
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.appearance_weight = appearance_weight
        self.motion_weight = motion_weight
        self.iou_weight = iou_weight
        self.homography_matrix = homography_matrix
        self.nn_budget = nn_budget

        self.person_extractor = CNNFeatureExtractor(device=device, checkpoint_path=person_reid_path)
        self.vehicle_extractor = CNNFeatureExtractor(device=device, checkpoint_path=vehicle_reid_path)

        self.executor = ThreadPoolExecutor(max_workers=1)

    def calibrate_point(self, point, homography_matrix):
        pt = np.array([point[0], point[1], 1.0], dtype=np.float32)
        transformed = homography_matrix @ pt

        if transformed[2] != 0:
            return transformed[0] / transformed[2], transformed[1] / transformed[2]
        else:
            return transformed[0], transformed[1]

    def _iou(self, bbox1, bbox2):
        xA = max(bbox1[0], bbox2[0])
        yA = max(bbox1[1], bbox2[1])
        xB = min(bbox1[2], bbox2[2])
        yB = min(bbox1[3], bbox2[3])

        interArea = max(0, xB - xA + 1) * max(0, yB - yA + 1)
        boxAArea = (bbox1[2] - bbox1[0] + 1) * (bbox1[3] - bbox1[1] + 1)
        boxBArea = (bbox2[2] - bbox2[0] + 1) * (bbox2[3] - bbox2[1] + 1)
        unionArea = float(boxAArea + boxBArea - interArea)
        if unionArea == 0:
            return 0.0
        return interArea / unionArea

    def _compute_cost(self, detections, timestamp: float, detection_fps: float):
        n_tracks = len(self.tracks)
        n_dets = len(detections)
        if n_tracks == 0:
            empty = np.empty((0, n_dets), dtype=float)
            return empty, empty, empty

        cost_matrix = np.zeros((n_tracks, n_dets), dtype=float)
        motion_matrix = np.zeros_like(cost_matrix)
        appearance_matrix = np.zeros_like(cost_matrix)
        iou_matrix = np.zeros_like(cost_matrix)

        for i, track in enumerate(self.tracks):
            track_cls = track.bbox[4] if len(track.bbox) > 4 else PERSON_CLASS_IDX
            pred_centroid = track.predict_with_dt(detection_fps, timestamp)
            gallery = track.get_gallery()
            if gallery:
                gallery_arr = np.stack(gallery, axis=0)
                gallery_norms = np.linalg.norm(gallery_arr, axis=1) + 1e-6
            else:
                gallery_arr = None

            for j, (det_centroid, det_bbox, det_feat) in enumerate(detections):
                det_cls = det_bbox[4] if len(det_bbox) > 4 else PERSON_CLASS_IDX
                if det_cls != track_cls:
                    cost_matrix[i, j] = 1e6
                    motion_matrix[i, j] = 1e6
                    appearance_matrix[i, j] = 1e6
                    iou_matrix[i, j] = 0.0
                    continue

                m_dist = np.linalg.norm(np.asarray(pred_centroid) - np.asarray(det_centroid))
                motion_matrix[i, j] = m_dist

                if det_feat is not None and gallery_arr is not None:
                    sims = gallery_arr @ det_feat / (gallery_norms * (np.linalg.norm(det_feat) + 1e-6))
                    a_dist = 1.0 - float(np.max(sims))
                else:
                    a_dist = 1.0
                appearance_matrix[i, j] = a_dist

                iou_score = self._iou(track.bbox, det_bbox)
                iou_matrix[i, j] = iou_score

                cost_matrix[i, j] = (
                    self.motion_weight * m_dist
                    + self.appearance_weight * a_dist
                    + self.iou_weight * (1.0 - iou_score)
                )

        return cost_matrix, motion_matrix, appearance_matrix

    def remove_tracks(self, track_ids):
        removed = [t.track_id for t in self.tracks if t.track_id in track_ids]
        if removed:
            print(f"Removing tracks: {removed}")
        self.tracks = [t for t in self.tracks if t.track_id not in track_ids]

    def update(
            self,
            rects,
            frame=None,
            features=None,
            timestamp: float | None = None,
            detection_fps=None,
    ):

        if len(rects) == 0:
            for track in self.tracks:
                track.time_since_update += 1
            removed_ids = [
                t.track_id for t in self.tracks
                if t.time_since_update > self.max_disappeared
            ]
            self.tracks = [
                t for t in self.tracks
                if t.time_since_update <= self.max_disappeared
            ]
            return {t.track_id: (t.centroid, t.bbox) for t in self.tracks}, removed_ids

        # Build detection list: each entry is (calibrated_point, bbox_with_conf, feature)
        detections = []
        if features is None and frame is not None:
            bboxes_person = []
            indices_person = []
            bboxes_vehicle = []
            indices_vehicle = []
            points = []

            for idx, rect in enumerate(rects):
                if len(rect) == 6:
                    x1, y1, x2, y2, cls, conf = rect
                else:
                    x1, y1, x2, y2, cls = rect
                    conf = None

                if self.homography_matrix is not None:
                    spx = int((x1 + x2) / 2.0)
                    spy = int(y2)
                    calibrated = self.calibrate_point((spx, spy), self.homography_matrix)
                else:
                    cX = int((x1 + x2) / 2.0)
                    cY = int((y1 + y2) / 2.0)
                    calibrated = (cX, cY)
                points.append(calibrated)

                if cls == PERSON_CLASS_IDX:
                    bboxes_person.append((x1, y1, x2, y2))
                    indices_person.append(idx)
                elif cls in VEHICLE_CLASSES:
                    bboxes_vehicle.append((x1, y1, x2, y2))
                    indices_vehicle.append(idx)
                else:
                    bboxes_person.append((x1, y1, x2, y2))
                    indices_person.append(idx)

            batch_features = [None] * len(rects)
            if bboxes_person:
                feats_person = self.person_extractor.extract_features_batch(frame, bboxes_person)
                for i, idx in enumerate(indices_person):
                    batch_features[idx] = feats_person[i]
            if bboxes_vehicle:
                feats_vehicle = self.vehicle_extractor.extract_features_batch(frame, bboxes_vehicle)
                for i, idx in enumerate(indices_vehicle):
                    batch_features[idx] = feats_vehicle[i]

            for i, rect in enumerate(rects):
                if len(rect) == 6:
                    x1, y1, x2, y2, cls, conf = rect
                else:
                    x1, y1, x2, y2, cls = rect
                    conf = None
                detections.append((
                    points[i],
                    (x1, y1, x2, y2, cls, conf),
                    batch_features[i]
                ))

        cost_matrix, motion_matrix, appearance_matrix = self._compute_cost(
            detections, timestamp, detection_fps=detection_fps
        )
        if cost_matrix.size > 0:
            rows, cols = linear_sum_assignment(cost_matrix)
        else:
            rows, cols = np.array([], dtype=int), np.array([], dtype=int)

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

        removed_ids = [
            t.track_id for t in self.tracks
            if t.time_since_update > self.max_disappeared
        ]
        self.tracks = [
            t for t in self.tracks
            if t.time_since_update <= self.max_disappeared
        ]

        for j, (cent, bbox, feat) in enumerate(detections):
            if j not in assigned_dets:
                new_track = Track(
                    self.next_track_id,
                    bbox,
                    cent,
                    feature=feat,
                    nn_budget=self.nn_budget,
                )
                new_track.last_timestamp = timestamp
                self.tracks.append(new_track)
                self.next_track_id += 1

        return {t.track_id: (t.centroid, t.bbox) for t in self.tracks}, removed_ids
