import cv2
import numpy as np
import json
import os

points = []
region_polygons = []
current_region_type = "crosswalk"

region_json_file = None

area_colors = {
    "detection_blackout": (50, 50, 50),
    "crosswalk": (0, 255, 255),
    "road": (50, 50, 50),
    "sidewalk": (255, 255, 0),
    "car_wait": (255, 102, 102),
    "pedes_wait": (0, 153, 0)
}

def set_region_file(file_path):
    global region_json_file
    region_json_file = file_path
    print(f"Polygon file set to {region_json_file}")

def get_next_polygon_id(rtype):

    existing_ids = set()
    for poly in region_polygons:
        if poly.get("type") == rtype and "id" in poly:
            try:
                existing_ids.add(int(poly["id"]))
            except ValueError:
                pass
    new_num = 1
    while new_num in existing_ids:
        new_num += 1
    return new_num

def load_polygons():
    global region_polygons, region_json_file
    if not region_json_file:
        print("No polygon file specified.")
        return

    if os.path.exists(region_json_file):
        with open(region_json_file, "r") as f:
            region_polygons = json.load(f)

        for poly in region_polygons:
            # Only assign an ID if the polygon type is not detection_blackout.
            if poly.get("type") != "detection_blackout" and 'id' not in poly:
                poly['id'] = get_next_polygon_id(poly["type"])

        print(f"Loaded polygons from {region_json_file}")
    else:
        region_polygons.clear()
        print(f"No existing polygon file at {region_json_file}. Starting fresh.")

def save_polygons():
    global region_json_file
    if not region_json_file:
        print("No polygon file specified. Cannot save.")
        return

    # Only assign an ID if the polygon type is not detection_blackout.
    for poly in region_polygons:
        if poly.get("type") != "detection_blackout" and 'id' not in poly:
            poly['id'] = get_next_polygon_id(poly["type"])

    with open(region_json_file, "w") as f:
        json.dump(region_polygons, f, indent=4)
    print(f"Polygon data saved to {region_json_file}")

def add_polygon(poly):

    if poly.get("type") != "detection_blackout" and 'id' not in poly:
        poly['id'] = get_next_polygon_id(poly["type"])
    region_polygons.append(poly)
    if poly.get("type") != "detection_blackout":
        print(f"Added polygon with id: {poly['id']}")
    else:
        print("Added detection_blackout polygon (no ID assigned)")

def overlay_regions(img, alpha=0.4):
    overlay = img.copy()
    for poly in region_polygons:
        pts = np.array(poly["points"], dtype=np.int32)
        color = area_colors.get(poly["type"], (0, 0, 255))
        cv2.polylines(overlay, [pts], isClosed=True, color=color, thickness=2)
        cv2.fillPoly(overlay, [pts], color)
    return cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)

def get_polygons_for_point(point, polygons):
    inside = []
    for poly in polygons:
        pts = np.array(poly["points"], dtype=np.int32)
        if cv2.pointPolygonTest(pts, point, False) >= 0:
            inside.append(poly["type"])
    return inside
