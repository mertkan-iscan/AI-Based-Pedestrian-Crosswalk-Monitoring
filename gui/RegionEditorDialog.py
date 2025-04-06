import os

import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

from region import RegionEditor


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

        left_layout = QtWidgets.QVBoxLayout()

        self.image_label = ClickableLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.image_label.clicked.connect(self.add_point)

        left_layout.addWidget(self.image_label)
        main_layout.addLayout(left_layout, stretch=3)  # Give more space to the image

        right_layout = QtWidgets.QVBoxLayout()

        # --- Group Box: Region Type Selection ---
        region_type_group = QtWidgets.QGroupBox("Select Region Type")
        region_type_layout = QtWidgets.QVBoxLayout()

        self.blackout_btn = QtWidgets.QPushButton("Detection Blackout")
        self.blackout_btn.clicked.connect(lambda: self.set_region_type("detection_blackout"))
        region_type_layout.addWidget(self.blackout_btn)

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