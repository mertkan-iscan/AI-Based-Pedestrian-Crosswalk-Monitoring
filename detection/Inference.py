import os
import cv2
import warnings
from ultralytics import YOLO
from utils.ConfigManager import ConfigManager

warnings.filterwarnings("ignore", category=FutureWarning)

# 1) Load the YAML you actually edited
cfg_path = os.path.join(os.getcwd(), "resources/config.yml")
yolo_cfg = ConfigManager(config_path=cfg_path).get_yolo_config()

# 2) Build model
model = YOLO(yolo_cfg["version"])
model.to(yolo_cfg["device"])

# 3) Read thresholds (with fallbacks)
imgsz          = yolo_cfg.get("imgsz", 640)
classes        = yolo_cfg.get("classes", [])
conf_global    = yolo_cfg.get("conf", 0.25)
conf_per_class = yolo_cfg.get("conf_per_class", {})

def run_inference(img):
    frame = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = model(
        frame,
        classes=classes,
        conf=conf_global,  # built-in filter
        imgsz=imgsz,
        verbose=False
    )
    r = results[0]
    boxes       = r.boxes.xyxy.cpu().numpy()
    class_ids   = r.boxes.cls.cpu().numpy().astype(int)
    confidences = r.boxes.conf.cpu().numpy()

    detections = []
    for box, cls, conf in zip(boxes, class_ids, confidences):
        # per-class thr or global
        thr = conf_per_class.get(cls, conf_global)
        if conf >= thr:
            x1, y1, x2, y2 = box
            detections.append((
                int(x1), int(y1), int(x2), int(y2),
                cls,
                float(conf)
            ))
    return detections
