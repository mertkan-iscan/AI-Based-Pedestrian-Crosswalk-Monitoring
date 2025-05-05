# MainWindow.py
from PyQt5 import QtCore, QtWidgets

from gui.AddLocationDialog import AddLocationDialog
from gui.RegionEditorDialog import RegionEditorDialog
from gui.VideoPlayerWindow import VideoPlayerWindow

from region import LocationManager
from region.RegionEditor import RegionEditor

from stream.FrameExtractor import FrameExtractor

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pedestrian Cross Monitoring GUI")
        self.resize(800, 600)
        self.locations = []
        self.selected_location = None
        self.initUI()

    def initUI(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget)

        list_container = QtWidgets.QWidget()
        list_layout = QtWidgets.QHBoxLayout(list_container)

        stream_group = QtWidgets.QGroupBox("Live Stream")
        stream_layout = QtWidgets.QVBoxLayout(stream_group)
        self.stream_list = QtWidgets.QListWidget()
        stream_layout.addWidget(self.stream_list)
        list_layout.addWidget(stream_group)

        video_group = QtWidgets.QGroupBox("Video")
        video_layout = QtWidgets.QVBoxLayout(video_group)
        self.video_list = QtWidgets.QListWidget()
        video_layout.addWidget(self.video_list)
        list_layout.addWidget(video_group)

        main_layout.addWidget(list_container, stretch=4)

        btn_layout = QtWidgets.QVBoxLayout()

        add_btn = QtWidgets.QPushButton("Add Location")
        add_btn.clicked.connect(self.open_add_location_dialog)
        btn_layout.addWidget(add_btn)

        edit_btn = QtWidgets.QPushButton("Edit Polygons")
        edit_btn.clicked.connect(self.edit_polygons)
        btn_layout.addWidget(edit_btn)

        edit_location_btn = QtWidgets.QPushButton("Edit Location")
        edit_location_btn.clicked.connect(self.open_edit_location_dialog)
        btn_layout.addWidget(edit_location_btn)

        delete_btn = QtWidgets.QPushButton("Delete Location")
        delete_btn.clicked.connect(self.delete_location)
        btn_layout.addWidget(delete_btn)

        run_btn = QtWidgets.QPushButton("Run Stream")
        run_btn.clicked.connect(self.run_stream)
        btn_layout.addWidget(run_btn)

        btn_layout.addStretch()

        quit_btn = QtWidgets.QPushButton("Quit")
        quit_btn.clicked.connect(self.close)
        btn_layout.addWidget(quit_btn)

        main_layout.addLayout(btn_layout, stretch=2)

        self.stream_list.itemSelectionChanged.connect(
            lambda: self.on_location_selected(self.stream_list)
        )
        self.video_list.itemSelectionChanged.connect(
            lambda: self.on_location_selected(self.video_list)
        )

        self.refresh_lists()

    def refresh_lists(self):
        self.stream_list.clear()
        self.video_list.clear()
        self.locations = LocationManager.load_locations()
        for loc in self.locations:
            if loc.get("stream_url"):
                self.stream_list.addItem(loc["name"])
            elif loc.get("video_path"):
                self.video_list.addItem(loc["name"])

    def on_location_selected(self, list_widget):
        if list_widget is self.stream_list:
            self.video_list.clearSelection()
        else:
            self.stream_list.clearSelection()

        selected = list_widget.selectedItems()
        if selected:
            name = selected[0].text()
            for loc in self.locations:
                if loc["name"] == name:
                    self.selected_location = loc
                    break
        else:
            self.selected_location = None

    def open_add_location_dialog(self):
        dialog = AddLocationDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.refresh_lists()

    def edit_polygons(self):
        if not self.selected_location:
            QtWidgets.QMessageBox.critical(self, "Error", "Please select a location first.")
            return
        editor = RegionEditor(self.selected_location["polygons_file"])
        editor.load_polygons()
        if self.selected_location.get("video_path"):
            frame = FrameExtractor.get_single_frame_file(self.selected_location["video_path"])
        else:
            frame = FrameExtractor.get_single_frame(self.selected_location["stream_url"])
        if frame is None:
            QtWidgets.QMessageBox.critical(self, "Error", "Could not retrieve a frame from the source.")
            return
        dialog = RegionEditorDialog(frame, self, region_editor=editor)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            editor.save_polygons()

    def open_edit_location_dialog(self):
        if not self.selected_location:
            QtWidgets.QMessageBox.critical(self, "Error", "Please select a location first.")
            return
        from gui.EditLocationDialog import EditLocationDialog
        dialog = EditLocationDialog(self.selected_location, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_loc = dialog.get_updated_location()
            LocationManager.update_location(self.selected_location, new_loc)
            self.selected_location = new_loc
            self.refresh_lists()

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
            f"Are you sure you want to delete '{self.selected_location['name']}'?\nThis action cannot be undone."
        )
        confirmation.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        confirmation.setDefaultButton(QtWidgets.QMessageBox.No)
        if confirmation.exec_() == QtWidgets.QMessageBox.Yes:
            LocationManager.delete_location(self.selected_location)
            self.selected_location = None
            self.refresh_lists()