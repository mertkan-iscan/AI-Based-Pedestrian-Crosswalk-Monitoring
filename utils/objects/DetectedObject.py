class DetectedObject:

    CLASS_NAMES = {
        0: "person",
        1: "bicycle",
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck",
    }

    def __init__(
        self,
        object_id,
        object_type,
        bbox,
        surface_point,
        region="unknown"
    ):
        self.id = object_id
        self.object_type = object_type
        self.bbox = bbox
        self.surface_point = surface_point
        self.region = region

    def update_bbox(self, new_bbox):
        self.bbox = new_bbox

    def update_surface_point(self, new_surface_point):
        self.surface_point = new_surface_point


    def __repr__(self):
        return (
            f"DetectedObject(ID={self.id}, "
            f"type={self.object_type}, "
            f"region={self.region}, "
            f"surface_point={self.surface_point})"
        )
