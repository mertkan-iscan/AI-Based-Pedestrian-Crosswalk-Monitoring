# ConfigManager.py

import yaml
import os

class ConfigManager:
    DEFAULT_CONFIG_PATH = "resources/config.yml"

    def __init__(self, config_path=None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        if not os.path.exists(self.config_path):
            self.create_default_config()
        self.load_config()

    def create_default_config(self):
        default_config = {

        }
        with open(self.config_path, 'w') as file:
            yaml.dump(default_config, file)

    def load_config(self):
        with open(self.config_path, 'r') as file:
            self.config = yaml.safe_load(file)



    def get_yolo_config(self):
        return self.config.get("yolo", {})

    def get_database_config(self):
        return self.config.get("database", {})

    def get_deepsort_config(self):
        return self.config.get("deepsort", {})

    def get_player_config(self):
        return self.config.get("player", {})

    def get_detection_config(self):
        return self.config.get("detection_thread", {})

    def get_crosswalk_monitor_config(self):
        return self.config.get("crosswalk_monitor", {})



    def get_detection_fps(self):
        return self.get_detection_config().get("detection_fps")

    def get_delay_seconds(self):
        return self.get_detection_config().get("delay_seconds")

    def get_traffic_light_fps(self):
        return self.get_crosswalk_monitor_config().get("traffic_light_fps")



    def update_config(self, section, parameter, value):
        if section in self.config and parameter in self.config[section]:
            self.config[section][parameter] = value
            self.save_config()
        else:
            raise KeyError(f"Invalid configuration parameter: {section}.{parameter}")

    def save_config(self):
        with open(self.config_path, 'w') as file:
            yaml.dump(self.config, file)
