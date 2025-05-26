import threading
import queue

class MotWriterThread(threading.Thread):
    def __init__(self, filename):
        super().__init__()
        self.queue = queue.Queue()
        self.filename = filename
        self._run = True
        self._buffer = []

    def run(self):
        while self._run or not self.queue.empty():
            try:
                data = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if data is None:
                break
            frame_idx, tracks_map = data
            for track_id, (centroid, bbox) in tracks_map.items():
                x1, y1, x2, y2, cls_idx, conf = bbox[:6]
                bb_left = float(x1)
                bb_top = float(y1)
                bb_width = float(x2 - x1)
                bb_height = float(y2 - y1)
                conf_val = float(conf) if conf is not None else 1.0
                line = f"{frame_idx},{track_id},{bb_left:.2f},{bb_top:.2f},{bb_width:.2f},{bb_height:.2f},{conf_val:.3f},-1,-1,-1\n"
                self._buffer.append(line)

    def submit(self, frame_idx, tracks_map):
        self.queue.put((frame_idx, tracks_map))

    def stop(self):
        self._run = False
        self.queue.put(None)
        self.join()
        # --- Dosyaya sadece burada yazılıyor! ---
        with open(self.filename, "w") as f:
            f.writelines(self._buffer)
