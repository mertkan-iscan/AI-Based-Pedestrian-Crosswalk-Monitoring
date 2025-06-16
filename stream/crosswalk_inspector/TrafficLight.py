import cv2
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any

class TrafficLight:
    def __init__(self, pack_id: int, light_id: int, light_type: str, lights_config: Dict[str, Dict[str, Any]]):
        self.pack_id = pack_id
        self.id = light_id
        self.type = light_type
        self.lights = lights_config
        self.crops: Dict[str, np.ndarray] = {}
        self.status: Optional[str] = None
        self.last_update: Optional[datetime] = None

    @classmethod
    def from_dict(cls, pack_id: int, data: dict):
        return cls(
            pack_id,
            data["id"],
            data["type"],
            data["lights"]
        )

    def crop_regions(self, frame: np.ndarray) -> Dict[str, np.ndarray]:
        self.crops.clear()
        for color, cfg in self.lights.items():
            cx, cy = int(cfg["center"][0]), int(cfg["center"][1])
            r = int(cfg["radius"])
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.circle(mask, (cx, cy), r, 255, -1)
            self.crops[color] = cv2.bitwise_and(frame, frame, mask=mask)
        return self.crops

    def update_status(self, result) -> Optional[str]:
        self.status = result
        self.last_update = datetime.now()
        return self.status
