import cv2
import numpy as np
import json
import os

points = []
region_polygons = []
current_region_type = "crosswalk"

region_json_file = None

area_colors = {
    "crosswalk": (0, 255, 255),
    "road": (50, 50, 50),
    "sidewalk": (255, 255, 0)
}

def set_region_file(file_path):

    global region_json_file
    region_json_file = file_path
    print(f"Polygon file set to {region_json_file}")

def load_polygons():

    global region_polygons, region_json_file
    if not region_json_file:
        print("No polygon file specified.")
        return
    if os.path.exists(region_json_file):
        with open(region_json_file, "r") as f:
            region_polygons = json.load(f)
        print(f"Loaded polygons from {region_json_file}")
    else:

        region_polygons.clear()
        print(f"No existing polygon file at {region_json_file}. Starting fresh.")

def save_polygons():

    global region_json_file
    if not region_json_file:
        print("No polygon file specified. Cannot save.")
        return
    with open(region_json_file, "w") as f:
        json.dump(region_polygons, f, indent=4)
    print(f"Polygon data saved to {region_json_file}")

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
