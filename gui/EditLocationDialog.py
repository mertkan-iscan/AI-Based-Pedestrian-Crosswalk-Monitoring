from PyQt5 import QtCore, QtWidgets

class EditLocationDialog(QtWidgets.QDialog):
    def __init__(self, location, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Location")
        # Work on a copy of the location.
        self.location = location.copy()
        self.initUI()

    def initUI(self):
        layout = QtWidgets.QFormLayout(self)

        # Location name field.
        self.name_edit = QtWidgets.QLineEdit(self.location.get("name", ""))
        layout.addRow("Name:", self.name_edit)

        # Determine which field to show: video file path or stream URL.
        if "video_path" in self.location and self.location["video_path"]:
            self.location_type = "video"
            self.edit_field = QtWidgets.QLineEdit(self.location.get("video_path", ""))
            field_label = "Video File Path:"
        else:
            self.location_type = "stream"
            self.edit_field = QtWidgets.QLineEdit(self.location.get("stream_url", ""))
            field_label = "Stream URL:"

        layout.addRow(field_label, self.edit_field)

        # Dialog buttons.
        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

    def get_updated_location(self):
        new_location = self.location.copy()
        new_location["name"] = self.name_edit.text().strip()
        if self.location_type == "video":
            new_location["video_path"] = self.edit_field.text().strip()
            new_location.pop("stream_url", None)
        else:
            new_location["stream_url"] = self.edit_field.text().strip()
            new_location.pop("video_path", None)
        return new_location
