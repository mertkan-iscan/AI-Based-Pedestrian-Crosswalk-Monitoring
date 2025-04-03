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
            "yolo": {
                "version": "yolov5xu.pt",
                "device": "cuda",
                "imgsz": "640"
            },
            "inference": {
                "skip_frames": 2,
                "max_latency": 0.5,
                "max_frame_gap": 5.0
            },
            "database": {
                "record_paths": False,
                "db_file": "resources/object_paths.db"
            }
        }
        with open(self.config_path, 'w') as file:
            yaml.dump(default_config, file)

    def load_config(self):
        with open(self.config_path, 'r') as file:
            self.config = yaml.safe_load(file)

    def get_yolo_config(self):
        return self.config.get("yolo", {})

    def get_inference_config(self):
        return self.config.get("inference", {})

    def get_database_config(self):
        return self.config.get("database", {})

    def update_config(self, section, parameter, value):
        if section in self.config and parameter in self.config[section]:
            self.config[section][parameter] = value
            self.save_config()
        else:
            raise KeyError(f"Invalid configuration parameter: {section}.{parameter}")

    def save_config(self):
        with open(self.config_path, 'w') as file:
            yaml.dump(self.config, file)
