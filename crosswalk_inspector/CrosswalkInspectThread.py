# CrosswalkInspectThread.py

import time
import cv2
import numpy as np
from datetime import datetime
import os
from PyQt5 import QtCore
from concurrent.futures import ThreadPoolExecutor

from crosswalk_inspector.objects.DetectedObject import DetectedObject
from crosswalk_inspector.objects.TrafficLight import TrafficLight
from utils.region.RegionManager import RegionManager
from crosswalk_inspector.GlobalState import GlobalState

class Region:
    def __init__(self, polygon):
        valid = isinstance(polygon, (list, tuple)) and len(polygon) >= 3
        self.contour = np.array(polygon, dtype=np.int32) if valid else None

    def contains(self, point):
        if self.contour is None:
            return False
        return cv2.pointPolygonTest(self.contour, tuple(point), False) >= 0

class EntityState:
    def __init__(self, track_id, class_name):
        self.track_id = track_id
        self.class_name = class_name
        self._entries = {}
        self.durations = {}

    def update_region(self, name, inside, now):
        was_inside = name in self._entries and name not in self.durations
        if inside and not was_inside:
            self._entries[name] = now
        elif not inside and was_inside:
            entry = self._entries.pop(name)
            self.durations[name] = (now - entry).total_seconds()

class CrosswalkPackMonitor:
    def __init__(self, pack_id, crosswalk_poly, pedes_wait_list, car_wait_list):
        self.pack_id = pack_id
        self.crosswalk = Region(crosswalk_poly)
        self.ped_wait_regions = [Region(p['points']) for p in pedes_wait_list]
        self.car_wait_regions = [Region(p['points']) for p in car_wait_list]
        self.entities = {}

    def process_frame(self, detections, now, tl_objects=None):
        """
        detections: list of DetectedObject
        now: datetime
        tl_objects: optional List[TrafficLight] for gating logic
        """
        for det in detections:
            tid = det.id
            cls = DetectedObject.CLASS_NAMES.get(det.object_type, "unknown")
            if tid not in self.entities:
                self.entities[tid] = EntityState(tid, cls)
            st = self.entities[tid]
            pt = det.foot_coordinate or det.centroid_coordinate
            if pt is None:
                continue

            # you can now check tl_objects state here if needed:
            # e.g. only update crosswalk duration when all tl.state == 'green'
            # if tl_objects and any(tl.pack_id == self.pack_id and tl.state!='green' for tl in tl_objects):
            #     continue

            for i, reg in enumerate(self.ped_wait_regions):
                st.update_region(f"ped_wait_{i}", reg.contains(pt), now)
            st.update_region("crosswalk", self.crosswalk.contains(pt), now)
            for i, reg in enumerate(self.car_wait_regions):
                st.update_region(f"car_wait_{i}", reg.contains(pt), now)

class CrosswalkInspectThread(QtCore.QThread):
    inspection_ready = QtCore.pyqtSignal(list, float)
    error_signal     = QtCore.pyqtSignal(str)

    def __init__(self,
                 editor: RegionManager,
                 global_state: GlobalState,
                 tl_objects: list[TrafficLight],
                 inverse_homography: np.ndarray = None,
                 check_period: float = 0.2,
                 parent=None):

        super().__init__(parent)

        self.editor      = editor
        self.state       = global_state
        self.H_inv       = inverse_homography
        self.check_period= check_period
        self._last_check = 0.0
        self._running    = True

        # **use the passed-in traffic-light objects**; do NOT recreate or re-inspect them
        self.tl_objects = tl_objects  # list[TrafficLight]

        # build crosswalk monitors as before
        self.monitors = {
            pack.id: CrosswalkPackMonitor(
                pack.id,
                pack.crosswalk['points'],
                pack.pedes_wait,
                pack.car_wait
            )
            for pack in editor.crosswalk_packs
        }

    def run(self):
        try:
            while self._running:
                objects, ts = self.state.get()
                if not objects:
                    time.sleep(0.01)
                    continue

                now_wall = time.time()
                now_ts   = datetime.fromtimestamp(ts)

                # coordinate transform if needed
                if now_wall - self._last_check >= self.check_period:
                    self._last_check = now_wall
                    for det in objects:
                        if self.H_inv is not None and det.centroid_coordinate:
                            x,y = det.centroid_coordinate
                            vx,vy,w = self.H_inv.dot([x, y, 1])
                            det.centroid_coordinate = (vx/w, vy/w)
                            if det.foot_coordinate:
                                x2,y2 = det.foot_coordinate
                                vx2,vy2,w2 = self.H_inv.dot([x2, y2, 1])
                                det.foot_coordinate = (vx2/w2, vy2/w2)
                    # process each pack — now passing tl_objects so you can gate on light state
                    for monitor in self.monitors.values():
                        monitor.process_frame(objects, now_ts, tl_objects=self.tl_objects)

                # emit detection→inspection ready (unchanged)
                self.inspection_ready.emit(objects, ts)

        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._running = False
        self.quit()
        self.wait()
