import os
import queue
from concurrent.futures import ThreadPoolExecutor
from PyQt5 import QtCore
from utils.region.RegionManager import RegionManager

class CrosswalkInspectThread(QtCore.QThread):
    inspection_ready = QtCore.pyqtSignal(list, float)
    error_signal     = QtCore.pyqtSignal(str)

    def __init__(self, editor: RegionManager, object_queue: queue.Queue, parent=None, max_workers=None):
        super().__init__(parent)
        self.editor       = editor
        self.object_queue = object_queue
        self._is_running  = True
        # default to number of CPU cores if not specified
        self.max_workers  = max_workers or (os.cpu_count() or 4)

    def run(self):
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                while self._is_running:
                    try:
                        objects, capture_time = self.object_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue

                    # schedule one future per object
                    future_to_obj = {}
                    for obj in objects:
                        # pick the point to test
                        if getattr(obj, "foot_coordinate", None) is not None:
                            px, py = obj.foot_coordinate
                        else:
                            px, py = obj.centroid_coordinate

                        fut = executor.submit(
                            self.editor.get_polygons_for_point,
                            (int(px), int(py)),
                            self.editor.region_polygons
                        )
                        future_to_obj[fut] = obj

                    # collect and update regions
                    for fut, obj in future_to_obj.items():
                        try:
                            regions = fut.result()
                            obj.region = regions[0] if regions else "unknown"
                        except Exception:
                            obj.region = "unknown"

                    # emit updated list
                    self.inspection_ready.emit(objects, capture_time)

        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()

