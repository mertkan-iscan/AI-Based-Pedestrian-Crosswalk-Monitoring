import time
from datetime import datetime

import cv2
import numpy as np
from PyQt5 import QtCore

from crosswalk_inspector.objects.DetectedObject import DetectedObject
from crosswalk_inspector.objects.TrafficLight import TrafficLight
from utils.region.RegionManager import RegionManager
from crosswalk_inspector.GlobalState import GlobalState


class Region:
    def __init__(self, polygon, homography_inv=None):
        valid = isinstance(polygon, (list, tuple)) and len(polygon) >= 3
        if valid:
            arr = np.array(polygon, dtype=np.int32)
            if arr.ndim == 2 and arr.shape[1] == 2:
                arr = arr.reshape(-1, 1, 2)
            self.contour = arr
            x, y, w, h = cv2.boundingRect(self.contour)
            self.bbox = (x, y, x + w, y + h)
        else:
            self.contour = None
            self.bbox = None
        self.H_inv = homography_inv

    def contains(self, pt_world):
        if self.contour is None:
            return False
        if self.H_inv is not None:
            vec = np.array([pt_world[0], pt_world[1], 1.0], dtype=float)
            dst = self.H_inv @ vec
            px, py = dst[0] / dst[2], dst[1] / dst[2]
        else:
            px, py = pt_world
        x, y = int(px), int(py)
        x0, y0, x1, y1 = self.bbox
        if x < x0 or x > x1 or y < y0 or y > y1:
            return False
        return cv2.pointPolygonTest(self.contour, (x, y), False) >= 0


class EntityState:
    def __init__(self, track_id, class_name):
        self.track_id = track_id
        self.class_name = class_name
        self._entries = {}
        self.durations = {}

    def update_region(self, name, inside, now):
        if inside and name not in self._entries:
            self._entries[name] = now
        elif not inside and name in self._entries:
            entry = self._entries.pop(name)
            self.durations[name] = (now - entry).total_seconds()


class CrosswalkPackMonitor:
    def __init__(
        self,
        pack_id,
        crosswalk_poly,
        pedes_wait_list,
        car_wait_list,
        homography_inv=None
    ):
        self.pack_id = pack_id
        self.crosswalk = Region(crosswalk_poly, homography_inv)
        self.ped_wait_regions = [Region(p['points'], homography_inv) for p in pedes_wait_list]
        self.car_wait_regions = [Region(p['points'], homography_inv) for p in car_wait_list]
        self.entities = {}

    def process_frame(self, detections, now, tl_objects=None):
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
    error_signal = QtCore.pyqtSignal(str)

    def __init__(
        self,
        editor: RegionManager,
        global_state: GlobalState,
        tl_objects: list[TrafficLight],
        check_period: float,
        homography_inv=None,
        parent=None
    ):
        super().__init__(parent)
        self.editor = editor
        self.state = global_state
        self.tl_objects = tl_objects
        self.check_period = check_period
        self._last_check = 0.0
        self._running = True
        self.H_inv = homography_inv
        self._last_tl_status = {tl.id: None for tl in tl_objects}
        self.monitors = {
            pack.id: CrosswalkPackMonitor(
                pack.id,
                pack.crosswalk["points"],
                pack.pedes_wait,
                pack.car_wait,
                homography_inv
            )
            for pack in editor.crosswalk_packs
        }

    def run(self):
        try:
            while self._running:
                now = time.time()
                if now - self._last_check < self.check_period:
                    time.sleep(0.005)
                    continue
                self._last_check = now

                objects, ts = self.state.get()
                if not objects:
                    continue

                now_ts = datetime.fromtimestamp(ts)
                timestr = now_ts.strftime("%H:%M:%S.%f")[:-3]

                lines = []

                # Log only if traffic light status changed
                tl_changed = False
                for tl in self.tl_objects:
                    last = self._last_tl_status.get(tl.id)
                    if tl.status != last:
                        tl_changed = True
                        break
                if tl_changed:
                    lines.append(f"[{timestr}] Traffic Light Statuses:")
                    for tl in self.tl_objects:
                        status = tl.status
                        lines.append(f"  Pack:{tl.pack_id} Light:{tl.id} Status:{status}")
                        self._last_tl_status[tl.id] = status

                # Crosswalk pack region counts
                for pack_id, mon in self.monitors.items():
                    crosswalk_count = sum(
                        1
                        for det in objects
                        if mon.crosswalk.contains(det.foot_coordinate or det.centroid_coordinate)
                    )
                    ped_counts = {
                        f"ped_wait_{i}": sum(
                            1
                            for det in objects
                            if reg.contains(det.foot_coordinate or det.centroid_coordinate)
                        )
                        for i, reg in enumerate(mon.ped_wait_regions)
                    }
                    car_counts = {
                        f"car_wait_{i}": sum(
                            1
                            for det in objects
                            if reg.contains(det.foot_coordinate or det.centroid_coordinate)
                        )
                        for i, reg in enumerate(mon.car_wait_regions)
                    }
                    region_counts = {"crosswalk": crosswalk_count, **ped_counts, **car_counts}
                    lines.append(f"[{timestr}] Pack:{pack_id} Region Counts: {region_counts}")

                if lines:
                    print("\n".join(lines), flush=True)

                self.inspection_ready.emit(objects, ts)

        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._running = False
        self.quit()
        self.wait()
