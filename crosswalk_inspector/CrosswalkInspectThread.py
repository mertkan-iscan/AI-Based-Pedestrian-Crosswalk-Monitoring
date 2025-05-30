import time
from datetime import datetime


from PyQt5 import QtCore

from crosswalk_inspector.CrosswalkPackMonitor import CrosswalkPackMonitor
from utils.objects.TrafficLight import TrafficLight
from utils.RegionManager import RegionManager
from utils.GlobalState import GlobalState


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
        self.global_state = global_state
        self.tl_objects = tl_objects
        self.check_period = check_period
        self.homography_inv = homography_inv
        self._running = True
        self._last_check = 0.0

        self.monitors = {
            pack.id: CrosswalkPackMonitor(pack, homography_inv)
            for pack in editor.crosswalk_packs
        }
        self.seq_state = {pid: {} for pid in self.monitors}
        self.event_handlers = [
            self._detect_sequence_events,
            self._detect_vehicle_events,
            self._detect_pedestrian_events
        ]

    def get_light_status(self, pack_id, light_type):
        vehicle = next((tl for tl in self.tl_objects if tl.pack_id == pack_id and tl.type == 'vehicle'), None)
        pedestrian = next((tl for tl in self.tl_objects if tl.pack_id == pack_id and tl.type == 'pedestrian'), None)
        v_status = vehicle.status if vehicle else None
        p_status = pedestrian.status if pedestrian else None
        if light_type == 'vehicle':
            if v_status in ('green', 'red'):
                return v_status
            if p_status in ('green', 'red'):
                return 'red' if p_status == 'green' else 'green'
            return 'UNKNOWN'
        else:
            if p_status in ('green', 'red'):
                return p_status
            if v_status in ('green', 'red'):
                return 'red' if v_status == 'green' else 'green'
            return 'UNKNOWN'

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
                now_time = time.time()
                if now_time - self._last_check < self.check_period:
                    time.sleep(0.005)
                    continue
                self._last_check = now_time

                objects, ts = self.global_state.get()
                if not objects:
                    continue
                timestamp = datetime.fromtimestamp(ts)
                timestr = timestamp.strftime("%H:%M:%S.%f")[:-3]

                for monitor in self.monitors.values():
                    monitor.process_frame(objects, timestamp)

                events = []
                for pack_id, monitor in self.monitors.items():
                    v_status = self.get_effective_traffic_light_status(pack_id, self.tl_objects, 'vehicle')
                    p_status = self.get_effective_traffic_light_status(pack_id, self.tl_objects, 'pedestrian')
                    for state in monitor.entities.values():
                        for handler in self.event_handlers:
                            events.extend(handler(pack_id, state, v_status, p_status, timestr))
                if events:
                    self._handle_events(events)
                self.inspection_ready.emit(objects, ts)
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._running = False
        self.quit()
        self.wait()

    def _detect_pedestrian_sequence_events(self, pack_id, state, v_status, p_status, timestr):
        seq = self.seq_state.setdefault(pack_id, {}).setdefault(state.id, {'start': None, 'step': 0})
        events = []
        d0 = state.durations.pop('ped_wait_0', None)
        d1 = state.durations.pop('ped_wait_1', None)
        if seq['step'] == 2:
            if (seq['start'] == 0 and d1 is not None) or (seq['start'] == 1 and d0 is not None):
                events.append(f"[{timestr}] Pedestrian {state.id} completed crossing Pack:{pack_id}")
                seq['step'] = 0
        if seq['step'] == 0:
            if d0 is not None:
                seq.update({'start': 0, 'step': 1})
            elif d1 is not None:
                seq.update({'start': 1, 'step': 1})
        return events

    def _detect_vehicle_events(self, pack_id, state, v_status, p_status, timestr):
        events = []
        if state.class_name != 'person':
            d = state.durations.pop('crosswalk', None)
            if d is not None and v_status == 'green':
                events.append(f"[{timestr}] Vehicle {state.id} passed Pack:{pack_id} in {d:.2f}s")
        return events

    def _detect_pedestrian_events(self, pack_id, state, v_status, p_status, timestr):
        events = []
        if state.class_name == 'person':
            d = state.durations.pop('crosswalk', None)
            seq = self.seq_state[pack_id][state.id]
            if d is not None and seq['step'] == 1:
                seq['step'] = 2
            if d is not None:
                status = p_status.lower()
                key = 'VIOLATION' if status in ('red', 'yellow') else 'Event'
                events.append(f"[{timestr}] {key}: Pedestrian {state.id} crossed on {status} light in Pack:{pack_id} ({d:.2f}s)")
        return events


    def _detect_sequence_events(self, pack_id, state, v_status, p_status, timestr):
        seq = self.seq_state.setdefault(pack_id, {}).setdefault(state.id, {'start': None, 'step': 0})
        events = []
        d0 = state.durations.pop('ped_wait_0', None)
        d1 = state.durations.pop('ped_wait_1', None)

        if seq['step'] == 2 and ((seq['start'] == 0 and d1 is not None) or (seq['start'] == 1 and d0 is not None)):
            events.append(f"[{timestr}] Pedestrian {state.id} completed crossing Pack:{pack_id}")
            monitor = self.monitors[pack_id]
            for v_state in monitor.entities.values():
                if v_state.class_name == 'person':
                    continue
                if 'crosswalk' in v_state.current_regions:
                    events.append(f"[{timestr}] Violation: Vehicle {v_state.id} entered crosswalk during pedestrian crossing Pack:{pack_id}")
                elif any(r.startswith('car_wait_') for r in v_state.current_regions):
                    events.append(f"[{timestr}] Vehicle {v_state.id} yielded to pedestrian {state.id} in Pack:{pack_id}")
            seq['step'] = 0

        if seq['step'] == 0:
            if d0 is not None:
                seq.update({'start': 0, 'step': 1})
            elif d1 is not None:
                seq.update({'start': 1, 'step': 1})

        return events
    def _handle_events(self, events):
        print("\n".join(events), flush=True)

