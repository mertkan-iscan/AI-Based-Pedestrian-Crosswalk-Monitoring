import cv2
import numpy as np

class Region:
    def __init__(self, points, homography_inv=None):
        valid = isinstance(points, (list, tuple)) and len(points) >= 3
        if not valid:
            raise ValueError("Region polygon must be a list of at least 3 points")
        arr = np.array(points, dtype=np.float32)
        self.contour = arr if arr.ndim == 3 else arr.reshape(-1, 1, 2)
        x, y, w, h = cv2.boundingRect(self.contour)
        self.bbox = (x, y, x + w, y + h)
        self.homography_inv = homography_inv

    def contains(self, pt_world):
        if self.homography_inv is not None:
            vec = np.array([pt_world[0], pt_world[1], 1.0], dtype=float)
            dst = self.homography_inv @ vec
            px, py = dst[0] / dst[2], dst[1] / dst[2]
        else:
            px, py = pt_world
        x, y = int(px), int(py)
        x0, y0, x1, y1 = self.bbox
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return False
        return cv2.pointPolygonTest(self.contour, (x, y), False) >= 0