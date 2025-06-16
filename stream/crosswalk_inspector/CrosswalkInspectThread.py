import os
import csv
import queue
import threading
import time
from datetime import datetime, timedelta
from PyQt5 import QtCore
from stream.crosswalk_inspector.CrosswalkPackMonitor import CrosswalkPackMonitor
from stream.crosswalk_inspector.Region import Region
from stream.crosswalk_inspector.TrafficLight import TrafficLight
from utils.RegionManager import RegionManager
from utils.GlobalState import GlobalState

class CrosswalkInspectThread(QtCore.QThread):
    inspection_ready = QtCore.pyqtSignal(list, float)
    error_signal      = QtCore.pyqtSignal(str)

    def __init__(
        self,
        editor: RegionManager,
        global_state: GlobalState,
        tl_objects: list[TrafficLight],
        check_period: float,
        homography_inv=None,
        location_name: str = "unknown",
        is_live: bool = True,
        delay_seconds: float = 0.0,
        parent=None
    ):
        super().__init__(parent)
        self.global_state       = global_state
        self.tl_objects         = tl_objects
        self.check_period       = check_period
        self.homography_inv     = homography_inv
        self.is_live            = is_live
        self.delay_seconds      = delay_seconds
        self._running           = True
        self._last_check        = 0.0

        self.sanitized_location = location_name.replace(" ", "_")

        if is_live:
            start_dt           = datetime.now() - timedelta(seconds=delay_seconds)
            self.start_label   = start_dt.strftime("%Y-%m-%d_%H-%M-%S")
        else:
            self.start_label       = "00-00-00"
            self.video_wall_start  = None
            self.last_ts           = None

        self.live_end_label    = None

        reports_dir = os.path.join(os.getcwd(), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        self.reports_dir        = reports_dir

        self.events_file_path   = os.path.join(
            reports_dir,
            f"events_{self.sanitized_location}_{self.start_label}.csv"
        )
        self.sidewalk_file_path = os.path.join(
            reports_dir,
            f"sidewalk_transitions_{self.sanitized_location}_{self.start_label}.csv"
        )

        self.events_csv    = open(self.events_file_path,   "a", newline="")
        self.events_writer = csv.writer(self.events_csv)
        if os.path.getsize(self.events_file_path) == 0:
            self.events_writer.writerow([
                "timestamp","event_type","entity_type","entity_id",
                "pack_id","duration","light_status","violation"
            ])

        self.sidewalk_csv    = open(self.sidewalk_file_path, "a", newline="")
        self.sidewalk_writer = csv.writer(self.sidewalk_csv)
        if os.path.getsize(self.sidewalk_file_path) == 0:
            self.sidewalk_writer.writerow([
                "timestamp","person_id","from_region","to_region"
            ])

        self.monitors            = {
            pack.id: CrosswalkPackMonitor(pack, homography_inv)
            for pack in editor.crosswalk_packs
        }
        self.seq_state           = {pid: {} for pid in self.monitors}
        self.event_handlers      = [
            self._detect_sequence_events,
            self._detect_vehicle_events,
            self._detect_vehicle_violation_events,
            self._detect_pedestrian_events
        ]
        self.sidewalk_regions    = {
            poly["id"]: Region(poly["points"], homography_inv)
            for poly in editor.other_regions.get("sidewalk", [])
        }
        self.sidewalk_assignments = {}
        self.trajectory_buffer    = {}
        self.origin_sidewalk      = {}

        self._write_queue   = queue.Queue()
        self._writer_thread = threading.Thread(
            target=self._writer_loop, daemon=True
        )
        self._writer_thread.start()

    def run(self):
        try:
            while self._running:
                now = time.time()
                if now - self._last_check < self.check_period:
                    time.sleep(0.005)
                    continue
                self._last_check = now

                objects, ts = self.global_state.get()
                if not objects:
                    continue

                if not self.is_live:
                    if self.video_wall_start is None:
                        self.video_wall_start = ts
                    self.last_ts = ts

                if self.is_live:
                    timestamp = datetime.fromtimestamp(ts)
                    timestr   = timestamp.strftime("%H-%M-%S")
                    self.live_end_label = timestr
                else:
                    elapsed = self.last_ts - self.video_wall_start
                    timestr = self._secs_to_timestr(elapsed)

                statuses = {
                    pid: (
                        self.get_effective_traffic_light_status(pid, self.tl_objects, "vehicle"),
                        self.get_effective_traffic_light_status(pid, self.tl_objects, "pedestrian")
                    )
                    for pid in self.monitors
                }

                for det in objects:
                    if det.object_type == "person":
                        pt = getattr(det, "surface_point", None) or getattr(det, "raw_surface_point", None)
                        if pt is not None:
                            self._handle_pedestrian_sidewalk_transition(det.id, pt, timestr)

                for pid, monitor in self.monitors.items():
                    monitor.process_frame(objects, datetime.fromtimestamp(ts))

                for pid, monitor in self.monitors.items():
                    vstat, pstat = statuses[pid]
                    for state in monitor.entities.values():
                        for handler in self.event_handlers:
                            evs = handler(pid, state, vstat, pstat, timestr)
                            if evs:
                                self._handle_events(evs)

                self.inspection_ready.emit(objects, ts)
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        # 1) signal run() to exit & wait for writer thread to finish
        self._running = False
        self._writer_thread.join(timeout=1.0)

        # 2) close CSV files so they can be renamed on Windows
        self.events_csv.close()
        self.sidewalk_csv.close()

        # 3) compute the final end label
        if self.is_live:
            end_dt    = datetime.now() - timedelta(seconds=self.delay_seconds)
            end_label = end_dt.strftime("%H-%M-%S")
        else:
            if self.video_wall_start is not None and self.last_ts is not None:
                elapsed_secs = self.last_ts - self.video_wall_start
                end_label    = self._secs_to_timestr(elapsed_secs)
            else:
                end_label    = self.start_label

        # 4) build new filenames with both start and end
        base        = f"{self.sanitized_location}_{self.start_label}_{end_label}"
        new_events  = os.path.join(self.reports_dir, f"events_{base}.csv")
        new_sideway = os.path.join(self.reports_dir, f"sidewalk_transitions_{base}.csv")

        # 5) perform rename
        try:
            os.rename(self.events_file_path, new_events)
            os.rename(self.sidewalk_file_path, new_sideway)
        except OSError:
            # if something goes wrong, at least the files are closed
            pass

        # 6) finally, quit the thread
        self.quit()
        self.wait()

    def _writer_loop(self):
        while self._running or not self._write_queue.empty():
            try:
                kind, row = self._write_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if kind == "event":
                self.events_writer.writerow(row)
            else:
                self.sidewalk_writer.writerow(row)
            self._write_queue.task_done()
        try:
            self.events_csv.flush()
            self.sidewalk_csv.flush()
        except Exception:
            pass

    def _handle_pedestrian_sidewalk_transition(self, tid, pt, timestr):
        prev = self.sidewalk_assignments.get(tid)
        curr = next(
            (sid for sid, reg in self.sidewalk_regions.items() if reg.contains(pt)),
            None
        )
        if prev is None and curr is not None:
            origin = self.origin_sidewalk.pop(tid, None)
            if origin is not None and origin != curr:
                self._write_queue.put(("sidewalk", [timestr, tid, origin, curr]))
        if prev is not None and curr is None:
            self.origin_sidewalk[tid]   = prev
            self.trajectory_buffer[tid] = [pt]
        elif prev is None and curr is None and tid in self.trajectory_buffer:
            self.trajectory_buffer[tid].append(pt)
        self.sidewalk_assignments[tid] = curr

    def _handle_events(self, events):
        for ev in events:
            row = [
                ev["timestamp"], ev["event_type"], ev["entity_type"],
                ev["entity_id"], ev["pack_id"], ev.get("duration"),
                ev.get("light_status"), ev.get("violation")
            ]
            self._write_queue.put(("event", row))

    def _detect_sequence_events(self, pack_id, state, v_status, p_status, timestr):
        seq    = self.seq_state.setdefault(pack_id, {}).setdefault(
            state.id, {"start": None, "step": 0}
        )
        events = []
        d0 = state.durations.pop("ped_wait_0", None)
        d1 = state.durations.pop("ped_wait_1", None)
        if seq["step"] == 2 and ((seq["start"] == 0 and d1) or (seq["start"] == 1 and d0)):
            events.append({
                "timestamp": timestr,
                "event_type": "pedestrian_completed",
                "entity_type": "pedestrian",
                "entity_id": state.id,
                "pack_id": pack_id,
                "duration": None,
                "light_status": None,
                "violation": False
            })
            monitor = self.monitors[pack_id]
            for v_state in monitor.entities.values():
                if v_state.class_name != "person":
                    if "crosswalk" in v_state.current_regions:
                        events.append({
                            "timestamp": timestr,
                            "event_type": "vehicle_violation_during_ped",
                            "entity_type": "vehicle",
                            "entity_id": v_state.id,
                            "pack_id": pack_id,
                            "duration": None,
                            "light_status": None,
                            "violation": True
                        })
                    elif any(r.startswith("car_wait_") for r in v_state.current_regions):
                        events.append({
                            "timestamp": timestr,
                            "event_type": "vehicle_yield",
                            "entity_type": "vehicle",
                            "entity_id": v_state.id,
                            "pack_id": pack_id,
                            "duration": None,
                            "light_status": None,
                            "violation": False
                        })
            seq["step"] = 0
        if seq["step"] == 0 and d0 is not None:
            seq.update({"start": 0, "step": 1})
        elif seq["step"] == 0 and d1 is not None:
            seq.update({"start": 1, "step": 1})
        return events

    def _detect_vehicle_events(self, pack_id, state, v_status, p_status, timestr):
        events = []
        if state.class_name != "person":
            d = state.durations.pop("crosswalk", None)
            if d is not None and v_status == "green":
                events.append({
                    "timestamp": timestr,
                    "event_type": "pass",
                    "entity_type": "vehicle",
                    "entity_id": state.id,
                    "pack_id": pack_id,
                    "duration": d,
                    "light_status": v_status,
                    "violation": False
                })
        return events

    def _detect_vehicle_violation_events(self, pack_id, state, v_status, p_status, timestr):
        events = []
        if state.class_name != "person":
            d = state.durations.pop("crosswalk", None)
            if d is not None and v_status in ("red", "yellow"):
                events.append({
                    "timestamp": timestr,
                    "event_type": "violation",
                    "entity_type": "vehicle",
                    "entity_id": state.id,
                    "pack_id": pack_id,
                    "duration": d,
                    "light_status": v_status,
                    "violation": True
                })
        return events

    def _detect_pedestrian_events(self, pack_id, state, v_status, p_status, timestr):
        events = []
        if state.class_name == "person":
            d = state.durations.pop("crosswalk", None)
            if d is not None:
                status = p_status.lower()
                events.append({
                    "timestamp": timestr,
                    "event_type": "cross",
                    "entity_type": "pedestrian",
                    "entity_id": state.id,
                    "pack_id": pack_id,
                    "duration": d,
                    "light_status": status,
                    "violation": status in ("red", "yellow")
                })
        return events

    def get_effective_traffic_light_status(self, pack_id, tl_objects, light_type):
        vehicle_tl, pedestrian_tl = None, None
        for tl in tl_objects:
            if tl.pack_id != pack_id:
                continue
            if tl.type == "vehicle":
                vehicle_tl = tl
            elif tl.type == "pedestrian":
                pedestrian_tl = tl
        v_status = vehicle_tl.status if vehicle_tl else None
        p_status = pedestrian_tl.status if pedestrian_tl else None
        if vehicle_tl and not pedestrian_tl:
            if v_status in ("green", "red"):
                return v_status if light_type == "vehicle" else ("red" if v_status == "green" else "green")
            if v_status == "yellow":
                return "yellow"
            return "UNKNOWN"
        if pedestrian_tl and not vehicle_tl:
            if p_status in ("green", "red"):
                return p_status if light_type == "pedestrian" else ("red" if p_status == "green" else "green")
            if p_status == "yellow":
                return "yellow"
            return "UNKNOWN"
        if vehicle_tl and pedestrian_tl:
            if v_status == "UNKNOWN" and p_status in ("green", "red"):
                v_status = "red" if p_status == "green" else "green"
            if p_status == "UNKNOWN" and v_status in ("green", "red"):
                p_status = "red" if v_status == "green" else "green"
            return v_status if light_type == "vehicle" else p_status
        return "UNKNOWN"

    @staticmethod
    def _secs_to_timestr(secs: float) -> str:
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        s = int(secs % 60)
        return f"{h:02d}-{m:02d}-{s:02d}"
