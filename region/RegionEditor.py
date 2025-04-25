import cv2
import numpy as np
import json
import os

class RegionEditor:

    DEFAULT_AREA_COLORS = {
        "detection_blackout": (50, 50, 50),
        "crosswalk": (0, 255, 255),
        "road": (50, 50, 50),
        "sidewalk": (255, 255, 0),
        "car_wait": (255, 102, 102),
        "pedes_wait": (0, 153, 0)
    }

    def __init__(self, region_json_file: str = None, area_colors: dict = None):
        self.region_json_file = region_json_file
        self.region_polygons = []  # list of dicts with 'type', 'points', and optional 'id'
        self.area_colors = area_colors or self.DEFAULT_AREA_COLORS.copy()

    def set_region_file(self, file_path: str):
        """Set the JSON file path for loading/saving polygons."""
        self.region_json_file = file_path
        print(f"Polygon file set to {self.region_json_file}")

    def _get_next_polygon_id(self, rtype: str) -> int:
        existing_ids = {int(poly["id"])
                        for poly in self.region_polygons
                        if poly.get("type") == rtype and 'id' in poly}
        new_id = 1
        while new_id in existing_ids:
            new_id += 1
        return new_id

    def load_polygons(self):
        """Load polygons from JSON file, assigning IDs where needed."""
        if not self.region_json_file:
            print("No polygon file specified.")
            return

        if os.path.exists(self.region_json_file):
            with open(self.region_json_file, 'r') as f:
                self.region_polygons = json.load(f)

            for poly in self.region_polygons:
                if poly.get('type') != 'detection_blackout' and 'id' not in poly:
                    poly['id'] = self._get_next_polygon_id(poly['type'])
            print(f"Loaded polygons from {self.region_json_file}")
        else:
            self.region_polygons = []
            print(f"No existing polygon file at {self.region_json_file}. Starting fresh.")

    def save_polygons(self):
        """Save current polygons to JSON file, assigning IDs where needed."""
        if not self.region_json_file:
            print("No polygon file specified. Cannot save.")
            return

        for poly in self.region_polygons:
            if poly.get('type') != 'detection_blackout' and 'id' not in poly:
                poly['id'] = self._get_next_polygon_id(poly['type'])

        with open(self.region_json_file, 'w') as f:
            json.dump(self.region_polygons, f, indent=4)
        print(f"Polygon data saved to {self.region_json_file}")

    def add_polygon(self, poly: dict):
        """Add a new polygon, assigning an ID if appropriate."""
        if poly.get('type') != 'detection_blackout' and 'id' not in poly:
            poly['id'] = self._get_next_polygon_id(poly['type'])
        self.region_polygons.append(poly)
        msg = (f"Added polygon with id: {poly['id']}"
               if poly.get('type') != 'detection_blackout'
               else "Added detection_blackout polygon (no ID assigned)")
        print(msg)

    def overlay_regions(self, img: np.ndarray, alpha: float = 0.4) -> np.ndarray:
        """Return image with semi-transparent polygon overlays."""
        overlay = img.copy()
        for poly in self.region_polygons:
            pts = np.array(poly['points'], dtype=np.int32)
            color = self.area_colors.get(poly['type'], (0, 0, 255))
            cv2.polylines(overlay, [pts], isClosed=True, color=color, thickness=2)
            cv2.fillPoly(overlay, [pts], color)
        return cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)

    def get_polygons_for_point(self, point: tuple) -> list:
        """Return list of region types whose polygons contain the point."""
        inside = []
        for poly in self.region_polygons:
            pts = np.array(poly['points'], dtype=np.int32)
            if cv2.pointPolygonTest(pts, point, False) >= 0:
                inside.append(poly['type'])
        return inside
