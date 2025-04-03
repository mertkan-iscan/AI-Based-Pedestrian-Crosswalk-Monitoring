import cv2
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
from ultralytics import YOLO


model = YOLO("yolov5xu.pt")
model.to("cuda")

def run_inference(img):

    frame_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    results = model(frame_rgb, classes=[0, 1, 2, 3])

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


def calculate_foot_location(bbox):

    if not (isinstance(bbox, (list, tuple)) and len(bbox) >= 4):
        raise ValueError("bbox must be a list or tuple with at least 4 elements: [x1, y1, x2, y2]")

    x1, y1, x2, y2 = bbox[:4]
    foot_x = int((x1 + x2) / 2)
    foot_y = y2

    return foot_x, foot_y