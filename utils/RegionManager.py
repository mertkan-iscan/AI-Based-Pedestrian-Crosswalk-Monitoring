import itertools
import json
from pathlib import Path
from utils.objects.CrosswalkPack import CrosswalkPack

class RegionManager:

    def __init__(self, polygons_file=None):
        self.polygons_file = polygons_file
        self.crosswalk_packs = []

        self.other_regions = {
            "detection_blackout": [],
            "road": [],
            "sidewalk": [],
            "deletion_area": [],
            "deletion_line": [],
            "crop_area": []
        }

        if self.polygons_file:
            self.load_polygons()

    def load_polygons(self):
        if not self.polygons_file:
            return
        self._load_from_file(self.polygons_file)

        # ----- BEGIN COUNTER RESET LOGIC -----
        if self.crosswalk_packs:
            max_pid = max(pack.id for pack in self.crosswalk_packs)
        else:
            max_pid = 0
        CrosswalkPack._pid_counter = itertools.count(max_pid + 1)

        poly_ids = []
        for pack in self.crosswalk_packs:
            if pack.crosswalk:
                poly_ids.append(pack.crosswalk["id"])
            poly_ids.extend(p["id"] for p in pack.pedes_wait)
            poly_ids.extend(p["id"] for p in pack.car_wait)
            poly_ids.extend(tl["id"] for tl in pack.traffic_light)
        if poly_ids:
            max_poly = max(poly_ids)
        else:
            max_poly = 0
        CrosswalkPack._poly_counter = itertools.count(max_poly + 1)

    def save_polygons(self):
        if not self.polygons_file:
            raise ValueError("polygons_file is undefined")
        self._save_to_file(self.polygons_file)

    def add_polygon(self, poly: dict):
        rtype = poly.get("type")
        pts = poly.get("points", [])
        if rtype in self.other_regions:
            self.add_other_region(rtype, pts)
        else:
            raise ValueError(f"RegionManager.add_polygon: unsupported type '{rtype}'")

    def clear_all(self):
        self.crosswalk_packs.clear()
        for lst in self.other_regions.values():
            lst.clear()

    def new_pack(self):
        pack = CrosswalkPack()
        self.crosswalk_packs.append(pack)
        return pack

    def add_other_region(self, region_type, points):
        existing_ids = [poly["id"] for poly in self.other_regions[region_type]]
        poly_id = max(existing_ids, default=0) + 1
        self.other_regions[region_type].append({"id": poly_id, "points": points})

    def _load_from_file(self, file_path):
        p = Path(file_path)
        if not p.exists() or p.stat().st_size == 0:
            self.crosswalk_packs = []
            for k in self.other_regions:
                self.other_regions[k] = []
            return
        raw = p.read_text().strip()
        if not raw:
            self.crosswalk_packs = []
            for k in self.other_regions:
                self.other_regions[k] = []
            return
        data = json.loads(raw)
        raw_packs = data.get("crosswalk_packs", [])
        self.crosswalk_packs = []
        for rp in raw_packs:
            pack = CrosswalkPack.from_dict(rp)
            tl_list = []
            nested = rp.get("traffic_light", {})
            for lt in ("vehicle", "pedestrian"):
                colors = nested.get(lt, {})
                for sc, ent in colors.items():
                    tl_list.append({
                        "id": pack.id,
                        "center": ent.get("center"),
                        "radius": ent.get("radius"),
                        "light_type": lt,
                        "signal_color": sc
                    })
            arr = rp.get("traffic_lights", [])
            for entry in arr:
                lights = entry.get("lights", {})
                for sc, ent in lights.items():
                    tl_list.append({
                        "id": entry.get("id"),
                        "center": ent.get("center"),
                        "radius": ent.get("radius"),
                        "light_type": entry.get("type"),
                        "signal_color": sc
                    })
            pack.traffic_light = tl_list
            self.crosswalk_packs.append(pack)
        for k in self.other_regions:
            self.other_regions[k] = data.get(k, [])

    def overlay_regions(self, image, alpha=0.4):
        import cv2, numpy as np
        area_colors = {
            "detection_blackout": (50, 50, 50),
            "crosswalk": (0, 255, 255),
            "road": (50, 50, 50),
            "sidewalk": (255, 255, 0),
            "car_wait": (255, 102, 102),
            "pedes_wait": (0, 153, 0),
            "traffic_light": (0, 0, 255),
            "deletion_area": (255, 0, 255),
            "deletion_line": (0, 255, 255),
            "crop_area": (0, 255, 0)  # Green for crop area
        }
        overlay = image.copy()

        def _fill(pts, col):
            arr = np.asarray(pts, np.int32).reshape((-1, 1, 2))
            cv2.fillPoly(overlay, [arr], col)

        def _draw_line(pts, col):
            arr = np.asarray(pts, np.int32).reshape((-1, 1, 2))
            cv2.polylines(overlay, [arr], False, col, 5)

        for pack in self.crosswalk_packs:
            if pack.crosswalk:
                _fill(pack.crosswalk.get("points", []), area_colors["crosswalk"])
            for p in pack.pedes_wait:
                _fill(p.get("points", []), area_colors["pedes_wait"])
            for p in pack.car_wait:
                _fill(p.get("points", []), area_colors["car_wait"])
            for tl in pack.traffic_light:
                c = tl.get("center")
                r = tl.get("radius")
                if isinstance(c, (list, tuple)) and r is not None:
                    cv2.circle(overlay, tuple(c), r, area_colors["traffic_light"], -1)
        for rtype, lst in self.other_regions.items():
            col = area_colors.get(rtype, (255, 0, 0))
            for poly in lst:
                if rtype == "deletion_line":
                    _draw_line(poly.get("points", []), col)
                elif rtype == "crop_area":
                    arr = np.asarray(poly.get("points", []), np.int32).reshape((-1, 1, 2))
                    cv2.rectangle(overlay, tuple(arr[0][0]), tuple(arr[1][0]), col, 2)
                else:
                    _fill(poly.get("points", []), col)
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)
        return image

    def _save_to_file(self, file_path):
        data = {"crosswalk_packs": []}
        for pack in self.crosswalk_packs:
            pd = {
                "id": pack.id,
                "crosswalk": pack.crosswalk.copy() if pack.crosswalk else None,
                "car_wait": [p.copy() for p in pack.car_wait],
                "pedes_wait": [p.copy() for p in pack.pedes_wait]
            }
            arr = []
            for tl in pack.traffic_light:
                entry = next((e for e in arr if e["id"] == tl["id"] and e["type"] == tl["light_type"]), None)
                if not entry:
                    entry = {"id": tl["id"], "type": tl["light_type"], "lights": {}}
                    arr.append(entry)
                entry["lights"][tl["signal_color"]] = {"center": tl.get("center"), "radius": tl.get("radius")}
            if arr:
                pd["traffic_lights"] = arr
            data["crosswalk_packs"].append(pd)
        data.update(self.other_regions)
        Path(file_path).write_text(json.dumps(data, indent=2))

    @property
    def region_polygons(self):
        flattened = []
        for pack in self.crosswalk_packs:
            if pack.crosswalk:
                p = pack.crosswalk.copy()
                p["type"] = "crosswalk"
                p["pack_id"] = pack.id
                flattened.append(p)
            for poly in pack.pedes_wait:
                p = poly.copy()
                p["type"] = "pedes_wait"
                p["pack_id"] = pack.id
                flattened.append(p)
            for poly in pack.car_wait:
                p = poly.copy()
                p["type"] = "car_wait"
                p["pack_id"] = pack.id
                flattened.append(p)
            for tl in pack.traffic_light:
                circle = {
                    "id": tl["id"],
                    "type": "traffic_light",
                    "pack_id": pack.id,
                    "center": tl.get("center"),
                    "radius": tl.get("radius"),
                    "light_type": tl.get("light_type"),
                    "signal_color": tl.get("signal_color")
                }
                flattened.append(circle)
        for rtype, lst in self.other_regions.items():
            for poly in lst:
                p = poly.copy()
                p["type"] = rtype
                p["pack_id"] = None
                flattened.append(p)
        return flattened

    def delete_pack(self, pack_id: int) -> bool:
        for idx, pack in enumerate(self.crosswalk_packs):
            if pack.id == pack_id:
                del self.crosswalk_packs[idx]
                return True
        return False

    def delete_polygon(self, region_type: str, poly_id: int, pack_id: int = None) -> bool:
        pack = None
        if pack_id is not None:
            pack = next((p for p in self.crosswalk_packs if p.id == pack_id), None)

        if region_type == "crosswalk":
            if pack and pack.crosswalk and pack.crosswalk.get("id") == poly_id:
                pack.crosswalk = None
                return True
            return False

        if region_type in ("car_wait", "pedes_wait"):
            if not pack:
                return False
            attr = "car_wait" if region_type == "car_wait" else "pedes_wait"
            original = len(getattr(pack, attr))
            filtered = [poly for poly in getattr(pack, attr) if poly.get("id") != poly_id]
            setattr(pack, attr, filtered)
            return len(filtered) != original

        if region_type == "traffic_light":
            if not pack:
                return False
            original = len(pack.traffic_light)
            pack.traffic_light = [
                tl for tl in pack.traffic_light
                if tl.get("id") != poly_id
            ]
            return len(pack.traffic_light) != original

        if region_type in self.other_regions:
            original = len(self.other_regions[region_type])
            self.other_regions[region_type] = [
                poly for poly in self.other_regions[region_type]
                if poly.get("id") != poly_id
            ]
            return len(self.other_regions[region_type]) != original

        return False
