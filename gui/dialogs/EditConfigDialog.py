from PyQt5 import QtWidgets
from utils.ConfigManager import ConfigManager

def _list_to_str(lst):
    return ",".join(str(x) for x in lst) if isinstance(lst, list) else str(lst)

def _str_to_list(s):
    # Accept comma or space separation
    if isinstance(s, list):
        return s
    s = s.strip()
    if not s:
        return []
    # Try JSON list, fallback to comma/space
    try:
        import json
        arr = json.loads(s)
        if isinstance(arr, list):
            return arr
    except Exception:
        pass
    return [int(x) if x.isdigit() else x for x in s.replace(",", " ").split() if x]

class EditConfigDialog(QtWidgets.QDialog):
    def __init__(self, location, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Config: {location['name']}")
        self.resize(480, 600)
        self.location = location
        self.config = location.get("config", ConfigManager.default_config()).copy()
        self.fields = {}
        self._build_ui()

    def _build_ui(self):
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        frame = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(frame)

        # Yolo
        yolo = self.config.get("yolo", {})
        self.fields['yolo_device'] = QtWidgets.QLineEdit(str(yolo.get("device", "")))
        layout.addRow("YOLO Device", self.fields['yolo_device'])
        self.fields['yolo_version'] = QtWidgets.QLineEdit(str(yolo.get("version", "")))
        layout.addRow("YOLO Version", self.fields['yolo_version'])
        self.fields['yolo_imgsz'] = QtWidgets.QSpinBox()
        self.fields['yolo_imgsz'].setMaximum(9999)
        self.fields['yolo_imgsz'].setValue(int(yolo.get("imgsz", 640)))
        layout.addRow("YOLO Image Size", self.fields['yolo_imgsz'])
        self.fields['yolo_conf'] = QtWidgets.QDoubleSpinBox()
        self.fields['yolo_conf'].setSingleStep(0.01)
        self.fields['yolo_conf'].setRange(0, 1)
        self.fields['yolo_conf'].setValue(float(yolo.get("conf", 0.5)))

        layout.addRow("YOLO Default Conf", self.fields['yolo_conf'])
        self.fields['yolo_classes'] = QtWidgets.QLineEdit(_list_to_str(yolo.get("classes", [])))
        layout.addRow("YOLO Classes (comma separated)", self.fields['yolo_classes'])

        # Conf per class (flat: "0:0.5,1:0.7")
        self.conf_per_class_table = QtWidgets.QTableWidget(self)
        self.conf_per_class_table.setColumnCount(2)
        self.conf_per_class_table.setHorizontalHeaderLabels(["Class ID", "Conf"])
        self.conf_per_class_table.setEditTriggers(QtWidgets.QTableWidget.AllEditTriggers)
        self.conf_per_class_table.horizontalHeader().setStretchLastSection(True)
        self.conf_per_class_table.setMinimumHeight(120)
        # Fill with current values
        conf_per_class = yolo.get("conf_per_class", {})
        self._load_conf_per_class_table(conf_per_class)
        layout.addRow("YOLO Conf Per Class", self.conf_per_class_table)

        btn_layout = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Add")
        remove_btn = QtWidgets.QPushButton("Remove Selected")
        add_btn.clicked.connect(self._add_conf_per_class_row)
        remove_btn.clicked.connect(self._remove_selected_conf_per_class_row)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        layout.addRow("", btn_layout)

        # Deepsort
        deepsort = self.config.get("deepsort", {})
        self.fields['deepsort_max_disappeared'] = QtWidgets.QSpinBox()
        self.fields['deepsort_max_disappeared'].setMaximum(9999)
        self.fields['deepsort_max_disappeared'].setValue(int(deepsort.get("max_disappeared", 40)))
        layout.addRow("DeepSort Max Disappeared", self.fields['deepsort_max_disappeared'])
        self.fields['deepsort_max_distance'] = QtWidgets.QDoubleSpinBox()
        self.fields['deepsort_max_distance'].setMaximum(9999)
        self.fields['deepsort_max_distance'].setValue(float(deepsort.get("max_distance", 10)))
        layout.addRow("DeepSort Max Distance", self.fields['deepsort_max_distance'])
        self.fields['deepsort_device'] = QtWidgets.QLineEdit(str(deepsort.get("device", "")))
        layout.addRow("DeepSort Device", self.fields['deepsort_device'])
        self.fields['deepsort_appearance_weight'] = QtWidgets.QDoubleSpinBox()
        self.fields['deepsort_appearance_weight'].setSingleStep(0.01)
        self.fields['deepsort_appearance_weight'].setRange(0, 1)
        self.fields['deepsort_appearance_weight'].setValue(float(deepsort.get("appearance_weight", 0.4)))
        layout.addRow("DeepSort Appearance Weight", self.fields['deepsort_appearance_weight'])
        self.fields['deepsort_motion_weight'] = QtWidgets.QDoubleSpinBox()
        self.fields['deepsort_motion_weight'].setSingleStep(0.01)
        self.fields['deepsort_motion_weight'].setRange(0, 1)
        self.fields['deepsort_motion_weight'].setValue(float(deepsort.get("motion_weight", 0.4)))
        layout.addRow("DeepSort Motion Weight", self.fields['deepsort_motion_weight'])
        self.fields['deepsort_iou_weight'] = QtWidgets.QDoubleSpinBox()
        self.fields['deepsort_iou_weight'].setSingleStep(0.01)
        self.fields['deepsort_iou_weight'].setRange(0, 1)
        self.fields['deepsort_iou_weight'].setValue(float(deepsort.get("iou_weight", 0.2)))
        layout.addRow("DeepSort IOU Weight", self.fields['deepsort_iou_weight'])
        self.fields['deepsort_nn_budget'] = QtWidgets.QSpinBox()
        self.fields['deepsort_nn_budget'].setMaximum(9999)
        self.fields['deepsort_nn_budget'].setValue(int(deepsort.get("nn_budget", 100)))
        layout.addRow("DeepSort NN Budget", self.fields['deepsort_nn_budget'])

        # Detection Thread
        det = self.config.get("detection_thread", {})
        self.fields['det_fps'] = QtWidgets.QSpinBox()
        self.fields['det_fps'].setMaximum(500)
        self.fields['det_fps'].setValue(int(det.get("detection_fps", 10)))
        layout.addRow("Detection FPS", self.fields['det_fps'])

        self.fields['det_delay'] = QtWidgets.QDoubleSpinBox()
        self.fields['det_delay'].setDecimals(2)
        self.fields['det_delay'].setMaximum(100)
        self.fields['det_delay'].setValue(float(det.get("delay_seconds", 5.0)))
        layout.addRow("Detection Delay Seconds", self.fields['det_delay'])

        self.fields['enable_mot_writer'] = QtWidgets.QCheckBox()
        self.fields['enable_mot_writer'].setChecked(bool(det.get("enable_mot_writer", True)))
        layout.addRow("Enable MOT Writer", self.fields['enable_mot_writer'])

        # Crosswalk Monitor
        cwm = self.config.get("crosswalk_monitor", {})
        self.fields['cwm_tl_fps'] = QtWidgets.QSpinBox()
        self.fields['cwm_tl_fps'].setMaximum(500)
        self.fields['cwm_tl_fps'].setValue(int(cwm.get("traffic_light_fps", 20)))
        layout.addRow("Traffic Light FPS", self.fields['cwm_tl_fps'])

        # Optionally: Player/database fields can be added similarly if needed

        # Place the form into the scroll area
        scroll.setWidget(frame)

        dlg_layout = QtWidgets.QVBoxLayout(self)
        dlg_layout.addWidget(scroll)

        # Buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        dlg_layout.addWidget(buttons)

    def _load_conf_per_class_table(self, conf_per_class):
        self.conf_per_class_table.setRowCount(0)
        for k, v in sorted(conf_per_class.items()):
            row = self.conf_per_class_table.rowCount()
            self.conf_per_class_table.insertRow(row)
            id_item = QtWidgets.QTableWidgetItem(str(k))
            conf_item = QtWidgets.QTableWidgetItem(str(v))
            self.conf_per_class_table.setItem(row, 0, id_item)
            self.conf_per_class_table.setItem(row, 1, conf_item)

    def _add_conf_per_class_row(self):
        row = self.conf_per_class_table.rowCount()
        self.conf_per_class_table.insertRow(row)
        self.conf_per_class_table.setItem(row, 0, QtWidgets.QTableWidgetItem(""))
        self.conf_per_class_table.setItem(row, 1, QtWidgets.QTableWidgetItem(""))

    def _remove_selected_conf_per_class_row(self):
        sel = self.conf_per_class_table.selectedItems()
        if not sel:
            return
        rows = {item.row() for item in sel}
        for row in sorted(rows, reverse=True):
            self.conf_per_class_table.removeRow(row)

    def _get_conf_per_class(self):
        conf_dict = {}
        for row in range(self.conf_per_class_table.rowCount()):
            id_item = self.conf_per_class_table.item(row, 0)
            conf_item = self.conf_per_class_table.item(row, 1)
            if id_item and conf_item:
                try:
                    k = int(id_item.text())
                    v = float(conf_item.text())
                    conf_dict[k] = v
                except Exception:
                    continue
        return conf_dict

    def _on_ok(self):
        try:
            yolo = {
                "device": self.fields['yolo_device'].text(),
                "version": self.fields['yolo_version'].text(),
                "imgsz": self.fields['yolo_imgsz'].value(),
                "conf": self.fields['yolo_conf'].value(),
                "classes": _str_to_list(self.fields['yolo_classes'].text()),
                "conf_per_class": self._get_conf_per_class(),
            }
            deepsort = {
                "max_disappeared": self.fields['deepsort_max_disappeared'].value(),
                "max_distance": self.fields['deepsort_max_distance'].value(),
                "device": self.fields['deepsort_device'].text(),
                "appearance_weight": self.fields['deepsort_appearance_weight'].value(),
                "motion_weight": self.fields['deepsort_motion_weight'].value(),
                "iou_weight": self.fields['deepsort_iou_weight'].value(),
                "nn_budget": self.fields['deepsort_nn_budget'].value(),
            }
            det = {
                "detection_fps": self.fields['det_fps'].value(),
                "delay_seconds": self.fields['det_delay'].value(),
                "enable_mot_writer": self.fields['enable_mot_writer'].isChecked(),
            }
            cwm = {
                "traffic_light_fps": self.fields['cwm_tl_fps'].value(),
            }

            # Write back to config
            self.location["config"] = {
                "yolo": yolo,
                "deepsort": deepsort,
                "player": {},  # Add player/database if you want to expose them
                "detection_thread": det,
                "crosswalk_monitor": cwm,
            }

            # Save to disk via LocationManager
            from utils.LocationManager import LocationManager
            lm = LocationManager()
            lm.update_location(self.location, self.location.copy())  # Save in-place

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Invalid Input", f"Error saving config: {e}")
            return

        self.accept()

