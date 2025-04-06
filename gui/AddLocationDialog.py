import os
import uuid

from PyQt5 import QtCore, QtGui, QtWidgets

from region import LocationManager


class AddLocationDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Location")
        self.resize(300, 200)
        self.setupUI()

    def setupUI(self):
        layout = QtWidgets.QVBoxLayout(self)
        name_label = QtWidgets.QLabel("Location Name:")
        self.name_edit = QtWidgets.QLineEdit()
        layout.addWidget(name_label)
        layout.addWidget(self.name_edit)
        stream_label = QtWidgets.QLabel("Stream URL:")
        self.stream_edit = QtWidgets.QLineEdit()
        layout.addWidget(stream_label)
        layout.addWidget(self.stream_edit)
        btn_layout = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Add")
        add_btn.clicked.connect(self.add_location)
        btn_layout.addWidget(add_btn)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def add_location(self):
        name = self.name_edit.text().strip()
        stream_url = self.stream_edit.text().strip()

        if not name or not stream_url:
            QtWidgets.QMessageBox.critical(self, "Error", "Name and Stream URL are required.")
            return

        polygons_file = os.path.join("resources", "location_regions", f"polygons_{uuid.uuid4().hex}.json")

        new_loc = {
            "name": name,
            "stream_url": stream_url,
            "polygons_file": polygons_file
        }

        LocationManager.add_location(new_loc)

        if not os.path.exists(polygons_file):

            with open(polygons_file, "w") as f:
                import json
                json.dump([], f, indent=4)

            print(f"Created new polygons file: {polygons_file}")

        self.accept()