class EntityState:
    def __init__(self, track_id, class_name):
        self.id = track_id
        self.class_name = class_name
        self.current_regions = set()
        self._entries = {}
        self.durations = {}

    def update_region(self, name, inside, now):
        if inside and name not in self._entries:
            self._entries[name] = now
        elif not inside and name in self._entries:
            start = self._entries.pop(name)
            self.durations[name] = (now - start).total_seconds()
        if inside:
            self.current_regions.add(name)
        else:
            self.current_regions.discard(name)