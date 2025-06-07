import yaml
import os
import json

LOCATIONS_JSON = "resources/locations.json"
GLOBAL_CONFIG_PATH = "resources/config.yml"

class ConfigManager:
    def __init__(self, location: dict = None):
        self.location = location
        self.global_config = self._load_global_config()
        self.locations = self._load_locations()
        # If location is provided, use its dict directly (must be from loaded locations)
        self._location_entry = None
        if location is not None:
            self._location_entry = self._find_location_entry(location)

    def _load_global_config(self):
        if not os.path.exists(GLOBAL_CONFIG_PATH):
            self._create_empty_global_config()
        with open(GLOBAL_CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f) or {}

    def _create_empty_global_config(self):
        empty = {
            "yolo": {},
            "deepsort": {},
            "player": {},
            "detection_thread": {},
            "crosswalk_monitor": {},
        }
        with open(GLOBAL_CONFIG_PATH, 'w') as f:
            yaml.dump(empty, f)

    @staticmethod
    def default_config():
        return {
            "yolo": {
                "device": "cuda",
                "version": "yolov5m.pt",
                "imgsz": 640,
                "conf": 0.50,
                "classes": [0, 1, 2, 3, 5, 7],
                "conf_per_class": {
                    0: 0.50,
                    1: 0.70,
                    2: 0.60
                }
            },
            "deepsort": {
                "max_disappeared": 40,
                "max_distance": 10,
                "device": "cuda",
                "appearance_weight": 0.4,
                "motion_weight": 0.4,
                "iou_weight": 0.2,
                "nn_budget": 100
            },
            "player": {},
            "detection_thread": {
                "detection_fps": 10,
                "delay_seconds": 5.0,
                "enable_mot_writer": False
            },
            "crosswalk_monitor": {
                "traffic_light_fps": 20
            }
        }

    def _load_locations(self):
        if not os.path.exists(LOCATIONS_JSON):
            with open(LOCATIONS_JSON, 'w') as f:
                json.dump([], f, indent=4)
            return []
        with open(LOCATIONS_JSON, 'r') as f:
            return json.load(f)

    def _find_location_entry(self, location):
        # Match by name (case-insensitive)
        name = location.get("name", "").strip().lower()
        for loc in self.locations:
            if loc.get("name", "").strip().lower() == name:
                return loc
        return None

    def _get_config_section(self, section):
        # Try per-location config first
        if self._location_entry:
            config = self._location_entry.get("config", {})
            if section in config:
                return config[section]
        # Fallback to global config
        return self.global_config.get(section, {})

    def get_yolo_config(self):
        return self._get_config_section("yolo")

    def get_database_config(self):
        return self._get_config_section("database")

    def get_deepsort_config(self):
        return self._get_config_section("deepsort")

    def get_player_config(self):
        return self._get_config_section("player")

    def get_detection_config(self):
        return self._get_config_section("detection_thread")

    def get_crosswalk_monitor_config(self):
        return self._get_config_section("crosswalk_monitor")

    def get_detection_fps(self):
        return self.get_detection_config().get("detection_fps")

    def get_delay_seconds(self):
        return self.get_detection_config().get("delay_seconds")

    def get_traffic_light_fps(self):
        return self.get_crosswalk_monitor_config().get("traffic_light_fps")

    def update_config(self, section, parameter, value):
        if self._location_entry is not None:
            # Per-location update
            if "config" not in self._location_entry:
                self._location_entry["config"] = {}
            if section not in self._location_entry["config"]:
                self._location_entry["config"][section] = {}
            self._location_entry["config"][section][parameter] = value
            self._save_locations()
        else:
            # Update global config
            if section not in self.global_config:
                self.global_config[section] = {}
            self.global_config[section][parameter] = value
            self._save_global_config()

    def _save_global_config(self):
        with open(GLOBAL_CONFIG_PATH, 'w') as f:
            yaml.dump(self.global_config, f)

    def _save_locations(self):
        with open(LOCATIONS_JSON, 'w') as f:
            json.dump(self.locations, f, indent=4)

