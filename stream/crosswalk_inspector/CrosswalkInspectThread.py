import os
import csv
import queue
import threading
import time
from datetime import datetime
from PyQt5 import QtCore
from stream.crosswalk_inspector.CrosswalkPackMonitor import CrosswalkPackMonitor
from stream.crosswalk_inspector.Region import Region
from stream.crosswalk_inspector.TrafficLight import TrafficLight
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
        location_name: str = "unknown",
        parent=None
    ):
        super().__init__(parent)
        self.global_state = global_state
        self.tl_objects = tl_objects
        self.check_period = check_period
        self.homography_inv = homography_inv
        self._running = True
        self._last_check = 0.0

        # set up monitors and initial state
        self.monitors = {pack.id: CrosswalkPackMonitor(pack, homography_inv)
                         for pack in editor.crosswalk_packs}
        self.seq_state = {pid: {} for pid in self.monitors}
        self.event_handlers = [
            self._detect_sequence_events,
            self._detect_vehicle_events,
            self._detect_vehicle_violation_events,
            self._detect_pedestrian_events
        ]
        self.sidewalk_regions = {poly["id"]: Region(poly["points"], homography_inv)
                                 for poly in editor.other_regions.get("sidewalk", [])}
        self.sidewalk_assignments = {}
        self.trajectory_buffer = {}
        self.origin_sidewalk = {}

        # prepare reports directory and CSV files
        reports_dir = os.path.join(os.getcwd(), 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        self.events_file_path = os.path.join(reports_dir, f"events_{location_name}.csv")
        self.sidewalk_file_path = os.path.join(reports_dir, f"sidewalk_transitions_{location_name}.csv")

        self.events_csv = open(self.events_file_path, 'a', newline='')
        self.events_writer = csv.writer(self.events_csv)
        if os.path.getsize(self.events_file_path) == 0:
            self.events_writer.writerow([
                'timestamp', 'event_type', 'entity_type', 'entity_id',
                'pack_id', 'duration', 'light_status', 'violation'
            ])

        self.sidewalk_csv = open(self.sidewalk_file_path, 'a', newline='')
        self.sidewalk_writer = csv.writer(self.sidewalk_csv)
        if os.path.getsize(self.sidewalk_file_path) == 0:
            self.sidewalk_writer.writerow([
                'timestamp', 'pedestrian_id', 'from_sidewalk',
                'to_sidewalk', 'trajectory_list'
            ])

        # setup asynchronous writer thread
        self._write_queue = queue.Queue()
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()

    def _writer_loop(self):
        """
        Background thread: consume write tasks and perform disk IO.
        """
        while self._running or not self._write_queue.empty():
            try:
                kind, row = self._write_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if kind == 'event':
                    self.events_writer.writerow(row)
                elif kind == 'sidewalk':
                    self.sidewalk_writer.writerow(row)
            except Exception:
                pass
            finally:
                self._write_queue.task_done()
        # final flush and close
        try:
            self.events_csv.flush()
            self.sidewalk_csv.flush()
            self.events_csv.close()
            self.sidewalk_csv.close()
        except Exception:
            pass

    def run(self):
        try:
            while self._running:
                start = time.time()
                if start - self._last_check < self.check_period:
                    time.sleep(0.005)
                    continue
                self._last_check = start

                objects, ts = self.global_state.get()
                if not objects:
                    continue
                timestamp = datetime.fromtimestamp(ts)
                timestr = timestamp.strftime("%H:%M:%S.%f")[:-3]

                # cache traffic light statuses per pack to avoid repeated scanning
                statuses = {}
                for pack_id in self.monitors:
                    statuses[pack_id] = (
                        self.get_effective_traffic_light_status(pack_id, self.tl_objects, 'vehicle'),
                        self.get_effective_traffic_light_status(pack_id, self.tl_objects, 'pedestrian')
                    )

                # handle sidewalk transitions
                for det in objects:
                    if det.object_type == 'person':
                        tid = det.id
                        pt = getattr(det, 'surface_point', None) or getattr(det, 'raw_surface_point', None)
                        if pt is not None:
                            self._handle_pedestrian_sidewalk_transition(tid, pt, timestr)

                # process each pack and its entities
                for pack_id, monitor in self.monitors.items():
                    monitor.process_frame(objects, timestamp)

                # collect and queue all events
                for pack_id, monitor in self.monitors.items():
                    v_status, p_status = statuses[pack_id]
                    for state in monitor.entities.values():
                        for handler in self.event_handlers:
                            evs = handler(pack_id, state, v_status, p_status, timestr)
                            if evs:
                                self._handle_events(evs)

                # emit signal once per loop, not per event
                self.inspection_ready.emit(objects, ts)

        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._running = False
        self._writer_thread.join(timeout=1.0)
        self.quit()
        self.wait()

    def _handle_pedestrian_sidewalk_transition(self, tid, pt, timestr):
        prev = self.sidewalk_assignments.get(tid)
        curr = next((sid for sid, region in self.sidewalk_regions.items() if region.contains(pt)), None)

        if prev is None and curr is not None:
            origin = self.origin_sidewalk.pop(tid, None)
            traj = self.trajectory_buffer.pop(tid, [])
            if origin is not None and origin != curr:
                row = [timestr, tid, origin, curr, traj]
                self._write_queue.put(('sidewalk', row))

        if prev is not None and curr is None:
            self.origin_sidewalk[tid] = prev
            self.trajectory_buffer[tid] = [pt]
        elif prev is None and curr is None and tid in self.trajectory_buffer:
            self.trajectory_buffer[tid].append(pt)

        self.sidewalk_assignments[tid] = curr

    def _handle_events(self, events):
        for ev in events:
            row = [
                ev['timestamp'], ev['event_type'], ev['entity_type'], ev['entity_id'],
                ev['pack_id'], ev.get('duration'), ev.get('light_status'), ev.get('violation')
            ]
            self._write_queue.put(('event', row))

    def _detect_vehicle_events(self, pack_id, state, v_status, p_status, timestr):
        # unchanged detection handlers...
        events = []
        if state.class_name != 'person':
            d = state.durations.pop('crosswalk', None)
            if d is not None and v_status == 'green':
                events.append({
                    'timestamp': timestr,
                    'event_type': 'pass',
                    'entity_type': 'vehicle',
                    'entity_id': state.id,
                    'pack_id': pack_id,
                    'duration': d,
                    'light_status': v_status,
                    'violation': False
                })
        return events


    def _detect_vehicle_violation_events(self, pack_id, state, v_status, p_status, timestr):
        events = []
        if state.class_name != 'person':
            d = state.durations.pop('crosswalk', None)
            if d is not None and v_status in ('red', 'yellow'):
                events.append({
                    'timestamp': timestr,
                    'event_type': 'violation',
                    'entity_type': 'vehicle',
                    'entity_id': state.id,
                    'pack_id': pack_id,
                    'duration': d,
                    'light_status': v_status,
                    'violation': True
                })
        return events

    def _detect_pedestrian_events(self, pack_id, state, v_status, p_status, timestr):
        events = []
        if state.class_name == 'person':
            d = state.durations.pop('crosswalk', None)
            if d is not None:
                status = p_status.lower()
                events.append({
                    'timestamp': timestr,
                    'event_type': 'cross',
                    'entity_type': 'pedestrian',
                    'entity_id': state.id,
                    'pack_id': pack_id,
                    'duration': d,
                    'light_status': status,
                    'violation': status in ('red', 'yellow')
                })
        return events

    def _detect_sequence_events(self, pack_id, state, v_status, p_status, timestr):
        seq = self.seq_state.setdefault(pack_id, {}).setdefault(state.id, {'start': None, 'step': 0})
        events = []
        d0 = state.durations.pop('ped_wait_0', None)
        d1 = state.durations.pop('ped_wait_1', None)

        if seq['step'] == 2 and ((seq['start'] == 0 and d1 is not None) or (seq['start'] == 1 and d0 is not None)):
            events.append({
                'timestamp': timestr,
                'event_type': 'pedestrian_completed',
                'entity_type': 'pedestrian',
                'entity_id': state.id,
                'pack_id': pack_id,
                'duration': None,
                'light_status': None,
                'violation': False
            })
            monitor = self.monitors[pack_id]
            for v_state in monitor.entities.values():
                if v_state.class_name != 'person':
                    if 'crosswalk' in v_state.current_regions:
                        events.append({
                            'timestamp': timestr,
                            'event_type': 'vehicle_violation_during_ped',
                            'entity_type': 'vehicle',
                            'entity_id': v_state.id,
                            'pack_id': pack_id,
                            'duration': None,
                            'light_status': None,
                            'violation': True
                        })
                    elif any(r.startswith('car_wait_') for r in v_state.current_regions):
                        events.append({
                            'timestamp': timestr,
                            'event_type': 'vehicle_yield',
                            'entity_type': 'vehicle',
                            'entity_id': v_state.id,
                            'pack_id': pack_id,
                            'duration': None,
                            'light_status': None,
                            'violation': False
                        })
            seq['step'] = 0

        if seq['step'] == 0 and d0 is not None:
            seq.update({'start': 0, 'step': 1})
        elif seq['step'] == 0 and d1 is not None:
            seq.update({'start': 1, 'step': 1})

        return events

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
                return 'red' if vehicle_status == 'green' else 'green'
            if vehicle_status == 'yellow':
                return 'yellow'
            return 'UNKNOWN'

        if pedestrian_tl and not vehicle_tl:
            if pedestrian_status in ('green', 'red'):
                if light_type == 'pedestrian':
                    return pedestrian_status
                return 'red' if pedestrian_status == 'green' else 'green'
            if pedestrian_status == 'yellow':
                return 'yellow'
            return 'UNKNOWN'

        if vehicle_tl and pedestrian_tl:
            if (vehicle_status in ('green', 'red') and pedestrian_status in ('green', 'red') and
                    vehicle_status == pedestrian_status):
                pass
            if vehicle_status == 'UNKNOWN' and pedestrian_status in ('green', 'red'):
                vehicle_status = 'red' if pedestrian_status == 'green' else 'green'
            if pedestrian_status == 'UNKNOWN' and vehicle_status in ('green', 'red'):
                pedestrian_status = 'red' if vehicle_status == 'green' else 'green'
            if light_type == 'vehicle':
                return vehicle_status or 'UNKNOWN'
            return pedestrian_status or 'UNKNOWN'

        return 'UNKNOWN'
