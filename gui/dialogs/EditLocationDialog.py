from PyQt5 import QtCore, QtGui, QtWidgets

from utils.LocationManager import LocationManager
from gui.dialogs.LocationDialogHelper import LocationDialogHelper


class EditLocationDialog(QtWidgets.QDialog, LocationDialogHelper):

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
        browse_btn = QtWidgets.QPushButton("Browse")
        browse_btn.clicked.connect(lambda: self.browse_video_file(self.video_path_edit))
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
        upload_btn.clicked.connect(lambda: self.browse_bird_image(self.preview_label))
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
        homo_btn.clicked.connect(lambda: self.set_homography(
            self.video_radio, self.video_path_edit, self.stream_edit,
            'bird_image_path', self.homo_status, location=self._updated
        ))
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
            LocationManager().update_location(self._original, updated)
        except ValueError as e:
            QtWidgets.QMessageBox.warning(self, "Validation", str(e))
            return

        # On success, store updated and close
        self._updated = updated
        self.accept()

    def get_updated_location(self):
        return getattr(self, "_updated", self._original)
