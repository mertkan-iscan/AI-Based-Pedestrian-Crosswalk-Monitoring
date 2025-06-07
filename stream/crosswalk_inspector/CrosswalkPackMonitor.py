from stream.crosswalk_inspector.EntityState import EntityState
from stream.crosswalk_inspector.Region import Region


class CrosswalkPackMonitor:
    def __init__(self, pack, homography_inv=None):
        self.pack_id = pack.id
        self.crosswalk = Region(pack.crosswalk['points'], homography_inv)
        self.ped_wait = [Region(p['points'], homography_inv) for p in pack.pedes_wait]
        self.car_wait = [Region(p['points'], homography_inv) for p in pack.car_wait]
        self.entities = {}

    def process_frame(self, detections, timestamp):
        for det in detections:

            tid = det.id
            cls = det.object_type

            if tid not in self.entities:
                self.entities[tid] = EntityState(tid, cls)

            state = self.entities[tid]
            pt = getattr(det, 'surface_point', None) or getattr(det, 'raw_surface_point', None)

            if pt is None:
                continue

            for idx, region in enumerate(self.ped_wait):
                state.update_region(f"ped_wait_{idx}", region.contains(pt), timestamp)

            state.update_region("crosswalk", self.crosswalk.contains(pt), timestamp)

            for idx, region in enumerate(self.car_wait):
                state.update_region(f"car_wait_{idx}", region.contains(pt), timestamp)
