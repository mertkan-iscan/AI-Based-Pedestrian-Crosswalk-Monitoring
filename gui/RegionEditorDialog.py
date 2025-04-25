# gui/RegionEditorDialog.py

import os
import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from region.RegionEditor import RegionEditor


class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal(int, int)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit(event.x(), event.y())
        super().mousePressEvent(event)


class RegionEditorDialog(QtWidgets.QDialog):
    def __init__(self, frozen_frame, parent=None, region_editor: RegionEditor = None):
        super().__init__(parent)
        self.editor = region_editor

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
        main_layout = QtWidgets.QHBoxLayout(self)

        # Left: image & region type label
        left_layout = QtWidgets.QVBoxLayout()
        self.image_label = ClickableLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                       QtWidgets.QSizePolicy.Expanding)
        self.image_label.clicked.connect(self.add_point)
        left_layout.addWidget(self.image_label)

        self.region_type_label = QtWidgets.QLabel(
            f"Current Region Type: {self.current_region_type}"
        )
        self.region_type_label.setAlignment(QtCore.Qt.AlignCenter)
        left_layout.addWidget(self.region_type_label)

        main_layout.addLayout(left_layout, stretch=4)

        # Right: controls
        right_layout = QtWidgets.QVBoxLayout()

        # Region type buttons
        region_type_group = QtWidgets.QGroupBox("Select Region Type")
        grid = QtWidgets.QGridLayout()
        btns = [
            ("Detection Blackout", "detection_blackout"),
            ("Crosswalk",         "crosswalk"),
            ("Road",              "road"),
            ("Sidewalk",          "sidewalk"),
            ("Car Wait",          "car_wait"),
            ("Ped Wait",          "pedes_wait"),
        ]
        for i, (txt, rtype) in enumerate(btns):
            btn = QtWidgets.QPushButton(txt)
            btn.clicked.connect(lambda _, t=rtype: self.set_region_type(t))
            grid.addWidget(btn, i // 2, i % 2)
        region_type_group.setLayout(grid)
        right_layout.addWidget(region_type_group)

        # Polygon actions
        poly_group = QtWidgets.QGroupBox("Polygon Editing")
        v = QtWidgets.QVBoxLayout()
        finalize_btn = QtWidgets.QPushButton("Finalize Polygon")
        finalize_btn.clicked.connect(self.finalize_polygon)
        v.addWidget(finalize_btn)

        clear_btn = QtWidgets.QPushButton("Clear Current Points")
        clear_btn.clicked.connect(self.clear_points)
        v.addWidget(clear_btn)

        delete_btn = QtWidgets.QPushButton("Delete Last Polygon")
        delete_btn.clicked.connect(self.delete_last_polygon)
        v.addWidget(delete_btn)

        reset_btn = QtWidgets.QPushButton("Reset All Polygons")
        reset_btn.clicked.connect(self.reset_polygons)
        v.addWidget(reset_btn)

        poly_group.setLayout(v)
        right_layout.addWidget(poly_group)

        # Exit
        exit_btn = QtWidgets.QPushButton("Exit Editing")
        exit_btn.clicked.connect(self.accept)
        right_layout.addWidget(exit_btn)
        right_layout.addStretch()

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setFixedWidth(250)
        main_layout.addWidget(right_widget, stretch=0)

    def update_display(self):
        img = self.frozen_frame.copy()
        # draw saved polygons
        img = self.editor.overlay_regions(img, alpha=0.4)
        # draw in-progress polygon
        if len(self.current_points) > 1:
            cv2.polylines(
                img,
                [np.array(self.current_points, dtype=np.int32)],
                isClosed=False,
                color=(0, 255, 0),
                thickness=2
            )
        for pt in self.current_points:
            cv2.circle(img, pt, 3, (0, 0, 255), -1)

        # convert & scale to QPixmap
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        bytes_per_line = 3 * w
        qimg = QtGui.QImage(
            rgb.data, w, h, bytes_per_line,
            QtGui.QImage.Format_RGB888
        ).copy()
        pixmap = QtGui.QPixmap.fromImage(qimg)
        lbl_size = self.image_label.size()
        if pixmap.width() > lbl_size.width() or pixmap.height() > lbl_size.height():
            pixmap = pixmap.scaled(
                lbl_size,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
        self.image_label.setPixmap(pixmap)

    def add_point(self, x, y):
        pix = self.image_label.pixmap()
        if pix is None:
            return
        lbl_w, lbl_h = self.image_label.size().width(), self.image_label.size().height()
        disp_w, disp_h = pix.width(), pix.height()
        off_x = (lbl_w - disp_w) // 2
        off_y = (lbl_h - disp_h) // 2
        if not (off_x <= x <= off_x + disp_w and off_y <= y <= off_y + disp_h):
            return
        rx = int((x - off_x) * (self.frozen_frame.shape[1] / disp_w))
        ry = int((y - off_y) * (self.frozen_frame.shape[0] / disp_h))
        self.current_points.append((rx, ry))
        self.update_display()

    def set_region_type(self, rtype):
        self.current_region_type = rtype
        self.region_type_label.setText(f"Current Region Type: {rtype}")
        self.update_display()

    def finalize_polygon(self):
        if len(self.current_points) < 3:
            QtWidgets.QMessageBox.warning(self, "Warning", "Need at least 3 points.")
            return
        poly = {
            "type":   self.current_region_type,
            "points": self.current_points.copy()
        }
        self.editor.add_polygon(poly)
        self.editor.save_polygons()
        self.current_points.clear()
        self.update_display()

    def clear_points(self):
        self.current_points.clear()
        self.update_display()

    def delete_last_polygon(self):
        if not self.editor.region_polygons:
            QtWidgets.QMessageBox.information(self, "Info", "No polygon to delete.")
            return
        self.editor.region_polygons.pop()
        self.editor.save_polygons()
        self.update_display()

    def reset_polygons(self):
        self.editor.region_polygons.clear()
        json_file = self.editor.region_json_file
        if json_file and os.path.exists(json_file):
            os.remove(json_file)
        self.update_display()

    def resizeEvent(self, event):
        self.update_display()
        super().resizeEvent(event)
