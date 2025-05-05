import cv2
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

from ultralytics import YOLO
from utils.ConfigManager import ConfigManager


config_manager = ConfigManager()
yolo_cfg = config_manager.get_yolo_config()

model = YOLO(yolo_cfg["version"])
model.to(yolo_cfg["device"])

imgsz = yolo_cfg.get("imgsz")

def run_inference(img):

    frame_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    results = model(frame_rgb, classes=[0,1,2,3,5,7], verbose=False, imgsz=imgsz)

    result = results[0]

    boxes_xyxy = result.boxes.xyxy.cpu().numpy()
    class_ids = result.boxes.cls.cpu().numpy()
    confidences = result.boxes.conf.cpu().numpy()

    detections = []
    for i, box in enumerate(boxes_xyxy):
        x1, y1, x2, y2 = box
        cls = int(class_ids[i])
        conf = float(confidences[i])
        detections.append((int(x1), int(y1), int(x2), int(y2), cls, conf))

    return detections