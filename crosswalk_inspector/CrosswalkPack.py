import itertools

class CrosswalkPack:
    _pid_counter = itertools.count(1)          # pack-level ids
    _poly_counter = itertools.count(1)         # polygon-level ids

    def __init__(self):
        self.id = next(self._pid_counter)
        self.crosswalk = None                  # {"id": …, "points": […]} or None
        self.pedes_wait = []                   # list of dicts
        self.car_wait = []                     # list of dicts
        self.traffic_light = []                # list of dicts

    @staticmethod
    def _new_polygon(points):
        return {"id": next(CrosswalkPack._poly_counter), "points": points}

    def set_crosswalk(self, points):
        self.crosswalk = self._new_polygon(points)

    def add_pedes_wait(self, points):
        self.pedes_wait.append(self._new_polygon(points))

    def add_car_wait(self, points):
        self.car_wait.append(self._new_polygon(points))

    def add_traffic_light(self, points):
        self.traffic_light.append(self._new_polygon(points))

    def to_dict(self):
        return {
            "id": self.id,
            "crosswalk": self.crosswalk,
            "pedes_wait": self.pedes_wait,
            "car_wait": self.car_wait,
            "traffic_light": self.traffic_light,
        }

    @classmethod
    def from_dict(cls, data):
        # Support missing traffic_light key for new format
        obj = cls.__new__(cls)
        obj.id = data.get("id")
        obj.crosswalk = data.get("crosswalk")
        obj.pedes_wait = data.get("pedes_wait", [])
        obj.car_wait = data.get("car_wait", [])
        obj.traffic_light = data.get("traffic_light", [])
        return obj
