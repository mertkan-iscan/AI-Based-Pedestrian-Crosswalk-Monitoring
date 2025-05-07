import json
from pathlib import Path
from crosswalk_inspector.CrosswalkPack import CrosswalkPack
from region.RegionIndexer import RegionIndexer


class RegionEditor:
    def __init__(self, polygons_file=None):
        # Path to *.json* on disk (may be None for in-memory use)
        self.polygons_file = polygons_file

        # Data containers
        self.crosswalk_packs = []              # list[CrosswalkPack]
        self.other_regions = {                 # stand-alone regions
            "detection_blackout": [],
            "road": [],
            "sidewalk": [],
            "deletion_area": []
        }

        # Auto-load if a file was given
        if self.polygons_file:
            self.load_polygons()

    # ---------- Public helpers expected elsewhere in the GUI ----------

    def load_polygons(self):
        if not self.polygons_file:
            return
        self._load_from_file(self.polygons_file)

    def save_polygons(self):
        if not self.polygons_file:
            raise ValueError("polygons_file is undefined")
        self._save_to_file(self.polygons_file)

    # ---------- Region-creation API (used by RegionEditorDialog, etc.) ----------

    def new_pack(self):
        pack = CrosswalkPack()
        self.crosswalk_packs.append(pack)
        return pack

    def add_other_region(self, region_type, points):
        poly_id = len(self.other_regions[region_type]) + 1
        self.other_regions[region_type].append({"id": poly_id, "points": points})

    # ---------- Point-lookup utility ----------

    def build_indexer(self):
        return RegionIndexer(self.crosswalk_packs, self.other_regions)

    # ---------- Private I/O ----------

    def _save_to_file(self, file_path):
        data = {
            "crosswalk_packs": [p.to_dict() for p in self.crosswalk_packs],
            **self.other_regions
        }
        Path(file_path).write_text(json.dumps(data, indent=2))

    def _load_from_file(self, file_path):
        p = Path(file_path)

        # Empty or non-existent file → start with nothing
        if not p.exists() or p.stat().st_size == 0:
            self.crosswalk_packs = []
            for key in self.other_regions:
                self.other_regions[key] = []
            return

        raw = p.read_text().strip()
        if not raw:
            self.crosswalk_packs = []
            for key in self.other_regions:
                self.other_regions[key] = []
            return

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {file_path}: {exc}") from None

        # Legacy format “[]” or any flat list → treat as empty
        if isinstance(data, list):
            self.crosswalk_packs = []
            for key in self.other_regions:
                self.other_regions[key] = []
            return

        # New nested format
        self.crosswalk_packs = [
            CrosswalkPack.from_dict(d) for d in data.get("crosswalk_packs", [])
        ]
        for key in self.other_regions:
            self.other_regions[key] = data.get(key, [])

    def overlay_regions(self, image, alpha=0.4):
        import cv2
        import numpy as np

        area_colors = {
            "detection_blackout": (50, 50, 50),
            "crosswalk": (0, 255, 255),
            "road": (50, 50, 50),
            "sidewalk": (255, 255, 0),
            "car_wait": (255, 102, 102),
            "pedes_wait": (0, 153, 0),
            "traffic_light": (0, 0, 255),
            "deletion_area": (255, 0, 255)
        }

        overlay = image.copy()

        def _fill(poly_points, color):
            pts = np.asarray(poly_points, dtype=np.int32).reshape((-1, 1, 2))
            cv2.fillPoly(overlay, [pts], color)

        for pack in self.crosswalk_packs:
            if pack.crosswalk:
                _fill(pack.crosswalk["points"], area_colors["crosswalk"])
            for poly in pack.pedes_wait:
                _fill(poly["points"], area_colors["pedes_wait"])
            for poly in pack.car_wait:
                _fill(poly["points"], area_colors["car_wait"])
            for poly in pack.traffic_light:
                _fill(poly["points"], area_colors["traffic_light"])

        for rtype, plist in self.other_regions.items():
            color = area_colors.get(rtype, (255, 0, 0))
            for poly in plist:
                _fill(poly["points"], color)

        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)
        return image


    @property
    def region_polygons(self):

        flattened = []

        # Crosswalk-pack polygons
        for pack in self.crosswalk_packs:
            if pack.crosswalk:
                poly = pack.crosswalk.copy()
                poly["type"] = "crosswalk"
                poly["pack_id"] = pack.id
                flattened.append(poly)

            for source, rtype in (
                (pack.pedes_wait, "pedes_wait"),
                (pack.car_wait,   "car_wait"),
                (pack.traffic_light, "traffic_light"),
            ):
                for poly in source:
                    p = poly.copy()
                    p["type"] = rtype
                    p["pack_id"] = pack.id
                    flattened.append(p)

        # Stand-alone regions
        for rtype, plist in self.other_regions.items():
            for poly in plist:
                p = poly.copy()
                p["type"] = rtype
                p["pack_id"] = None
                flattened.append(p)

        return flattened

    def add_polygon(self, poly):
        rtype = poly.get("type")
        points = poly.get("points")
        if rtype is None or points is None:
            raise ValueError("polygon dict needs 'type' and 'points'")

        # Crosswalk-pack members
        if rtype in {"crosswalk", "pedes_wait", "car_wait", "traffic_light"}:
            pack_id = poly.get("pack_id")
            pack = None
            if pack_id is not None:
                pack = next((p for p in self.crosswalk_packs if p.id == pack_id), None)
            if pack is None:
                pack = self.new_pack()

            # Create polygon with a fresh id
            new_poly = pack._new_polygon(points)

            if rtype == "crosswalk":
                pack.crosswalk = new_poly
            elif rtype == "pedes_wait":
                pack.pedes_wait.append(new_poly)
            elif rtype == "car_wait":
                pack.car_wait.append(new_poly)
            else:  # "traffic_light"
                # attach the subtype
                new_poly["light_type"] = poly.get("light_type", "vehicle")
                pack.traffic_light.append(new_poly)

            poly.update({"id": new_poly["id"], "pack_id": pack.id})
            return new_poly["id"]

        # Stand-alone regions (unchanged)…
        if rtype in self.other_regions:
            new_id = len(self.other_regions[rtype]) + 1
            self.other_regions[rtype].append({"id": new_id, "points": points})
            poly.update({"id": new_id, "pack_id": None})
            return new_id

        raise ValueError(f"Unknown region type: {rtype}")

    def delete_polygon(self, region_type: str, polygon_id: int, pack_id=None):
        if region_type in {"crosswalk", "pedes_wait", "car_wait", "traffic_light"}:
            pack = next((p for p in self.crosswalk_packs if p.id == pack_id), None)
            if not pack:
                return False
            if region_type == "crosswalk" and pack.crosswalk and pack.crosswalk["id"] == polygon_id:
                pack.crosswalk = None
            else:
                target = getattr(pack, region_type)
                before = len(target)
                target[:] = [p for p in target if p["id"] != polygon_id]
                if len(target) == before:
                    return False
            # drop empty pack
            if not any([pack.crosswalk, pack.pedes_wait, pack.car_wait, pack.traffic_light]):
                self.crosswalk_packs = [p for p in self.crosswalk_packs if p.id != pack.id]
            return True
        if region_type in self.other_regions:
            before = len(self.other_regions[region_type])
            self.other_regions[region_type][:] = [
                p for p in self.other_regions[region_type] if p["id"] != polygon_id
            ]
            return len(self.other_regions[region_type]) < before
        return False

    def delete_pack(self, pack_id: int) -> bool:
        before = len(self.crosswalk_packs)
        self.crosswalk_packs = [p for p in self.crosswalk_packs if p.id != pack_id]
        return len(self.crosswalk_packs) < before

    def clear_all(self):
        self.crosswalk_packs.clear()
        for key in self.other_regions:
            self.other_regions[key].clear()