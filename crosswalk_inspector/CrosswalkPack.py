from typing import List, Dict
from detection.DetectedObject import DetectedObject

class CrosswalkPack:
    def __init__(self, region_polygons: List[Dict]):
        """
        region_polygons: your RegionEditor.region_polygons,
                         each dict has keys "type", "points", and "id".
        """
        self.region_polygons = region_polygons
        self._group = self._group_polygons()

        # convenience refs
        self.crosswalk_polys = self._group.get("crosswalk", [])
        self.ped_wait_polys = self._group.get("pedes_wait", [])
        self.car_wait_polys = self._group.get("car_wait", [])
        self.traffic_light_polys = self._group.get("traffic_light", [])
        self.selected_traffic_light_id = None

        # sanity checks
        if len(self.crosswalk_polys) != 1:
            raise ValueError("Expected exactly 1 crosswalk region")
        if len(self.ped_wait_polys) < 2:
            raise ValueError("Expected at least 2 pedestrian‑wait regions")
        if len(self.car_wait_polys) < 1:
            raise ValueError("Expected at least 1 car‑wait region")
        if len(self.traffic_light_polys) < 1:
            raise ValueError("Expected at least 1 traffic‑light region")

    def _group_polygons(self) -> Dict[str, List[Dict]]:
        d = {}
        for poly in self.region_polygons:
            typ = poly["type"]
            d.setdefault(typ, []).append(poly)
        return d

    def set_traffic_light_id(self, polygon_id: int):
        """Choose which traffic‑light polygon to use for color detection."""
        ids = [p["id"] for p in self.traffic_light_polys]
        if polygon_id not in ids:
            raise ValueError(f"No traffic_light region with id={polygon_id}")
        self.selected_traffic_light_id = polygon_id

    def get_traffic_light_polygon(self) -> Dict:
        """Returns the polygon dict for the selected traffic light side."""
        if self.selected_traffic_light_id is None:
            raise ValueError("Traffic light not set; call set_traffic_light_id() first")
        for poly in self.traffic_light_polys:
            if poly["id"] == self.selected_traffic_light_id:
                return poly

    def evaluate(self,
                 detected_objects: List[DetectedObject],
                 traffic_light_color: str
                 ) -> Dict[str, List[int]]:
        """
        When light is red, returns:
          - cars_in_crosswalk:   [IDs]
          - cars_not_in_car_wait: [IDs]
          - pedestrians_waiting:  [IDs]
        """
        res = {
            "cars_in_crosswalk": [],
            "cars_not_in_car_wait": [],
            "pedestrians_waiting": []
        }
        if traffic_light_color.lower() != "red":
            return res

        for obj in detected_objects:
            # treat cars and trucks both as vehicles
            if obj.object_type in ("car", "truck"):
                if obj.region == "crosswalk":
                    res["cars_in_crosswalk"].append(obj.id)
                elif obj.region != "car_wait":
                    res["cars_not_in_car_wait"].append(obj.id)

            elif obj.object_type == "person":
                if obj.region == "pedes_wait":
                    res["pedestrians_waiting"].append(obj.id)

        return res
