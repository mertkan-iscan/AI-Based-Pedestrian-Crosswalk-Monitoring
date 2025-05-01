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

        # -------- Left: image --------
        left_layout = QtWidgets.QVBoxLayout()
        self.image_label = ClickableLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        self.image_label.clicked.connect(self.on_click)
        left_layout.addWidget(self.image_label)
        main_layout.addLayout(left_layout, stretch=4)

        # -------- Right: controls --------
        right_layout = QtWidgets.QVBoxLayout()

        region_type_group = QtWidgets.QGroupBox("Select Region Type")
        grid = QtWidgets.QGridLayout()
        types = [("Detection Blackout", "detection_blackout"),
                 ("Road", "road"),
                 ("Sidewalk", "sidewalk")]
        for i, (txt, t) in enumerate(types):
            btn = QtWidgets.QPushButton(txt)
            btn.clicked.connect(lambda _, r=t: self.set_region_type(r))
            grid.addWidget(btn, i // 2, i % 2)
        pack_btn = QtWidgets.QPushButton("Add Crosswalk Pack")
        pack_btn.clicked.connect(self.open_crosswalk_pack_editor)
        grid.addWidget(pack_btn, 1, 1)
        region_type_group.setLayout(grid)
        right_layout.addWidget(region_type_group)

        # Polygon editing buttons
        poly_group = QtWidgets.QGroupBox("Polygon Editing")
        vbox = QtWidgets.QVBoxLayout()
        finalize_btn = QtWidgets.QPushButton("Finalize Polygon")
        finalize_btn.clicked.connect(self.finalize_polygon)
        vbox.addWidget(finalize_btn)
        clear_btn = QtWidgets.QPushButton("Clear Current Points")
        clear_btn.clicked.connect(self.clear_points)
        vbox.addWidget(clear_btn)
        reset_btn = QtWidgets.QPushButton("Reset All")
        reset_btn.clicked.connect(self.reset_polygons)
        vbox.addWidget(reset_btn)
        poly_group.setLayout(vbox)
        right_layout.addWidget(poly_group)

        # List of existing polygons with delete support
        self.poly_list = QtWidgets.QListWidget()
        self.poly_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        right_layout.addWidget(self.poly_list, stretch=1)
        del_btn = QtWidgets.QPushButton("Delete Selected")
        del_btn.clicked.connect(self.delete_selected_polygon)
        right_layout.addWidget(del_btn)

        exit_btn = QtWidgets.QPushButton("Exit Editing")
        exit_btn.clicked.connect(self.accept)
        right_layout.addWidget(exit_btn)
        right_layout.addStretch()

        container = QtWidgets.QWidget()
        container.setLayout(right_layout)
        container.setFixedWidth(250)
        main_layout.addWidget(container, stretch=0)

    def refresh_poly_list(self):
        self.poly_list.clear()
        for poly in self.editor.region_polygons:
            label = f"{poly['type']} #{poly['id']}"
            if poly["pack_id"] is not None:
                label += f"  (pack {poly['pack_id']})"
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, (poly["type"], poly["id"], poly["pack_id"]))
            self.poly_list.addItem(item)

    def delete_selected_polygon(self):
        item = self.poly_list.currentItem()
        if not item:
            QtWidgets.QMessageBox.information(self, "Info", "No polygon selected.")
            return
        rtype, pid, pack_id = item.data(QtCore.Qt.UserRole)
        if self.editor.delete_polygon(rtype, pid, pack_id):
            self.editor.save_polygons()
            self.update_display()

    def on_click(self, x, y):
        label_w = self.image_label.width()
        label_h = self.image_label.height()
        img_h, img_w = self.frozen_frame.shape[:2]
        scale = min(label_w / img_w, label_h / img_h)
        new_w, new_h = int(img_w * scale), int(img_h * scale)
        x0 = (label_w - new_w) // 2
        y0 = (label_h - new_h) // 2
        if x < x0 or x > x0 + new_w or y < y0 or y > y0 + new_h:
            return
        px = int((x - x0) / scale)
        py = int((y - y0) / scale)
        self.current_points.append([px, py])
        self.update_display()

    def set_region_type(self, region_type: str):
        self.current_region_type = region_type
        self.current_points.clear()
        self.update_display()

    def open_crosswalk_pack_editor(self):
        dlg = CrosswalkPackEditorDialog(self.frozen_frame, parent=self, region_editor=self.editor)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.update_display()
        self.refresh_poly_list()

    def update_display(self):
        img = self.frozen_frame.copy()
        img = self.editor.overlay_regions(img, alpha=0.4)
        for pt in self.current_points:
            cv2.circle(img, tuple(pt), 4, (0, 0, 255), -1)
        qimg = QtGui.QImage(img.data, img.shape[1], img.shape[0], img.strides[0], QtGui.QImage.Format_BGR888)
        pix = QtGui.QPixmap.fromImage(qimg)
        self.image_label.setPixmap(pix.scaled(self.image_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        self.refresh_poly_list()

    def finalize_polygon(self):
        if len(self.current_points) < 3:
            QtWidgets.QMessageBox.warning(self, "Warning", "Need at least 3 points.")
            return
        poly = {
            "type": self.current_region_type,
            "points": self.current_points.copy(),
        }
        self.editor.add_polygon(poly)
        self.editor.save_polygons()
        self.current_points.clear()
        self.update_display()

    def delete_last_polygon(self):
        if not self.editor.region_polygons:
            QtWidgets.QMessageBox.information(self, "Info", "No polygon to delete.")
            return
        self.editor.region_polygons.pop()
        self.editor.save_polygons()
        self.update_display()

    def clear_points(self):
        self.current_points.clear()
        self.update_display()

    def reset_polygons(self):
        self.editor.region_polygons.clear()
        json_file = self.editor.region_json_file
        if json_file and os.path.exists(json_file):
            os.remove(json_file)
        self.update_display()
        self.refresh_poly_list()

    def resizeEvent(self, event):
        self.update_display()
        super().resizeEvent(event)


# gui/CrosswalkPackEditorDialog.py
import os
import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from region.RegionEditor import RegionEditor
from gui.RegionEditorDialog import ClickableLabel


class CrosswalkPackEditorDialog(QtWidgets.QDialog):
    def __init__(self, frozen_frame, parent=None, region_editor: RegionEditor = None):
        super().__init__(parent)
        self.editor = region_editor
        self.frozen_frame = frozen_frame.copy()
        self.current_points = []
        self.polygons = {
            "crosswalk": [],
            "car_wait": [],
            "pedes_wait": [],
            "traffic_light": []
        }
        self.stage_info = [
            ("crosswalk", 1, 1),
            ("car_wait", 1, 2),
            ("pedes_wait", 1, 2),
            ("traffic_light", 1, 4)
        ]
        self.stage = 0

        self.setWindowTitle("Crosswalk Pack Editing")
        self.setWindowFlags(
            QtCore.Qt.Window
            | QtCore.Qt.WindowSystemMenuHint
            | QtCore.Qt.WindowMinimizeButtonHint
            | QtCore.Qt.WindowMaximizeButtonHint
            | QtCore.Qt.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(True)

        self.initUI()
        self.showMaximized()

        # Draw once the layout is fully settled, so the pixmap fits the label size
        QtCore.QTimer.singleShot(0, self.update_display)

    def resizeEvent(self, event):
        self.update_display()
        super().resizeEvent(event)

    def initUI(self):
        self.setWindowTitle("Add Crosswalk Pack")
        main_layout = QtWidgets.QHBoxLayout(self)

        left_layout = QtWidgets.QVBoxLayout()
        self.image_label = ClickableLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        self.image_label.clicked.connect(self.on_click)
        left_layout.addWidget(self.image_label)
        main_layout.addLayout(left_layout, stretch=4)

        right_layout = QtWidgets.QVBoxLayout()
        self.stage_label = QtWidgets.QLabel()
        right_layout.addWidget(self.stage_label)

        self.finalize_btn = QtWidgets.QPushButton("Finalize Polygon")
        self.finalize_btn.clicked.connect(self.finalize_polygon)
        right_layout.addWidget(self.finalize_btn)

        self.clear_btn = QtWidgets.QPushButton("Clear Points")
        self.clear_btn.clicked.connect(self.clear_points)
        right_layout.addWidget(self.clear_btn)

        self.delete_btn = QtWidgets.QPushButton("Delete Last Polygon")
        self.delete_btn.clicked.connect(self.delete_last_polygon)
        right_layout.addWidget(self.delete_btn)

        self.next_btn = QtWidgets.QPushButton("Next Stage")
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self.next_stage)
        right_layout.addWidget(self.next_btn)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        right_layout.addWidget(cancel_btn)
        right_layout.addStretch()

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setFixedWidth(250)
        main_layout.addWidget(right_widget, stretch=0)

    def on_click(self, x, y):
        label_w, label_h = self.image_label.width(), self.image_label.height()
        img_h, img_w = self.frozen_frame.shape[:2]
        scale = min(label_w / img_w, label_h / img_h)
        new_w, new_h = int(img_w * scale), int(img_h * scale)
        x0 = (label_w - new_w) // 2
        y0 = (label_h - new_h) // 2
        if x < x0 or x > x0 + new_w or y < y0 or y > y0 + new_h:
            return
        px = int((x - x0) / scale)
        py = int((y - y0) / scale)
        self.current_points.append([px, py])
        self.update_display()

    def update_display(self):
        img = self.frozen_frame.copy()
        colors = {"crosswalk": (0, 255, 255), "car_wait": (255, 102, 102), "pedes_wait": (0, 153, 0)}
        for typ, polys in self.polygons.items():
            for pts in polys:
                arr = np.array(pts, np.int32).reshape((-1, 1, 2))
                cv2.polylines(img, [arr], True, colors[typ], 2)
        for pt in self.current_points:
            cv2.circle(img, tuple(pt), 4, (0, 0, 255), -1)
        qimg = QtGui.QImage(img.data, img.shape[1], img.shape[0], img.strides[0], QtGui.QImage.Format_BGR888)
        pix = QtGui.QPixmap.fromImage(qimg)
        self.image_label.setPixmap(pix.scaled(self.image_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        typ, minc, maxc = self.stage_info[self.stage]
        count = len(self.polygons[typ])
        self.stage_label.setText(f"Stage {self.stage+1}/3: {typ.replace('_',' ').title()} ({count} of {maxc})")

    def finalize_polygon(self):
        if len(self.current_points) < 3:
            QtWidgets.QMessageBox.warning(self, "Warning", "Need at least 3 points.")
            return
        typ, minc, maxc = self.stage_info[self.stage]
        if len(self.polygons[typ]) >= maxc:
            QtWidgets.QMessageBox.warning(self, "Warning", f"Max {maxc} polygons for {typ}.")
            return
        self.polygons[typ].append(self.current_points.copy())
        self.current_points.clear()
        if len(self.polygons[typ]) >= minc:
            self.next_btn.setEnabled(True)
        self.update_display()
        self.refresh_poly_list()

    def delete_last_polygon(self):
        typ, minc, maxc = self.stage_info[self.stage]
        if self.polygons[typ]:
            self.polygons[typ].pop()
        if len(self.polygons[typ]) < minc:
            self.next_btn.setEnabled(False)
        self.update_display()

    def clear_points(self):
        self.current_points.clear()
        self.update_display()

    def next_stage(self):
        """
        Proceed to the next drawing stage or, on the last click,
        build and store the crosswalk pack.
        """
        typ, minc, maxc = self.stage_info[self.stage]
        if len(self.polygons[typ]) < minc:
            return

        # ───────── Move to next stage ─────────
        if self.stage < 2:
            self.stage += 1
            self.current_points.clear()
            next_typ, next_min, next_max = self.stage_info[self.stage]
            if len(self.polygons[next_typ]) >= next_min:
                self.next_btn.setEnabled(True)
            if self.stage == 2:
                self.next_btn.setText("Finish Pack")
            self.update_display()
            return

        # ───────── Last stage → commit pack ─────────
        pack = self.editor.new_pack()  # create new CrosswalkPack
        for rtype, polys in self.polygons.items():
            for pts in polys:
                self.editor.add_polygon({
                    "type": rtype,
                    "points": pts,
                    "pack_id": pack.id
                })

        self.editor.save_polygons()
        self.accept()
