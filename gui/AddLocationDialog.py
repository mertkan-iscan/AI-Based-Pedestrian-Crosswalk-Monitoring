import os
import uuid
import json

from PyQt5 import QtCore, QtGui, QtWidgets

from region import LocationManager
from stream.FrameExtractor import FrameExtractor
from gui.HomographySetterDialog import HomographySetterDialog


class AddLocationDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Location")
        # Increased height to accommodate additional controls.
        self.resize(300, 300)
        self.homography_matrix = None  # to store the computed homography
        self.setupUI()

    def setupUI(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Location name input.
        name_label = QtWidgets.QLabel("Location Name:")
        self.name_edit = QtWidgets.QLineEdit()
        layout.addWidget(name_label)
        layout.addWidget(self.name_edit)

        # Stream URL input.
        stream_label = QtWidgets.QLabel("Stream URL:")
        self.stream_edit = QtWidgets.QLineEdit()
        layout.addWidget(stream_label)
        layout.addWidget(self.stream_edit)

        # --- New: Bird's Eye View Image Upload Section ---
        birds_eye_label = QtWidgets.QLabel("Bird's Eye View Image Path:")
        layout.addWidget(birds_eye_label)
        # Create a horizontal layout for the QLineEdit and Browse button.
        birds_eye_layout = QtWidgets.QHBoxLayout()
        self.birdseye_path_edit = QtWidgets.QLineEdit()
        birds_eye_layout.addWidget(self.birdseye_path_edit)
        browse_btn = QtWidgets.QPushButton("Browse")
        browse_btn.clicked.connect(self.browseBirdsEyeImage)
        birds_eye_layout.addWidget(browse_btn)
        layout.addLayout(birds_eye_layout)
        # --- End New Section ---

        # Homography setter section.
        self.set_homography_btn = QtWidgets.QPushButton("Set Homography")
        self.set_homography_btn.clicked.connect(self.setHomography)
        layout.addWidget(self.set_homography_btn)
        self.homography_status_label = QtWidgets.QLabel("Homography not set.")
        layout.addWidget(self.homography_status_label)

        # Dialog buttons (Add/Cancel).
        btn_layout = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Add")
        add_btn.clicked.connect(self.add_location)
        btn_layout.addWidget(add_btn)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def browseBirdsEyeImage(self):
        # Open a file dialog filtering for common image types.
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Bird's Eye View Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_name:
            self.birdseye_path_edit.setText(file_name)

    def setHomography(self):
        # Get stream URL and retrieve a frame.
        stream_url = self.stream_edit.text().strip()
        if not stream_url:
            QtWidgets.QMessageBox.critical(self, "Error", "Please enter the stream URL first.")
            return
        camera_frame = FrameExtractor.get_single_frame(stream_url)
        if camera_frame is None:
            QtWidgets.QMessageBox.critical(self, "Error", "Could not retrieve a frame from the stream.")
            return
        # Open the Homography Setter Dialog.
        dialog = HomographySetterDialog(camera_frame, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            H_matrix = dialog.get_homography()
            if H_matrix is not None:
                self.homography_matrix = H_matrix
                self.homography_status_label.setText("Homography set successfully.")
            else:
                self.homography_status_label.setText("Homography computation failed.")
        else:
            self.homography_status_label.setText("Homography not set.")

    def add_location(self):
        name = self.name_edit.text().strip()
        stream_url = self.stream_edit.text().strip()
        birds_eye_image_path = self.birdseye_path_edit.text().strip()

        if not name or not stream_url:
            QtWidgets.QMessageBox.critical(self, "Error", "Name and Stream URL are required.")
            return

        polygons_file = os.path.join("resources", "location_regions", f"polygons_{uuid.uuid4().hex}.json")

        new_loc = {
            "name": name,
            "stream_url": stream_url,
            "polygons_file": polygons_file
        }

        # Include the bird's eye view image path if provided.
        if birds_eye_image_path:
            new_loc["birds_eye_image"] = birds_eye_image_path

        # If a homography has been set, include it.
        if self.homography_matrix is not None:
            new_loc["homography_matrix"] = self.homography_matrix.tolist()

        LocationManager.add_location(new_loc)

        # Create an empty polygons file if it doesn't exist.
        if not os.path.exists(polygons_file):
            with open(polygons_file, "w") as f:
                json.dump([], f, indent=4)
            print(f"Created new polygons file: {polygons_file}")

        self.accept()
