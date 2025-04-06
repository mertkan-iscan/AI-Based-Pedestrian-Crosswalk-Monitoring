from PyQt5 import QtCore, QtWidgets

from gui.AddLocationDialog import AddLocationDialog
from gui.AddVideoRecordDialog import AddVideoRecordDialog
from gui.RegionEditorDialog import RegionEditorDialog
from gui.VideoPlayerWindow import VideoPlayerWindow
from region import RegionEditor, LocationManager


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
        layout = QtWidgets.QVBoxLayout(central_widget)

        self.location_list = QtWidgets.QListWidget()
        self.refresh_location_list()
        self.location_list.itemSelectionChanged.connect(self.on_location_selected)

        layout.addWidget(self.location_list)
        btn_layout = QtWidgets.QHBoxLayout()

        add_btn = QtWidgets.QPushButton("Add Location")
        add_btn.clicked.connect(self.open_add_location_dialog)
        btn_layout.addWidget(add_btn)

        add_btn = QtWidgets.QPushButton("Add Video")
        add_btn.clicked.connect(self.open_add_video_dialog)
        btn_layout.addWidget(add_btn)

        edit_btn = QtWidgets.QPushButton("Edit Polygons")
        edit_btn.clicked.connect(self.edit_polygons)
        btn_layout.addWidget(edit_btn)

        run_btn = QtWidgets.QPushButton("Run Stream")
        run_btn.clicked.connect(self.run_stream)
        btn_layout.addWidget(run_btn)

        delete_btn = QtWidgets.QPushButton("Delete Location")
        delete_btn.clicked.connect(self.delete_location)
        btn_layout.addWidget(delete_btn)

        quit_btn = QtWidgets.QPushButton("Quit")
        quit_btn.clicked.connect(self.close)
        btn_layout.addWidget(quit_btn)

        layout.addLayout(btn_layout)

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

        if "video_path" in self.selected_location and self.selected_location["video_path"]:
            from stream.LiveStream import get_single_frame_file
            frame = get_single_frame_file(self.selected_location["video_path"])
        else:
            from stream.LiveStream import get_single_frame
            frame = get_single_frame(self.selected_location["stream_url"])

        if frame is None:
            QtWidgets.QMessageBox.critical(self, "Error", "Could not retrieve a frame from the source.")
            return

        dialog = RegionEditorDialog(frame, self)
        dialog.exec_()


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
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Location",
            f"Are you sure you want to delete '{self.selected_location['name']}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            LocationManager.delete_location(self.selected_location)
            self.selected_location = None
            self.refresh_location_list()




