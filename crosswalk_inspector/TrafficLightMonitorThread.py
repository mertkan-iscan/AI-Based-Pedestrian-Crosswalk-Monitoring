# TrafficLightMonitorThread.py
import time
from datetime import datetime
from PyQt5 import QtCore
from concurrent.futures import ThreadPoolExecutor

from crosswalk_inspector.objects.TrafficLight import TrafficLight
from utils.region.RegionManager import RegionManager
from crosswalk_inspector.GlobalState import GlobalState

class TrafficLightMonitorThread(QtCore.QThread):
    """QThread that periodically crops and analyzes traffic-light regions."""
    error_signal = QtCore.pyqtSignal(str)

    def __init__(
        self,
        editor: RegionManager,
        global_state: GlobalState,
        analyze_fn,
        inverse_homography=None,
        check_period: float = 0.2,
        parent=None,
        max_workers=None
    ):
        super().__init__(parent)
        self.editor        = editor
        self.state         = global_state
        self.analyze_fn    = analyze_fn  # TODO: implement color‐classification logic
        self.H_inv         = inverse_homography
        self.check_period  = check_period
        self._running      = True
        self.max_workers   = max_workers or (QtCore.QThread.idealThreadCount() or 4)

        # build TrafficLight objects
        self.tl_objects = []
        for pack in editor.crosswalk_packs:
            groups = {}
            for c in pack.traffic_light:
                gid = c['id']
                groups.setdefault(gid, {
                    'type': c['light_type'],
                    'lights': {}
                })['lights'][c['signal_color']] = {
                    'center': c['center'],
                    'radius': c['radius']
                }
            for gid, cfg in groups.items():
                self.tl_objects.append(
                    TrafficLight(pack.id, gid, cfg['type'], cfg['lights'])
                )

    def run(self):
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                last_check = 0.0
                while self._running:
                    now_wall = time.time()
                    if now_wall - last_check < self.check_period:
                        time.sleep(0.01)
                        continue
                    last_check = now_wall

                    frame = self.state.last_frame
                    if frame is None:
                        continue

                    # optional: apply inverse homography if needed
                    if self.H_inv is not None:
                        # ...apply H_inv to frame or to centers before cropping...
                        pass

                    # process each light in parallel
                    futures = [executor.submit(self._process_light, tl) for tl in self.tl_objects]
                    # just wait for them all to finish
                    for f in futures:
                        f.result()
        except Exception as e:
            self.error_signal.emit(str(e))

    def _process_light(self, tl: TrafficLight):
        """Crop, analyze, and print status change for one light."""
        tl.crop_regions(self.state.last_frame)               # :contentReference[oaicite:0]{index=0}:contentReference[oaicite:1]{index=1}
        new_status = tl.update_status(self.analyze_fn)        # :contentReference[oaicite:2]{index=2}
        timestamp  = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] Pack:{tl.pack_id} Light:{tl.id} → {new_status}")

    def stop(self):
        self._running = False
        self.quit()
        self.wait()
