from PyQt5 import QtWidgets
from stream.FrameExtractor import FrameExtractor
from gui.HomographySetterDialog import HomographySetterDialog


class EditLocationDialog(QtWidgets.QDialog):
    def __init__(self, location, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Location")
        # Work on a copy of the location.
        self.location = location.copy()
        # Load existing homography (if present).
        self.homography_matrix = self.location.get("homography_matrix", None)
        self.initUI()

    def browseVideoFile(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.avi *.mkv *.mov *.flv);;All Files (*)"
        )
        if file_name:
            self.edit_field.setText(file_name)

    def initUI(self):
        layout = QtWidgets.QFormLayout(self)

        # Location name field.
        self.name_edit = QtWidgets.QLineEdit(self.location.get("name", ""))
        layout.addRow("Name:", self.name_edit)

        if "video_path" in self.location and self.location["video_path"]:
            self.location_type = "video"

            self.edit_field = QtWidgets.QLineEdit(self.location.get("video_path", ""))

            src_layout = QtWidgets.QHBoxLayout()  # <─ NEW layout
            src_layout.addWidget(self.edit_field)

            browse_src_btn = QtWidgets.QPushButton("Browse")
            browse_src_btn.clicked.connect(self.browseVideoFile)
            src_layout.addWidget(browse_src_btn)

            layout.addRow("Video File Path:", src_layout)
        else:
            self.location_type = "stream"
            self.edit_field = QtWidgets.QLineEdit(self.location.get("stream_url", ""))
            layout.addRow("Stream URL:", self.edit_field)

        self.birdseye_edit = QtWidgets.QLineEdit(self.location.get("birds_eye_image", ""))
        birds_eye_layout = QtWidgets.QHBoxLayout()
        birds_eye_layout.addWidget(self.birdseye_edit)
        browse_btn = QtWidgets.QPushButton("Browse")
        browse_btn.clicked.connect(self.browseBirdsEyeImage)
        birds_eye_layout.addWidget(browse_btn)
        layout.addRow("Bird's Eye View Image Path:", birds_eye_layout)

        self.set_homography_btn = QtWidgets.QPushButton("Set Homography")
        self.set_homography_btn.clicked.connect(self.setHomography)
        self.homography_status_label = QtWidgets.QLabel()
        if self.homography_matrix is not None:
            self.homography_status_label.setText("Homography is set.")
        else:
            self.homography_status_label.setText("Homography not set.")
        homography_layout = QtWidgets.QHBoxLayout()
        homography_layout.addWidget(self.set_homography_btn)
        homography_layout.addWidget(self.homography_status_label)
        layout.addRow("Homography:", homography_layout)

        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

    def browseBirdsEyeImage(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Bird's Eye View Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_name:
            self.birdseye_edit.setText(file_name)

    def setHomography(self):
        camera_frame = None
        if self.location_type == "video":
            path = self.edit_field.text().strip()
            if path:
                camera_frame = FrameExtractor.get_single_frame_file(path)
        else:
            stream_url = self.edit_field.text().strip()
            if stream_url:
                camera_frame = FrameExtractor.get_single_frame(stream_url)
        if camera_frame is None:
            QtWidgets.QMessageBox.critical(self, "Error", "Could not retrieve a frame from the source.")
            return
        # Open the Homography Setter Dialog.
        dialog = HomographySetterDialog(camera_frame, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            H_matrix = dialog.get_homography()
            if H_matrix is not None:
                self.homography_matrix = H_matrix
                self.homography_status_label.setText("Homography is set.")
            else:
                self.homography_status_label.setText("Homography not set.")
        else:
            self.homography_status_label.setText("Homography not set.")

    def get_updated_location(self):
        new_location = self.location.copy()
        new_location["name"] = self.name_edit.text().strip()
        if self.location_type == "video":
            new_location["video_path"] = self.edit_field.text().strip()
            new_location.pop("stream_url", None)
        else:
            new_location["stream_url"] = self.edit_field.text().strip()
            new_location.pop("video_path", None)
        # Include the bird's eye view image path if provided.
        birds_eye_image = self.birdseye_edit.text().strip()
        if birds_eye_image:
            new_location["birds_eye_image"] = birds_eye_image
        else:
            new_location.pop("birds_eye_image", None)

        # Add homography if it has been set.
        if self.homography_matrix is not None:
            if hasattr(self.homography_matrix, "tolist"):
                new_location["homography_matrix"] = self.homography_matrix.tolist()
            else:
                new_location["homography_matrix"] = self.homography_matrix
        return new_location
