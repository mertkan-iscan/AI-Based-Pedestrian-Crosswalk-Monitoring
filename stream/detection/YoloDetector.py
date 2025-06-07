import cv2
import warnings
from ultralytics import YOLO

warnings.filterwarnings("ignore", category=FutureWarning)

class YoloDetector:
    def __init__(self, yolo_config):

        self.cfg = yolo_config
        self.model = YOLO(self.cfg["version"])
        self.model.to(self.cfg["device"])
        self.imgsz          = self.cfg.get("imgsz")
        self.classes        = self.cfg.get("classes")
        self.conf_global    = self.cfg.get("conf")
        self.conf_per_class = self.cfg.get("conf_per_class")

    def run(self, img):

        frame = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.model(
            frame,
            classes=self.classes,
            conf=self.conf_global,
            imgsz=self.imgsz,
            verbose=False
        )

        r = results[0]
        boxes = r.boxes.xyxy.cpu().numpy()
        class_ids = r.boxes.cls.cpu().numpy().astype(int)
        confidences = r.boxes.conf.cpu().numpy()

        detections = []
        for box, cls, conf in zip(boxes, class_ids, confidences):
            thr = self.conf_per_class.get(cls, self.conf_global)
            if conf >= thr:
                x1, y1, x2, y2 = box
                detections.append((
                    int(x1), int(y1), int(x2), int(y2),
                    cls,
                    float(conf)
                ))
        return detections