# CrosswalkInspectThread.py

import time
import cv2
import numpy as np
from datetime import datetime
import os
from concurrent.futures import ThreadPoolExecutor
from PyQt5 import QtCore

from crosswalk_inspector.objects.DetectedObject import DetectedObject
from crosswalk_inspector.objects.TrafficLight import TrafficLight
from utils.region.RegionManager import RegionManager
from crosswalk_inspector.GlobalState import GlobalState

class Region:
    def __init__(self, polygon):
        valid = isinstance(polygon, (list, tuple)) and len(polygon) >= 3
        if valid:
            self.contour = np.array(polygon, dtype=np.int32)
        else:
            self.contour = None

    def contains(self, point):
        if self.contour is None:
            return False
        try:
            return cv2.pointPolygonTest(self.contour, tuple(point), False) >= 0
        except:
            return False

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

    def process_frame(self, detections, now):
        for det in detections:
            tid = det.id
            cls = DetectedObject.CLASS_NAMES.get(det.object_type, "unknown")
            if tid not in self.entities:
                self.entities[tid] = EntityState(tid, cls)
            st = self.entities[tid]
            pt = det.foot_coordinate or det.centroid_coordinate
            if pt is None:
                continue

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
                 analyze_fn,
                 inverse_homography: np.ndarray = None,
                 check_period: float = 0.2,
                 parent=None,
                 max_workers=None):
        super().__init__(parent)
        self.editor = editor
        self.state = global_state
        self.analyze_fn = analyze_fn
        self.H_inv = inverse_homography
        self.check_period = check_period
        self._last_check = 0.0
        self._running = True
        self.max_workers = max_workers or (os.cpu_count() or 4)

        # build TrafficLight objects
        self.tl_objects = []
        for pack in editor.crosswalk_packs:
            groups = {}
            for c in pack.traffic_light:
                gid = c['id']
                groups.setdefault(gid, {
                    'type': c.get('light_type'),
                    'lights': {}
                })['lights'][c['signal_color']] = {
                    'center': c['center'],
                    'radius': c['radius']
                }
            for gid, cfg in groups.items():
                self.tl_objects.append(
                    TrafficLight(pack.id, gid, cfg['type'], cfg['lights'])
                )

        # build monitors
        self.monitors = {}
        for pack in editor.crosswalk_packs:
            self.monitors[pack.id] = CrosswalkPackMonitor(
                pack.id,
                pack.crosswalk['points'],
                pack.pedes_wait,
                pack.car_wait
            )

    def run(self):
        try:
            with ThreadPoolExecutor(self.max_workers) as execr:
                while self._running:
                    objects, ts = self.state.get()
                    if not objects:
                        time.sleep(0.01)
                        continue

                    now_wall = time.time()
                    now_ts   = datetime.fromtimestamp(ts)

                    if now_wall - self._last_check >= self.check_period:
                        self._last_check = now_wall
                        for det in objects:
                            if self.H_inv is not None and det.centroid_coordinate:
                                x, y = det.centroid_coordinate
                                vx, vy, w = self.H_inv.dot([x, y, 1])
                                det.centroid_coordinate = (vx / w, vy / w)
                                if det.foot_coordinate:
                                    x2, y2 = det.foot_coordinate
                                    vx2, vy2, w2 = self.H_inv.dot([x2, y2, 1])
                                    det.foot_coordinate = (vx2 / w2, vy2 / w2)
                        for m in self.monitors.values():
                            m.process_frame(objects, now_ts)

                    futures = [execr.submit(self._proc_tl, tl) for tl in self.tl_objects]
                    for f in futures:
                        try:
                            f.result()
                        except Exception:
                            pass

                    self.inspection_ready.emit(objects, ts)
        except Exception as e:
            self.error_signal.emit(str(e))

    def _proc_tl(self, tl: TrafficLight):
        frame = self.state.last_frame
        if frame is None:
            return
        tl.crop_regions(frame)
        tl.update_status(self.analyze_fn)

    def stop(self):
        self._running = False
        self.quit()
        self.wait()
