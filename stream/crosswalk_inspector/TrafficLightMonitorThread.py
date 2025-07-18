import cv2
import numpy as np
import time
import threading
from typing import List, Tuple, Dict
from PyQt5 import QtCore

from stream.crosswalk_inspector.TrafficLight import TrafficLight


def hsv_color_classifier(crops: Dict[str, np.ndarray]) -> str:
    hsv_ranges = {
        'red':    [([0, 100, 100], [10, 255, 255]), ([160, 100, 100], [180, 255, 255])],
        'yellow': [([15, 100, 100], [35, 255, 255])],
        'green':  [([40, 100, 100], [85, 255, 255])]
    }
    best_color, best_cnt = 'UNKNOWN', 0
    for color, ranges in hsv_ranges.items():
        img = crops.get(color)
        if img is None or img.size == 0:
            continue
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask = None
        for lo, hi in ranges:
            part = cv2.inRange(hsv, np.array(lo), np.array(hi))
            mask = part if mask is None else cv2.bitwise_or(mask, part)
        cnt = int(cv2.countNonZero(mask))
        if cnt > best_cnt:
            best_cnt, best_color = cnt, color
    return best_color

class TrafficLightMonitorThread(QtCore.QThread):
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, delay: float = 0.0, parent=None):
        super().__init__(parent)
        self.delay = float(delay)
        self.analyze_fn = self.robust_traffic_light_classifier

    def hsv_color_classifier(self, crops: Dict[str, np.ndarray]) -> str:
        hsv_ranges = {
            'red': [([0, 100, 100], [10, 255, 255]), ([160, 100, 100], [180, 255, 255])],
            'yellow': [([15, 100, 100], [35, 255, 255])],
            'green': [([40, 100, 100], [85, 255, 255])]
        }
        best_color, best_cnt = 'UNKNOWN', 0
        for color, ranges in hsv_ranges.items():
            img = crops.get(color)
            if img is None or img.size == 0:
                continue
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            mask = None
            for lo, hi in ranges:
                part = cv2.inRange(hsv, np.array(lo), np.array(hi))
                mask = part if mask is None else cv2.bitwise_or(mask, part)
            cnt = int(cv2.countNonZero(mask))
            if cnt > best_cnt:
                best_cnt, best_color = cnt, color
        return best_color

    def mean_top_percent_v(self, img, percent=5):
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        v = hsv[..., 2].flatten()
        v = v[v > 0]
        if len(v) == 0:
            return 0
        top_n = max(1, int(len(v) * percent / 100))
        return np.mean(np.partition(v, -top_n)[-top_n:])

    def robust_traffic_light_classifier(self, crops: Dict[str, np.ndarray]) -> str:
        MIN_ON_THRESHOLD = 80
        MIN_DIFF = 8

        means = {}
        for color in ['red', 'yellow', 'green']:
            crop = crops.get(color)
            if crop is None or crop.size == 0:
                means[color] = 0
                continue
            means[color] = self.mean_top_percent_v(crop, percent=5)

        sorted_means = sorted(means.items(), key=lambda x: x[1], reverse=True)
        top_color, top_value = sorted_means[0]
        second_value = sorted_means[1][1]

        if all(val < MIN_ON_THRESHOLD for val in means.values()):
            return "UNKNOWN"

        if top_value - second_value >= MIN_DIFF:
            return top_color

        return top_color


    @QtCore.pyqtSlot(list)
    def on_new_crops(
        self,
        data: List[Tuple[TrafficLight, Dict[str, np.ndarray], float]]
    ):
        now = time.time()
        for tl, crops, ts in data:
            # 1) classify immediately to see if status actually changed
            predicted = self.analyze_fn(crops)
            # 2) if no change vs. last known status, skip scheduling
            if predicted == tl.status:
                continue

            # 3) schedule the actual update (immediate or delayed)
            emit_time     = ts + self.delay
            schedule_delay = emit_time - now

            if schedule_delay <= 0:
                self._update_light(tl, crops)
            else:
                timer = threading.Timer(
                    schedule_delay,
                    self._update_light,
                    args=(tl, crops)
                )
                timer.daemon = True
                timer.start()

    def _update_light(self, tl: TrafficLight, crops: Dict[str, np.ndarray]):
        crops_snapshot = dict(crops)
        tl.crops = {k: v.copy() for k, v in crops_snapshot.items()}
        result = self.analyze_fn(crops)
        tl.update_status(result)

    def run(self):
        try:
            self.exec_()
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self.quit()
        self.wait()