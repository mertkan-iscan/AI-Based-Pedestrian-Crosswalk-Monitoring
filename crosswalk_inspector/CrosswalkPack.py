import itertools

class CrosswalkPack:
    _pid_counter = itertools.count(1)          # pack-level ids
    _poly_counter = itertools.count(1)         # polygon-level ids

    def __init__(self, id, crosswalk, pedes_wait, car_wait, traffic_light):
        self.id = id
        self.crosswalk = crosswalk
        self.pedes_wait = pedes_wait
        self.car_wait = car_wait
        self.traffic_light = traffic_light
        self.is_signalized = bool(traffic_light)

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
        pedes = data.get("pedes_wait", [])
        cars  = data.get("car_wait", [])
        tls   = data.get("traffic_lights", [])
        return cls(
            data.get("id"),
            data.get("crosswalk"),
            pedes,
            cars,
            tls
        )
