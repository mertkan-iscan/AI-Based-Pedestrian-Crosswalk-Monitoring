import math

def _point_in_poly(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[(i + 1) % n]
        intersect = ((yi > y) != (yj > y)) and \
                    (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi)
        if intersect:
            inside = not inside
    return inside

class RegionIndexer:
    def __init__(self, crosswalk_packs, other_regions):
        self.crosswalk_packs = crosswalk_packs     # list[CrosswalkPack]
        self.other_regions = other_regions         # {"detection_blackout":[…], …}

    def lookup(self, point):
        for pack in self.crosswalk_packs:
            target_sets = (
                ("crosswalk", [pack.crosswalk]),
                ("pedes_wait", pack.pedes_wait),
                ("car_wait", pack.car_wait),
                ("traffic_light", pack.traffic_light),
            )
            for rtype, plist in target_sets:
                for poly in plist:
                    if _point_in_poly(point, poly["points"]):
                        return rtype, poly["id"], pack.id
        for rtype, plist in self.other_regions.items():
            for poly in plist:
                if _point_in_poly(point, poly["points"]):
                    return rtype, poly["id"], None
        return None
