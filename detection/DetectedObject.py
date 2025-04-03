class DetectedObject:

    CLASS_NAMES = {0: "person", 2: "car", 3: "truck"}

    def __init__(self,
                 object_id,
                 object_type,
                 centroid_coordinate,
                 foot_coordinate,
                 region):

        self.id = object_id
        self.object_type = object_type

        self.centroid_coordinate = centroid_coordinate
        #only person class has foot coordinates
        self.foot_coordinate = foot_coordinate if object_type == "person" else None

        self.region = region

    def update_foot(self, new_foot_coordinate):
        if self.object_type == "person":
            self.foot_coordinate = new_foot_coordinate

    def update_centroid(self, new_centroid_coordinate):
        self.centroid_coordinate = new_centroid_coordinate

    def __repr__(self):
        return (f"DetectedObject(ID={self.id},"
                f"type={self.object_type}, "
                f"region={self.region},"
                f"centroid={self.centroid_coordinate}, "
                f"path={self.path_coordinates})"
                f"foot={self.foot_coordinate})"
                )