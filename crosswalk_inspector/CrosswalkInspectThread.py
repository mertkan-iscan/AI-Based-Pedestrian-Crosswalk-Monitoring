import time
from datetime import datetime

import cv2
import numpy as np
from PyQt5 import QtCore

from crosswalk_inspector.objects.DetectedObject import DetectedObject
from crosswalk_inspector.objects.TrafficLight import TrafficLight
from utils.RegionManager import RegionManager
from utils.GlobalState import GlobalState


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
        self.current_regions = set()
        self._entries = {}
        self.durations = {}

    def update_region(self, name, inside, now):
        if inside and name not in self._entries:
            self._entries[name] = now
        elif not inside and name in self._entries:
            entry = self._entries.pop(name)
            self.durations[name] = (now - entry).total_seconds()
        if inside:
            self.current_regions.add(name)
        else:
            self.current_regions.discard(name)


class CrosswalkPackMonitor:
    def __init__(self, pack_id, crosswalk_poly, pedes_wait_list, car_wait_list, homography_inv=None):
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
            pt = det.surface_point or det.raw_surface_point
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

    # thresholds
    T_PED_WAIT = 2.0

    def __init__(self,
                 editor: RegionManager,
                 global_state: GlobalState,
                 tl_objects: list[TrafficLight],
                 check_period: float,
                 homography_inv=None, parent=None
    ):

        super().__init__(parent)

        print("Loading Crosswalk Packs:")
        for pack in editor.crosswalk_packs:
            print(f"  Pack ID: {pack.id}")
            print(f"    Crosswalk points: {pack.crosswalk['points']}")
            print(f"    Ped_wait regions: {[p['points'] for p in pack.pedes_wait]}")
            print(f"    Car_wait regions: {[p['points'] for p in pack.car_wait]}")

        print("Loading Traffic Light Objects:")
        for tl in tl_objects:
            colors = list(tl.lights.keys())
            print(f"  TL ID: {tl.id}, Pack ID: {tl.pack_id}, Colors: {colors}, Initial status: {tl.status}")

        self.editor      = editor
        self.state       = global_state
        self.tl_objects  = tl_objects
        self.check_period = check_period
        self._last_check = 0.0
        self._running    = True
        self.H_inv       = homography_inv

        self.packs = {pack.id: pack for pack in editor.crosswalk_packs}
        self._last_tl_status = {tl.id: None for tl in tl_objects}
        self.monitors = {
            pack.id: CrosswalkPackMonitor(
                pack.id,
                pack.crosswalk["points"],
                pack.pedes_wait,
                pack.car_wait,
                homography_inv
            ) for pack in editor.crosswalk_packs
        }

    def get_effective_traffic_light_status(self, pack_id, tl_objects, light_type):
        vehicle_tl = None
        pedestrian_tl = None
        for tl in tl_objects:
            if tl.pack_id != pack_id:
                continue
            if tl.type == 'vehicle':
                vehicle_tl = tl
            elif tl.type == 'pedestrian':
                pedestrian_tl = tl

        vehicle_status = vehicle_tl.status if vehicle_tl else None
        pedestrian_status = pedestrian_tl.status if pedestrian_tl else None

        if vehicle_tl and not pedestrian_tl:
            if vehicle_status in ('green', 'red'):
                if light_type == 'vehicle':
                    return vehicle_status
                else:
                    return 'red' if vehicle_status == 'green' else 'green'
            elif vehicle_status == 'yellow':
                return 'yellow'
            else:
                return 'UNKNOWN'
        elif pedestrian_tl and not vehicle_tl:
            if pedestrian_status in ('green', 'red'):
                if light_type == 'pedestrian':
                    return pedestrian_status
                else:
                    return 'red' if pedestrian_status == 'green' else 'green'
            elif pedestrian_status == 'yellow':
                return 'yellow'
            else:
                return 'UNKNOWN'
        elif vehicle_tl and pedestrian_tl:
            if (
                vehicle_status in ('green', 'red')
                and pedestrian_status in ('green', 'red')
                and vehicle_status == pedestrian_status
            ):
                print(f"[WARNING] Inconsistent traffic light status in pack {pack_id}: "
                      f"vehicle={vehicle_status}, pedestrian={pedestrian_status}")
            if vehicle_status == 'UNKNOWN' and pedestrian_status in ('green', 'red'):
                vehicle_status = 'red' if pedestrian_status == 'green' else 'green'
            if pedestrian_status == 'UNKNOWN' and vehicle_status in ('green', 'red'):
                pedestrian_status = 'red' if vehicle_status == 'green' else 'green'
            if light_type == 'vehicle':
                return vehicle_status if vehicle_status is not None else 'UNKNOWN'
            else:
                return pedestrian_status if pedestrian_status is not None else 'UNKNOWN'
        else:
            return 'UNKNOWN'

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

                for mon in self.monitors.values():
                    mon.process_frame(objects, now_ts, self.tl_objects)

                lines = []
                any_change = False
                for tl in self.tl_objects:
                    pack = self.packs.get(tl.pack_id)
                    if pack and pack.is_signalized and self._last_tl_status[tl.id] != tl.status:
                        any_change = True
                        break

                if any_change:
                    lines.append(f"[{timestr}] Traffic Light Statuses:")
                    for tl in self.tl_objects:
                        pack = self.packs.get(tl.pack_id)
                        if pack and pack.is_signalized and self._last_tl_status[tl.id] != tl.status:
                            lines.append(f"  Pack:{tl.pack_id} Light:{tl.id} Status:{tl.status}")
                            self._last_tl_status[tl.id] = tl.status

                for pack_id, mon in self.monitors.items():
                    vehicle_status = self.get_effective_traffic_light_status(pack_id, self.tl_objects, 'vehicle')
                    pedestrian_status = self.get_effective_traffic_light_status(pack_id, self.tl_objects, 'pedestrian')
                    for tid, st in mon.entities.items():
                        # Vehicle event
                        if st.class_name != 'person':
                            dur = st.durations.pop('crosswalk', None)
                            if dur is not None and vehicle_status == 'green':
                                lines.append(
                                    f"[{timestr}] Event: Vehicle {tid} passed through crosswalk in Pack:{pack_id} (dur={dur:.2f}s)"
                                )
                        # Pedestrian event (crossed during red/yellow)
                        if st.class_name == 'person':
                            dur = st.durations.pop('crosswalk', None)
                            if dur is not None:
                                if pedestrian_status in ('red', 'yellow'):
                                    lines.append(
                                        f"[{timestr}] VIOLATION: Person {tid} crossed on {pedestrian_status.upper()} pedestrian light in Pack:{pack_id} (dur={dur:.2f}s)"
                                    )
                                elif pedestrian_status == 'green':
                                    lines.append(
                                        f"[{timestr}] Event: Person {tid} crossed on green pedestrian light in Pack:{pack_id} (dur={dur:.2f}s)"
                                    )

                if lines:
                    print("\n".join(lines), flush=True)

                self.inspection_ready.emit(objects, ts)
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._running = False
        self.quit()
        self.wait()
