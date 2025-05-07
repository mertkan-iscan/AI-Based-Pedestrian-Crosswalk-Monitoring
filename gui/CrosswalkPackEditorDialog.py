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

class CrosswalkPackEditorDialog(QtWidgets.QDialog):
    def __init__(self, frozen_frame, parent=None, region_editor: RegionEditor = None):
        super().__init__(parent)
        self.editor = region_editor
        self.frozen_frame = frozen_frame.copy()
        self.current_points = []
        # store points or dicts with light_type
        self.polygons = {
            "crosswalk": [],
            "car_wait": [],
            "pedes_wait": [],
            "traffic_light": []
        }
        # (type, min count, max count)
        self.stage_info = [
            ("crosswalk", 1, 1),
            ("car_wait", 1, 2),
            ("pedes_wait", 1, 2),
            ("traffic_light", 1, 4)
        ]
        self.stage = 0

        # traffic-light subtype controls
        self.light_type_group = QtWidgets.QButtonGroup(self)
        self.radio_vehicle    = QtWidgets.QRadioButton("Vehicle Light")
        self.radio_pedestrian = QtWidgets.QRadioButton("Pedestrian Light")
        self.light_type_group.addButton(self.radio_vehicle)
        self.light_type_group.addButton(self.radio_pedestrian)
        self.radio_vehicle.setChecked(True)  # default vehicle

        self.setWindowTitle("Crosswalk Pack Editing")
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.WindowSystemMenuHint |
            QtCore.Qt.WindowMinimizeButtonHint |
            QtCore.Qt.WindowMaximizeButtonHint |
            QtCore.Qt.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(True)

        self.initUI()
        self.showMaximized()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_display()

    def resizeEvent(self, event):
        self.update_display()
        super().resizeEvent(event)

    def initUI(self):
        self.setWindowTitle("Add Crosswalk Pack")
        main_layout = QtWidgets.QHBoxLayout(self)

        # Image area
        left_layout = QtWidgets.QVBoxLayout()
        self.image_label = ClickableLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        self.image_label.clicked.connect(self.on_click)
        left_layout.addWidget(self.image_label)
        main_layout.addLayout(left_layout, stretch=4)

        # Controls
        right_layout = QtWidgets.QVBoxLayout()
        self.stage_label = QtWidgets.QLabel()
        right_layout.addWidget(self.stage_label)

        # traffic light radios hidden until needed
        right_layout.addWidget(self.radio_vehicle)
        right_layout.addWidget(self.radio_pedestrian)
        self.radio_vehicle.hide()
        self.radio_pedestrian.hide()

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
        w, h = self.image_label.width(), self.image_label.height()
        ih, iw = self.frozen_frame.shape[:2]
        scale = min(w/iw, h/ih)
        nx, ny = int((x - (w - iw*scale)/2)/scale), int((y - (h - ih*scale)/2)/scale)
        if nx<0 or nx>iw or ny<0 or ny>ih:
            return
        self.current_points.append([nx, ny])
        self.update_display()

    def update_display(self):
        img = self.frozen_frame.copy()
        colors = {
            "crosswalk":    (0, 255, 255),
            "car_wait":     (255, 102, 102),
            "pedes_wait":   (0, 153, 0),
            "traffic_light":(0,   0, 255)
        }
        typ, minc, maxc = self.stage_info[self.stage]
        # draw existing
        for t, polys in self.polygons.items():
            for entry in polys:
                pts = entry["points"] if t=="traffic_light" else entry
                arr = np.array(pts, np.int32).reshape((-1,1,2))
                cv2.polylines(img, [arr], True, colors[t], 2)
        # draw in-progress polyline
        if len(self.current_points)>1:
            arr = np.array(self.current_points, np.int32).reshape((-1,1,2))
            cv2.polylines(img, [arr], False, colors[typ], 1)
        # draw points
        for pt in self.current_points:
            cv2.circle(img, tuple(pt), 4, (0,0,255), -1)
        # radios visibility
        if typ=="traffic_light":
            self.radio_vehicle.show(); self.radio_pedestrian.show()
        else:
            self.radio_vehicle.hide(); self.radio_pedestrian.hide()
        # render
        qimg = QtGui.QImage(img.data, img.shape[1], img.shape[0], img.strides[0], QtGui.QImage.Format_BGR888)
        pix = QtGui.QPixmap.fromImage(qimg)
        self.image_label.setPixmap(pix.scaled(self.image_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        # label
        total = len(self.stage_info)
        count = len(self.polygons[typ])
        self.stage_label.setText(f"Stage {self.stage+1}/{total}: {typ.replace('_',' ').title()} ({count} of {maxc})")

    def finalize_polygon(self):
        typ, minc, maxc = self.stage_info[self.stage]
        if len(self.current_points)<3:
            QtWidgets.QMessageBox.warning(self, "Warning", "Need at least 3 points.")
            return
        if len(self.polygons[typ])>=maxc:
            QtWidgets.QMessageBox.warning(self, "Warning", f"Max {maxc} polygons for {typ}.")
            return
        if typ=="traffic_light":
            lt = "pedestrian" if self.radio_pedestrian.isChecked() else "vehicle"
            self.polygons[typ].append({"points":self.current_points.copy(), "light_type":lt})
        else:
            self.polygons[typ].append(self.current_points.copy())
        self.current_points.clear()
        if len(self.polygons[typ])>=minc:
            self.next_btn.setEnabled(True)
        self.update_display()

    def delete_last_polygon(self):
        typ, minc, maxc = self.stage_info[self.stage]
        if self.polygons[typ]: self.polygons[typ].pop()
        if len(self.polygons[typ])<minc: self.next_btn.setEnabled(False)
        self.update_display()

    def clear_points(self):
        self.current_points.clear()
        self.update_display()

    def next_stage(self):
        typ, minc, maxc = self.stage_info[self.stage]
        if len(self.polygons[typ])<minc: return
        # advance or finish
        if self.stage < len(self.stage_info)-1:
            self.stage +=1
            if self.stage==len(self.stage_info)-1: self.next_btn.setText("Finish Pack")
            self.current_points.clear()
            self.update_display()
            return
        # commit
        pack = self.editor.new_pack()
        for rtype, polys in self.polygons.items():
            for entry in polys:
                if rtype=="traffic_light":
                    self.editor.add_polygon({"type":rtype, "points":entry["points"], "pack_id":pack.id, "light_type":entry["light_type"]})
                else:
                    self.editor.add_polygon({"type":rtype, "points":entry, "pack_id":pack.id})
        self.editor.save_polygons()
        self.accept()
