from PyQt5 import QtCore, QtWidgets

from utils.LocationManager import LocationManager
from gui.dialogs.LocationDialogHelper import LocationDialogHelper


class AddLocationDialog(QtWidgets.QDialog, LocationDialogHelper):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Location")
        self.resize(300, 420)
        self.homography_matrix = None
        self.bird_image_path = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # location name
        layout.addWidget(QtWidgets.QLabel("Location Name:"))
        self.name_edit = QtWidgets.QLineEdit()
        layout.addWidget(self.name_edit)

        # source type selection
        type_group = QtWidgets.QGroupBox("Source Type:")
        type_layout = QtWidgets.QHBoxLayout(type_group)
        self.stream_radio = QtWidgets.QRadioButton("Live Stream")
        self.video_radio = QtWidgets.QRadioButton("Video File")
        self.stream_radio.setChecked(True)
        type_layout.addWidget(self.stream_radio)
        type_layout.addWidget(self.video_radio)
        layout.addWidget(type_group)

        # stream URL field
        self.stream_widget = QtWidgets.QWidget()
        stream_layout = QtWidgets.QVBoxLayout(self.stream_widget)
        stream_layout.addWidget(QtWidgets.QLabel("Stream URL:"))
        self.stream_edit = QtWidgets.QLineEdit()
        stream_layout.addWidget(self.stream_edit)
        layout.addWidget(self.stream_widget)

        # video file field
        self.video_widget = QtWidgets.QWidget()
        video_layout = QtWidgets.QVBoxLayout(self.video_widget)
        video_layout.addWidget(QtWidgets.QLabel("Video File:"))
        self.video_path_edit = QtWidgets.QLineEdit()

        browse_video_btn = QtWidgets.QPushButton("Browse")
        browse_video_btn.clicked.connect(lambda: self.browse_video_file(self.video_path_edit))

        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.video_path_edit)
        row.addWidget(browse_video_btn)
        video_layout.addLayout(row)
        layout.addWidget(self.video_widget)

        # bev image upload
        upload_btn = QtWidgets.QPushButton("Upload Bird’s-Eye Image")
        upload_btn.clicked.connect(lambda: self.browse_bird_image(self.birdImageLabel))
        self.birdImageLabel = QtWidgets.QLabel()
        self.birdImageLabel.setFixedSize(150, 150)
        self.birdImageLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.birdImageLabel.setScaledContents(True)
        layout.addWidget(upload_btn)
        layout.addWidget(self.birdImageLabel)

        # homography setter
        homo_btn = QtWidgets.QPushButton("Set Homography")

        homo_btn.clicked.connect(lambda: self.set_homography(
            self.video_radio, self.video_path_edit, self.stream_edit,
            'bird_image_path', self.homo_status
        ))

        self.homo_status = QtWidgets.QLabel("Homography not set.")
        layout.addWidget(homo_btn)
        layout.addWidget(self.homo_status)

        # dialog buttons
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # toggle between source fields
        self.stream_radio.toggled.connect(self.toggle_source_fields)
        self.video_radio.toggled.connect(self.toggle_source_fields)
        self.toggle_source_fields()

    def toggle_source_fields(self):
        is_stream = self.stream_radio.isChecked()
        self.stream_widget.setVisible(is_stream)
        self.video_widget.setVisible(not is_stream)

    def _on_ok(self):
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Name is required.")
            return

        loc = {"name": name}
        if self.stream_radio.isChecked():
            loc["stream_url"] = self.stream_edit.text().strip()
        else:
            loc["video_path"] = self.video_path_edit.text().strip()

        if self.bird_image_path:
            loc["birds_eye_image"] = self.bird_image_path
        if self.homography_matrix is not None:
            hm = (
                self.homography_matrix.tolist()
                if hasattr(self.homography_matrix, "tolist")
                else self.homography_matrix
            )
            loc["homography_matrix"] = hm

        try:
            LocationManager().add_location(loc)
        except ValueError as e:
            QtWidgets.QMessageBox.warning(self, "Validation", str(e))
            return

        self.accept()
