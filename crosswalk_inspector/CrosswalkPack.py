import itertools

class CrosswalkPack:
    _pid_counter = itertools.count(1)          # pack-level ids
    _poly_counter = itertools.count(1)         # polygon-level ids

    def __init__(self):
        self.id = next(self._pid_counter)
        self.crosswalk = None                  # {"id": …, "points": […]}
        self.pedes_wait = []                   # list of dicts
        self.car_wait = []
        self.traffic_light = []

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
        obj = cls.__new__(cls)
        obj.id = data["id"]
        obj.crosswalk = data["crosswalk"]
        obj.pedes_wait = data["pedes_wait"]
        obj.car_wait = data["car_wait"]
        obj.traffic_light = data["traffic_light"]
        return obj
