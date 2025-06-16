import queue
import time
import threading
import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from stream.detection.DetectedObject import DetectedObject
from stream.detection.YoloDetector import YoloDetector
from stream.detection.Deepsort.DeepsortTracker import DeepSortTracker
from utils.RegionManager import RegionManager
from utils.GlobalState import GlobalState
from utils.ConfigManager import ConfigManager
from utils.benchmark.MetricSignals import signals


def lines_intersect(a1, a2, b1, b2):
    def ccw(A, B, C):
        return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])
    return (ccw(a1, b1, b2) != ccw(a2, b1, b2)) and (ccw(a1, a2, b1) != ccw(a1, a2, b2))

def point_to_segment_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5

class DetectionThread(QThread):

    detections_ready = pyqtSignal(list, float)
    error_signal = pyqtSignal(str)

    def __init__(
        self,
        polygons_file: str,
        detection_queue: "queue.Queue",
        state: GlobalState,
        detection_fps,
        delay,
        mot_writer,
        location,
        homography_matrix=None,
        parent=None,
    ):

        super().__init__(parent)

        yolo_cfg = ConfigManager(location=location).get_yolo_config()
        self.detector = YoloDetector(yolo_config=yolo_cfg)

        self.detection_fps = detection_fps
        self.queue = detection_queue
        self.delay = float(delay)
        self._run = True

        self.state = state
        self.editor = RegionManager(polygons_file)
        self.editor.load_polygons()

        self._timers = set()

        self.mot_writer = mot_writer
        self.frame_counter = 1
        self._mot_lines_buffer = []

        self._blackout_mask = None

        self.location = location
        cfg = ConfigManager(location=self.location).get_deepsort_config()
        self.tracker = DeepSortTracker(
            max_disappeared   = cfg.get("max_disappeared"),
            max_distance      = cfg.get("max_distance"),
            device            = cfg.get("device"),
            appearance_weight = cfg.get("appearance_weight"),
            motion_weight     = cfg.get("motion_weight"),
            iou_weight        = cfg.get("iou_weight"),
            nn_budget         = cfg.get("nn_budget"),
            homography_matrix = homography_matrix,
            person_reid_path  = "PPLR+CAJ_market1501_86.1.pth",
            vehicle_reid_path  = "PPLR+CAJ_veri_45.3.pth",
        )

        self.H_inv = None
        if homography_matrix is not None:
            try:
                self.H_inv = np.linalg.inv(np.asarray(homography_matrix, dtype=np.float32))
            except np.linalg.LinAlgError:
                self.H_inv = None

    def _compute_static_mask(self, frame_shape):
        # Create a single channel mask (uint8), initially all white (keep all)
        mask = np.ones(frame_shape[:2], dtype=np.uint8) * 255
        for poly in self.editor.other_regions.get("detection_blackout", []):
            pts = np.array(poly["points"], dtype=np.int32)
            cv2.fillPoly(mask, [pts], 0)
        return mask

    def _mask_blackout(self, frame):
        masked = frame.copy()
        for poly in self.editor.other_regions.get("detection_blackout", []):
            pts = np.array(poly["points"], dtype=np.int32)
            cv2.fillPoly(masked, [pts], (0, 0, 0))
        return masked

    def _bev_to_cam(self, pt):
        if self.H_inv is None:
            return pt
        vec = np.array([[pt[0], pt[1], 1]], dtype=np.float32).T
        res = self.H_inv @ vec
        res /= res[2, 0]
        return float(res[0, 0]), float(res[1, 0])

    def _bbox_hits_deletion_line(self, bbox, threshold=6.0):
        x1, y1, x2, y2 = bbox[:4]
        bbox_edges = [
            ((x1, y1), (x2, y1)),
            ((x2, y1), (x2, y2)),
            ((x2, y2), (x1, y2)),
            ((x1, y2), (x1, y1)),
        ]

        def sample_edge(p1, p2, n=5):
            return [(p1[0] + (p2[0] - p1[0]) * i / (n - 1), p1[1] + (p2[1] - p1[1]) * i / (n - 1)) for i in range(n)]

        for rtype in ("deletion_line", "pedestrian_deletion_line"):
            for line in self.editor.other_regions.get(rtype, []):
                pts = line["points"]
                if len(pts) >= 2:
                    for i in range(len(pts) - 1):
                        lx1, ly1 = pts[i]
                        lx2, ly2 = pts[i + 1]
                        for (b1, b2) in bbox_edges:
                            if lines_intersect((lx1, ly1), (lx2, ly2), b1, b2):
                                return True
                            for (px, py) in sample_edge(b1, b2, n=5):
                                dist = point_to_segment_dist(px, py, lx1, ly1, lx2, ly2)
                                if dist <= threshold:
                                    return True
        return False

    def run(self):
        while self._run:
            try:
                frame, capture_time, display_time = self.queue.get(timeout=0.05)
            except queue.Empty:
                continue

            t_dequeue = time.time()
            signals.queue_wait_logged.emit(t_dequeue - capture_time)

            masked = self._mask_blackout(frame)

            t_inf_start = time.time()
            detections = self.detector.run(masked)
            t_inf_end = time.time()
            signals.detection_logged.emit(t_inf_end - t_inf_start)

            t_post_start = time.time()
            tracks_map, removed_ids= self.tracker.update(
                detections,
                frame=masked,
                timestamp=capture_time,
                detection_fps=self.detection_fps
            )

            if self.mot_writer is not None:
                self.mot_writer.submit(self.frame_counter, tracks_map)
            self.frame_counter += 1

            ids_to_remove = []
            objects_to_emit = []
            for tid, (surface_point, bbox) in tracks_map.items():

                x1, y1, x2, y2, cls_idx, conf = bbox[:6]
                obj_type = DetectedObject.CLASS_NAMES.get(cls_idx, "unknown")

                obj = DetectedObject(
                    tid,
                    obj_type,
                    (int(x1), int(y1), int(x2), int(y2)),
                    surface_point
                )

                obj.confidence = float(conf)

                for t in self.tracker.tracks:
                    if t.track_id == tid:
                        obj.motion_distance = getattr(t, "motion_distance", None)
                        obj.appearance_distance = getattr(t, "appearance_distance", None)
                        break
                objects_to_emit.append(obj)

            all_to_remove = list(set(ids_to_remove) | set(removed_ids))
            if all_to_remove:
                self.tracker.remove_tracks(all_to_remove)

            signals.postproc_logged.emit(time.time() - t_post_start)

            emit_at = display_time + self.delay
            wait = emit_at - time.time()

            schedule_delay = emit_at - time.time()
            signals.scheduling_logged.emit(schedule_delay)

            timer = threading.Timer(
                max(0.0, wait),
                lambda objs=objects_to_emit, rm=all_to_remove, cap=capture_time:
                self._emit_detections_with_deletion(objs, rm, cap)
            )

            timer.daemon = True
            timer.start()

    def _emit_detections(self, detected_objects, capture_time):
        self.state.update(detected_objects, time.time())
        self.detections_ready.emit(detected_objects, capture_time)

    def _emit_detections_with_deletion(self, objects, ids_to_remove, capture_time):
        if ids_to_remove:
            self.state.remove(ids_to_remove)
        if objects:
            self.state.update(objects, time.time())
        self.detections_ready.emit(objects, capture_time)

    def stop(self):
        self._run = False
        for timer in getattr(self, "_timers", []):
            timer.cancel()
        self._timers.clear()
        self.quit()
        self.wait()
