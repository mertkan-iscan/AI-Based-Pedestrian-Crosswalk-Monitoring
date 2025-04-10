from PyQt5 import QtCore, QtWidgets
from gui.AddLocationDialog import AddLocationDialog
from gui.AddVideoRecordDialog import AddVideoRecordDialog
from gui.RegionEditorDialog import RegionEditorDialog
from gui.VideoPlayerWindow import VideoPlayerWindow
from region import RegionEditor, LocationManager
from stream.FrameExtractor import FrameExtractor


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pedestrian Cross Monitoring GUI")
        self.resize(800, 600)
        self.locations = LocationManager.load_locations()
        self.selected_location = None
        self.initUI()

    def initUI(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        # Main horizontal layout
        main_layout = QtWidgets.QHBoxLayout(central_widget)

        # Left side: Location list
        self.location_list = QtWidgets.QListWidget()
        self.refresh_location_list()
        self.location_list.itemSelectionChanged.connect(self.on_location_selected)

        # Right side: Buttons vertically stacked
        btn_layout = QtWidgets.QVBoxLayout()

        add_btn = QtWidgets.QPushButton("Add Location")
        add_btn.clicked.connect(self.open_add_location_dialog)
        btn_layout.addWidget(add_btn)

        add_video_btn = QtWidgets.QPushButton("Add Video")
        add_video_btn.clicked.connect(self.open_add_video_dialog)
        btn_layout.addWidget(add_video_btn)

        edit_btn = QtWidgets.QPushButton("Edit Polygons")
        edit_btn.clicked.connect(self.edit_polygons)
        btn_layout.addWidget(edit_btn)

        # New Edit Location button
        edit_location_btn = QtWidgets.QPushButton("Edit Location")
        edit_location_btn.clicked.connect(self.open_edit_location_dialog)
        btn_layout.addWidget(edit_location_btn)

        delete_btn = QtWidgets.QPushButton("Delete Location")
        delete_btn.clicked.connect(self.delete_location)
        btn_layout.addWidget(delete_btn)

        run_btn = QtWidgets.QPushButton("Run Stream")
        run_btn.clicked.connect(self.run_stream)
        btn_layout.addWidget(run_btn)

        # Add stretch to push Quit button to the bottom
        btn_layout.addStretch()

        quit_btn = QtWidgets.QPushButton("Quit")
        quit_btn.clicked.connect(self.close)
        btn_layout.addWidget(quit_btn)

        # Add widgets/layouts to the main layout with stretch factors
        main_layout.addWidget(self.location_list, stretch=4)
        main_layout.addLayout(btn_layout, stretch=2)

    def refresh_location_list(self):
        self.location_list.clear()
        self.locations = LocationManager.load_locations()
        for loc in self.locations:
            self.location_list.addItem(loc["name"])

    def on_location_selected(self):
        selected_items = self.location_list.selectedItems()
        if selected_items:
            selected_name = selected_items[0].text()
            for loc in self.locations:
                if loc["name"] == selected_name:
                    self.selected_location = loc
                    break

    def open_add_location_dialog(self):
        dialog = AddLocationDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.refresh_location_list()

    def open_add_video_dialog(self):
        dialog = AddVideoRecordDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.refresh_location_list()

    def edit_polygons(self):
        if not self.selected_location:
            QtWidgets.QMessageBox.critical(self, "Error", "Please select a location first.")
            return

        RegionEditor.region_json_file = self.selected_location["polygons_file"]
        RegionEditor.load_polygons()

        # Use FrameExtractor for video file frame retrieval.
        if "video_path" in self.selected_location and self.selected_location["video_path"]:
            frame = FrameExtractor.get_single_frame_file(self.selected_location["video_path"])
        else:
            frame = FrameExtractor.get_single_frame(self.selected_location["stream_url"])

        if frame is None:
            QtWidgets.QMessageBox.critical(self, "Error", "Could not retrieve a frame from the source.")
            return

        dialog = RegionEditorDialog(frame, self)
        dialog.exec_()

    def open_edit_location_dialog(self):
        if not self.selected_location:
            QtWidgets.QMessageBox.critical(self, "Error", "Please select a location first.")
            return
        from gui.EditLocationDialog import EditLocationDialog
        dialog = EditLocationDialog(self.selected_location, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_location = dialog.get_updated_location()
            LocationManager.update_location(self.selected_location, new_location)
            self.selected_location = new_location
            self.refresh_location_list()

    def run_stream(self):
        if not self.selected_location:
            QtWidgets.QMessageBox.critical(self, "Error", "Please select a location first.")
            return
        self.video_window = VideoPlayerWindow(self.selected_location)
        self.video_window.show()

    def delete_location(self):
        if not self.selected_location:
            QtWidgets.QMessageBox.critical(self, "Error", "Please select a location first.")
            return

        confirmation = QtWidgets.QMessageBox(self)
        confirmation.setIcon(QtWidgets.QMessageBox.Warning)
        confirmation.setWindowTitle("Confirm Delete")
        confirmation.setText(
            f"Are you sure you want to delete '{self.selected_location['name']}'?\nThis action cannot be undone.")
        confirmation.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        confirmation.setDefaultButton(QtWidgets.QMessageBox.No)

        if confirmation.exec_() == QtWidgets.QMessageBox.Yes:
            LocationManager.delete_location(self.selected_location)
            self.selected_location = None
            self.refresh_location_list()
