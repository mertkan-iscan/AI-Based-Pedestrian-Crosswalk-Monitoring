import cv2
import numpy as np
import uuid
import json
import os

from PyQt5 import QtCore, QtGui, QtWidgets
from region import RegionEditor, LocationManager

from stream.VideoStreamThread import VideoStreamThread


class ScalableLabel(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(0, 0)

    def sizeHint(self):
        return QtCore.QSize(100, 100)

    def minimumSizeHint(self):
        return QtCore.QSize(0, 0)


class VideoPlayerWindow(QtWidgets.QMainWindow):
    def __init__(self, location, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Live Stream - {location['name']}")
        self.resize(800, 600)
        self.location = location
        self.current_pixmap = None
        self.initUI()
        self.start_stream()
        self.showMaximized()

    def initUI(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        # Create a splitter to show the video and detected objects side by side.
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # Left side: Video display and Stop button
        video_widget = QtWidgets.QWidget()
        video_layout = QtWidgets.QVBoxLayout(video_widget)

        self.video_label = ScalableLabel()
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        self.video_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        video_layout.addWidget(self.video_label)

        stop_btn = QtWidgets.QPushButton("Stop Stream")
        stop_btn.clicked.connect(self.stop_stream)
        video_layout.addWidget(stop_btn)

        splitter.addWidget(video_widget)

        # Right side: Detected objects list
        self.objects_list = QtWidgets.QListWidget()
        splitter.addWidget(self.objects_list)
        splitter.setSizes([600, 200])  # Adjust initial sizes

        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.addWidget(splitter)

    def start_stream(self):
        if "video_path" in self.location and self.location["video_path"]:
            stream_source = self.location["video_path"]
        else:
            stream_source = self.location["stream_url"]

        self.stream_thread = VideoStreamThread(stream_source, self.location["polygons_file"])
        self.stream_thread.frame_ready.connect(self.update_frame)
        self.stream_thread.objects_ready.connect(self.update_detected_objects)
        self.stream_thread.error_signal.connect(self.handle_error)
        self.stream_thread.start()

    def update_frame(self, q_img):
        pixmap = QtGui.QPixmap.fromImage(q_img)
        self.current_pixmap = pixmap
        scaled_pixmap = pixmap.scaled(self.video_label.size(),
                                      QtCore.Qt.KeepAspectRatio,
                                      QtCore.Qt.SmoothTransformation)
        self.video_label.setPixmap(scaled_pixmap)

    def update_detected_objects(self, objects):

        self.objects_list.clear()
        for obj in objects:
            item_text = f"ID: {obj.id}, Type: {obj.object_type}, Region: {obj.region}"
            self.objects_list.addItem(item_text)

    def resizeEvent(self, event):
        if self.current_pixmap:
            scaled_pixmap = self.current_pixmap.scaled(self.video_label.size(),
                                                       QtCore.Qt.KeepAspectRatio,
                                                       QtCore.Qt.SmoothTransformation)
            self.video_label.setPixmap(scaled_pixmap)
        super().resizeEvent(event)

    def handle_error(self, error_msg):
        QtWidgets.QMessageBox.critical(self, "Stream Error", error_msg)
        self.stop_stream()

    def stop_stream(self):
        if hasattr(self, "stream_thread") and self.stream_thread is not None:
            self.stream_thread.stop()
            self.stream_thread = None
        self.close()

    def closeEvent(self, event):
        self.stop_stream()
        event.accept()

class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal(int, int)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit(event.x(), event.y())
        super().mousePressEvent(event)


class RegionEditorDialog(QtWidgets.QDialog):
    def __init__(self, frozen_frame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Region Editing")
        self.setWindowFlags(
            QtCore.Qt.Window
            | QtCore.Qt.WindowSystemMenuHint
            | QtCore.Qt.WindowMinimizeButtonHint
            | QtCore.Qt.WindowMaximizeButtonHint
            | QtCore.Qt.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(True)
        self.frozen_frame = frozen_frame.copy()
        self.current_points = []
        self.current_region_type = "crosswalk"
        self.initUI()
        self.update_display()
        self.showMaximized()

    def initUI(self):
        """Create a more intuitive UI by grouping region type controls and polygon actions."""

        # Main horizontal layout: left side for image, right side for controls
        main_layout = QtWidgets.QHBoxLayout(self)

        # -----------------------------
        # Left Layout: Image display
        # -----------------------------
        left_layout = QtWidgets.QVBoxLayout()

        self.image_label = ClickableLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.image_label.clicked.connect(self.add_point)

        left_layout.addWidget(self.image_label)
        main_layout.addLayout(left_layout, stretch=3)  # Give more space to the image

        # -----------------------------
        # Right Layout: Grouped controls
        # -----------------------------
        right_layout = QtWidgets.QVBoxLayout()

        # --- Group Box: Region Type Selection ---
        region_type_group = QtWidgets.QGroupBox("Select Region Type")
        region_type_layout = QtWidgets.QVBoxLayout()

        self.crosswalk_btn = QtWidgets.QPushButton("Crosswalk")
        self.crosswalk_btn.clicked.connect(lambda: self.set_region_type("crosswalk"))
        region_type_layout.addWidget(self.crosswalk_btn)

        self.road_btn = QtWidgets.QPushButton("Road")
        self.road_btn.clicked.connect(lambda: self.set_region_type("road"))
        region_type_layout.addWidget(self.road_btn)

        self.sidewalk_btn = QtWidgets.QPushButton("Sidewalk")
        self.sidewalk_btn.clicked.connect(lambda: self.set_region_type("sidewalk"))
        region_type_layout.addWidget(self.sidewalk_btn)

        self.car_wait_btn = QtWidgets.QPushButton("Car Wait")
        self.car_wait_btn.clicked.connect(lambda: self.set_region_type("car_wait"))
        region_type_layout.addWidget(self.car_wait_btn)

        self.pedes_wait_btn = QtWidgets.QPushButton("Pedestrian Wait")
        self.pedes_wait_btn.clicked.connect(lambda: self.set_region_type("pedes_wait"))
        region_type_layout.addWidget(self.pedes_wait_btn)

        region_type_group.setLayout(region_type_layout)
        right_layout.addWidget(region_type_group)

        # --- Group Box: Polygon Editing Actions ---
        polygon_group = QtWidgets.QGroupBox("Polygon Editing")
        polygon_layout = QtWidgets.QVBoxLayout()

        finalize_btn = QtWidgets.QPushButton("Finalize Polygon")
        finalize_btn.clicked.connect(self.finalize_polygon)
        polygon_layout.addWidget(finalize_btn)

        clear_btn = QtWidgets.QPushButton("Clear Current Points")
        clear_btn.clicked.connect(self.clear_points)
        polygon_layout.addWidget(clear_btn)

        delete_btn = QtWidgets.QPushButton("Delete Last Polygon")
        delete_btn.clicked.connect(self.delete_last_polygon)
        polygon_layout.addWidget(delete_btn)

        reset_btn = QtWidgets.QPushButton("Reset All Polygons")
        reset_btn.clicked.connect(self.reset_polygons)
        polygon_layout.addWidget(reset_btn)

        polygon_group.setLayout(polygon_layout)
        right_layout.addWidget(polygon_group)

        # --- Exit / Close Button at the bottom ---
        exit_btn = QtWidgets.QPushButton("Exit Editing")
        exit_btn.clicked.connect(self.accept)
        right_layout.addWidget(exit_btn)

        # Add stretch so everything stays nicely at the top
        right_layout.addStretch()

        main_layout.addLayout(right_layout, stretch=1)

    def update_display(self):
        img = self.frozen_frame.copy()
        img = RegionEditor.overlay_regions(img, alpha=0.4)
        if len(self.current_points) > 1:
            cv2.polylines(img, [np.array(self.current_points, dtype=np.int32)],
                          isClosed=False, color=(0, 255, 0), thickness=2)
        for pt in self.current_points:
            cv2.circle(img, pt, 3, (0, 0, 255), -1)

        cv2.putText(img, f"Current Region Type: {self.current_region_type}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        height, width, channel = rgb.shape
        bytes_per_line = 3 * width
        qimg = QtGui.QImage(rgb.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888).copy()
        pixmap = QtGui.QPixmap.fromImage(qimg)

        label_size = self.image_label.size()
        if pixmap.width() > label_size.width() or pixmap.height() > label_size.height():
            scaled_pixmap = pixmap.scaled(label_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        else:
            scaled_pixmap = pixmap
        self.image_label.setPixmap(scaled_pixmap)

    def add_point(self, x, y):
        label_size = self.image_label.size()
        pixmap = self.image_label.pixmap()
        if pixmap is None:
            return
        disp_width = pixmap.width()
        disp_height = pixmap.height()
        offset_x = (label_size.width() - disp_width) // 2
        offset_y = (label_size.height() - disp_height) // 2
        if x < offset_x or y < offset_y or x > offset_x + disp_width or y > offset_y + disp_height:
            return
        rel_x = x - offset_x
        rel_y = y - offset_y
        ratio_x = self.frozen_frame.shape[1] / disp_width
        ratio_y = self.frozen_frame.shape[0] / disp_height
        orig_x = int(rel_x * ratio_x)
        orig_y = int(rel_y * ratio_y)
        self.current_points.append((orig_x, orig_y))
        self.update_display()

    def set_region_type(self, rtype):
        self.current_region_type = rtype
        self.update_display()

    def finalize_polygon(self):
        if len(self.current_points) >= 3:
            RegionEditor.region_polygons.append({
                "type": self.current_region_type,
                "points": self.current_points.copy()
            })
            self.current_points.clear()
            RegionEditor.save_polygons()
            self.update_display()
        else:
            QtWidgets.QMessageBox.warning(self, "Warning", "Polygon requires at least 3 points.")

    def clear_points(self):
        self.current_points.clear()
        self.update_display()

    def delete_last_polygon(self):
        if RegionEditor.region_polygons:
            RegionEditor.region_polygons.pop()
            RegionEditor.save_polygons()
            self.update_display()
        else:
            QtWidgets.QMessageBox.information(self, "Info", "No polygon to delete.")

    def reset_polygons(self):
        RegionEditor.region_polygons.clear()
        if RegionEditor.region_json_file and os.path.exists(RegionEditor.region_json_file):
            os.remove(RegionEditor.region_json_file)
        self.update_display()

    def resizeEvent(self, event):
        self.update_display()
        super().resizeEvent(event)



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
        from stream.LiveStream import get_single_frame
        RegionEditor.region_json_file = self.selected_location["polygons_file"]
        RegionEditor.load_polygons()
        frame = get_single_frame(self.selected_location["stream_url"])
        if frame is None:
            QtWidgets.QMessageBox.critical(self, "Error", "Could not retrieve a frame from the stream.")
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