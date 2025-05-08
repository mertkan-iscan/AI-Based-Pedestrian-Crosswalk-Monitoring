import os
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QFileDialog
from utils import LocationManager
from stream.FrameExtractor import FrameExtractor
from gui.dialogs.CropDialog import CropDialog
from gui.dialogs.HomographySetterDialog import HomographySetterDialog


class EditLocationDialog(QtWidgets.QDialog):
    def __init__(self, location, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Location")
        self.resize(300, 480)
        # preserve original for matching
        self._original = location
        # work on a separate copy for edits
        self._updated = location.copy()
        self.homography_matrix = self._updated.get("homography_matrix")
        self.bird_image_path = self._updated.get("birds_eye_image")
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Name
        layout.addWidget(QtWidgets.QLabel("Location Name:"))
        self.name_edit = QtWidgets.QLineEdit(self._updated.get("name", ""))
        layout.addWidget(self.name_edit)

        # Source type radios
        type_group = QtWidgets.QGroupBox("Source Type:")
        type_layout = QtWidgets.QHBoxLayout(type_group)
        self.stream_radio = QtWidgets.QRadioButton("Live Stream")
        self.video_radio = QtWidgets.QRadioButton("Video File")
        if "video_path" in self._updated:
            self.video_radio.setChecked(True)
        else:
            self.stream_radio.setChecked(True)
        type_layout.addWidget(self.stream_radio)
        type_layout.addWidget(self.video_radio)
        layout.addWidget(type_group)

        # Stream URL field
        self.stream_widget = QtWidgets.QWidget()
        stream_layout = QtWidgets.QVBoxLayout(self.stream_widget)
        stream_layout.addWidget(QtWidgets.QLabel("Stream URL:"))
        self.stream_edit = QtWidgets.QLineEdit(self._updated.get("stream_url", ""))
        stream_layout.addWidget(self.stream_edit)
        layout.addWidget(self.stream_widget)

        # Video file field
        self.video_widget = QtWidgets.QWidget()
        video_layout = QtWidgets.QVBoxLayout(self.video_widget)
        video_layout.addWidget(QtWidgets.QLabel("Video File:"))
        self.video_path_edit = QtWidgets.QLineEdit(self._updated.get("video_path", ""))
        browse_btn = QtWidgets.QPushButton("Browse Video")
        browse_btn.clicked.connect(self._browse_video_file)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.video_path_edit)
        row.addWidget(browse_btn)
        video_layout.addLayout(row)
        layout.addWidget(self.video_widget)

        self.stream_radio.toggled.connect(self._toggle_source)
        self.video_radio.toggled.connect(self._toggle_source)
        self._toggle_source()

        # Bird's-eye image upload and preview
        upload_btn = QtWidgets.QPushButton("Upload Bird’s-Eye Image")
        upload_btn.clicked.connect(self._browse_bird_image)
        layout.addWidget(upload_btn)
        self.preview_label = QtWidgets.QLabel()
        self.preview_label.setFixedSize(150, 150)
        self.preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_label.setScaledContents(True)
        if self.bird_image_path:
            pix = QtGui.QPixmap(self.bird_image_path)
            self.preview_label.setPixmap(pix)
        layout.addWidget(self.preview_label)

        # Homography setter
        homo_btn = QtWidgets.QPushButton("Set Homography")
        homo_btn.clicked.connect(self._set_homography)
        layout.addWidget(homo_btn)
        self.homo_status = QtWidgets.QLabel(
            "Homography set." if self.homography_matrix else "Homography not set."
        )
        layout.addWidget(self.homo_status)

        # Dialog buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _toggle_source(self):
        is_stream = self.stream_radio.isChecked()
        self.stream_widget.setVisible(is_stream)
        self.video_widget.setVisible(not is_stream)

    def _browse_video_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mkv *.mov)"
        )
        if path:
            self.video_path_edit.setText(path)

    def _browse_bird_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Bird’s-Eye Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return
        dlg = CropDialog(path, self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        cropped = dlg.getCropped()
        name, ext = os.path.splitext(os.path.basename(path))
        save_dir = os.path.join(os.getcwd(), "resources", "satellite_images")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"{name}_cropped{ext}")
        cropped.save(save_path)
        self.bird_image_path = save_path
        self.preview_label.setPixmap(QtGui.QPixmap(save_path))

    def _set_homography(self):
        if not self.bird_image_path:
            QtWidgets.QMessageBox.critical(self, "Error", "Upload a bird’s-eye image first.")
            return
        if self.video_radio.isChecked():
            frame = FrameExtractor.get_single_frame_file(self._updated["video_path"])
        else:
            frame = FrameExtractor.get_single_frame(self._updated["stream_url"])
        if frame is None:
            QtWidgets.QMessageBox.critical(self, "Error", "Cannot grab camera frame.")
            return
        dlg = HomographySetterDialog(frame, self.bird_image_path, self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.homography_matrix = dlg.get_homography()
            self.homo_status.setText("Homography set.")
        else:
            self.homo_status.setText("Homography not set.")

    def _on_ok(self):
        # Validate name
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Name is required.")
            return

        # Build updated dict
        updated = self._original.copy()
        updated["name"] = name
        if self.video_radio.isChecked():
            updated["video_path"] = self.video_path_edit.text().strip()
            updated.pop("stream_url", None)
        else:
            updated["stream_url"] = self.stream_edit.text().strip()
            updated.pop("video_path", None)
        if hasattr(self, "bird_image_path") and self.bird_image_path:
            updated["birds_eye_image"] = self.bird_image_path
        if self.homography_matrix is not None:
            updated["homography_matrix"] = (
                self.homography_matrix.tolist()
                if hasattr(self.homography_matrix, "tolist")
                else self.homography_matrix
            )

        # Attempt to update via LocationManager (will enforce uniqueness)
        try:
            LocationManager.update_location(self._original, updated)
        except ValueError as e:
            QtWidgets.QMessageBox.warning(self, "Validation", str(e))
            return

        # On success, store updated and close
        self._updated = updated
        self.accept()

    def get_updated_location(self):
        return getattr(self, "_updated", self._original)
