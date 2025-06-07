import json
import os
import unicodedata
import re
from utils.ConfigManager import ConfigManager

class LocationManager:
    CONFIG_FILE = "resources/locations.json"
    POLYGONS_DIR = os.path.join("resources", "location_regions")

    @staticmethod
    def _ensure_polygons_dir():
        if not os.path.exists(LocationManager.POLYGONS_DIR):
            os.makedirs(LocationManager.POLYGONS_DIR)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        nkfd = unicodedata.normalize("NFKD", name)
        ascii_str = "".join(c for c in nkfd if not unicodedata.combining(c))
        ascii_str = ascii_str.lower()
        ascii_str = ascii_str.replace(" ", "_")
        ascii_str = re.sub(r"[^a-z0-9_]", "", ascii_str)
        return ascii_str

    def load_locations(self):
        if not os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, "w") as f:
                json.dump([], f, indent=4)
            locations = []
        else:
            with open(self.CONFIG_FILE, "r") as f:
                locations = json.load(f)

        self._ensure_polygons_dir()

        updated = False
        for loc in locations:
            path = loc.get("polygons_file")
            if not path or not os.path.exists(path):
                base = self._sanitize_filename(loc["name"])
                new_fname = f"region_polygons_{base}.json"
                new_path = os.path.join(self.POLYGONS_DIR, new_fname)
                if not os.path.exists(new_path):
                    with open(new_path, "w") as pf:
                        pf.write("")  # empty JSON file
                loc["polygons_file"] = new_path
                updated = True

        if updated:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(locations, f, indent=4)
        return locations

    def add_location(self, location: dict):
        locations = self.load_locations()
        if any(loc['name'].lower() == location['name'].lower() for loc in locations):
            raise ValueError(f"Location name '{location['name']}' already exists.")
        self._ensure_polygons_dir()
        filename = f"region_polygons_{self._sanitize_filename(location['name'])}.json"
        file_path = os.path.join(self.POLYGONS_DIR, filename)
        location['polygons_file'] = file_path
        if "config" not in location:
            location["config"] = ConfigManager.default_config()
        with open(file_path, "w") as pf:
            pf.write("")
        locations.append(location)
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(locations, f, indent=4)
        print(f"Added location: {location['name']}")

    def delete_location(self, location: dict):
        locations = self.load_locations()
        updated = [loc for loc in locations if loc != location]
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(updated, f, indent=4)
        print(f"Deleted location: {location['name']}")

        polygons_file = location.get("polygons_file")
        if polygons_file and os.path.exists(polygons_file):
            os.remove(polygons_file)
            print(f"Deleted polygons file: {polygons_file}")

    def update_location(self, old_location: dict, new_location: dict):
        locations = self.load_locations()
        orig_name = old_location['name'].lower()
        new_name = new_location['name'].lower()
        for loc in locations:
            name = loc['name'].lower()
            if name == new_name and name != orig_name:
                raise ValueError(f"Location name '{new_location['name']}' already exists.")

        found = False
        for idx, loc in enumerate(locations):
            if loc['name'].lower() == orig_name:
                self._ensure_polygons_dir()
                base = self._sanitize_filename(new_location['name'])
                new_fname = f"region_polygons_{base}.json"
                new_path = os.path.join(self.POLYGONS_DIR, new_fname)
                old_path = loc.get('polygons_file')
                if old_path and os.path.exists(old_path):
                    os.rename(old_path, new_path)
                else:
                    with open(new_path, 'w') as pf:
                        pf.write("")
                new_location['polygons_file'] = new_path
                if "config" not in new_location:
                    new_location["config"] = old_location.get("config", ConfigManager.default_config())
                locations[idx] = new_location
                found = True
                break

        if not found:
            raise ValueError(f"Original location '{old_location['name']}' not found.")
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(locations, f, indent=4)
        print(f"Updated location '{old_location['name']}' → '{new_location['name']}'")
