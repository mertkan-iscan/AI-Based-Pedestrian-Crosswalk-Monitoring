import json
import os
import uuid

from PyQt5 import QtCore, QtGui, QtWidgets

from region import LocationManager


class AddVideoRecordDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Video Record")
        self.resize(300, 200)
        self.setupUI()

    def setupUI(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Name input
        name_label = QtWidgets.QLabel("Location Name:")
        self.name_edit = QtWidgets.QLineEdit()
        layout.addWidget(name_label)
        layout.addWidget(self.name_edit)

        # Video file selection input
        video_label = QtWidgets.QLabel("Video File:")
        self.video_path_edit = QtWidgets.QLineEdit()
        layout.addWidget(video_label)
        file_layout = QtWidgets.QHBoxLayout()
        file_layout.addWidget(self.video_path_edit)
        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)

        # Buttons layout
        btn_layout = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Add")
        add_btn.clicked.connect(self.add_location)
        btn_layout.addWidget(add_btn)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def browse_file(self):
        # Open a file dialog to select video files
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mkv *.mov)"
        )
        if file_path:
            self.video_path_edit.setText(file_path)

    def add_location(self):
        name = self.name_edit.text().strip()
        video_file_path = self.video_path_edit.text().strip()

        if not name or not video_file_path:
            QtWidgets.QMessageBox.critical(self, "Error", "Name and Video File are required.")
            return

        polygons_file = os.path.join("resources", "location_regions", f"polygons_{uuid.uuid4().hex}.json")
        new_loc = {
            "name": name,
            "video_path": video_file_path,
            "polygons_file": polygons_file
        }
        LocationManager.add_location(new_loc)

        if not os.path.exists(polygons_file):
            with open(polygons_file, "w") as f:
                json.dump([], f, indent=4)
            print(f"Created new polygons file: {polygons_file}")

        self.accept()