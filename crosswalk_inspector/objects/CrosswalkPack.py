import itertools

class CrosswalkPack:
    _pid_counter = itertools.count(1)

    def __init__(
        self,
        id=None,
        crosswalk=None,
        pedes_wait=None,
        car_wait=None,
        traffic_light=None,
    ):
        self.id = id if id is not None else next(CrosswalkPack._pid_counter)
        self.crosswalk = crosswalk
        self.pedes_wait = pedes_wait or []
        self.car_wait = car_wait or []
        # flat list of all circles, each with "id", "light_type", "signal_color", etc.
        self.traffic_light = traffic_light or []
        self.is_signalized = bool(self.traffic_light)

        # integer counter for traffic‐light groups, reset per pack
        existing_ids = [tl["id"] for tl in self.traffic_light]
        self._next_tl_id = max(existing_ids, default=0) + 1

        self._crosswalk_counter = itertools.count(1)
        self._pedes_wait_counter  = itertools.count(1)
        self._car_wait_counter    = itertools.count(1)

    def set_crosswalk(self, points):
        cid = next(self._crosswalk_counter)
        self.crosswalk = {"id": cid, "points": points}

    def add_pedes_wait(self, points):
        pid = next(self._pedes_wait_counter)
        self.pedes_wait.append({"id": pid, "points": points})

    def add_car_wait(self, points):
        wid = next(self._car_wait_counter)
        self.car_wait.append({"id": wid, "points": points})

    def add_traffic_light_group(self, light_type, lights):
        gid = self._next_tl_id
        self._next_tl_id += 1

        for color, info in lights.items():
            self.traffic_light.append({
                "id": gid,
                "light_type": light_type,
                "signal_color": color,
                "center": info["center"],
                "radius": info["radius"],
            })

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
        return cls(
            data.get("id"),
            data.get("crosswalk"),
            data.get("pedes_wait", []),
            data.get("car_wait", []),
            data.get("traffic_light", []),
        )
