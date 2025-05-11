# TrafficLightMonitorThread.py
import cv2
import numpy as np
from datetime import datetime
from typing import List, Tuple, Dict
from PyQt5 import QtCore

from crosswalk_inspector.objects.TrafficLight import TrafficLight  # :contentReference[oaicite:0]{index=0}:contentReference[oaicite:1]{index=1}

def hsv_color_classifier(crops: Dict[str, np.ndarray]) -> str:
    # … same implementation as before …
    hsv_ranges = {
        'red': [([0,100,100],[10,255,255]),([160,100,100],[180,255,255])],
        'yellow': [([15,100,100],[35,255,255])],
        'green': [([40,100,100],[85,255,255])]
    }
    max_color, max_count = 'UNKNOWN', 0
    for color, ranges in hsv_ranges.items():
        img = crops.get(color)
        if img is None or img.size == 0: continue
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask = None
        for lo, hi in ranges:
            m = cv2.inRange(hsv, np.array(lo), np.array(hi))
            mask = m if mask is None else cv2.bitwise_or(mask, m)
        cnt = int(cv2.countNonZero(mask))
        if cnt > max_count:
            max_count, max_color = cnt, color
    return max_color

class TrafficLightMonitorThread(QtCore.QThread):
    """
    Receives lists of (TrafficLight, crops_dict, timestamp) via a signal,
    runs classification, and logs status changes.
    """
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.analyze_fn = hsv_color_classifier
        # slot will be connected by the producer:
        # producer.traffic_light_crops.connect(self.on_new_crops)
        self.moveToThread(self)  # ensure slot runs in this thread

    @QtCore.pyqtSlot(list)
    def on_new_crops(self,
            data: List[Tuple[TrafficLight, Dict[str, np.ndarray], float]]):
        """
        data: list of tuples (tl_object, crops, capture_time)
        """
        for tl, crops, ts in data:
            status = tl.update_status(self.analyze_fn)
            timestr = datetime.fromtimestamp(ts) \
                      .strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestr}] Pack:{tl.pack_id} Light:{tl.id} → {status}")

    def run(self):
        # Start Qt event loop to process incoming signals
        try:
            self.exec_()
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self.quit()
        self.wait()
