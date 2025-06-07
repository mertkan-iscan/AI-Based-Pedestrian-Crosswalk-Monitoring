import cv2, numpy as np, math
from PyQt5 import QtCore, QtGui, QtWidgets


class ClickableLabel(QtWidgets.QLabel):
    pressed = QtCore.pyqtSignal(int, int)
    moved = QtCore.pyqtSignal(int, int)
    released = QtCore.pyqtSignal(int, int)
    clicked = QtCore.pyqtSignal(int, int)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self.pressed.emit(e.x(), e.y())
            self.clicked.emit(e.x(), e.y())
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if e.buttons() & QtCore.Qt.LeftButton:
            self.moved.emit(e.x(), e.y())
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self.released.emit(e.x(), e.y())
        super().mouseReleaseEvent(e)


class CrosswalkPackEditorDialog(QtWidgets.QDialog):
    def __init__(self, frozen_frame, parent=None, region_manager=None):
        super().__init__(parent)
        self.manager = region_manager
        self.manager.load_polygons()
        self.frozen_frame = frozen_frame.copy()
        self.current_points = []
        self.polygons = {
            "crosswalk": [],
            "car_wait": [],
            "pedes_wait": [],
            "traffic_lights": []
        }

        self._max_counts = {
            "crosswalk": 1,
            "car_wait": 2,
            "pedes_wait": 2
        }

        self.mode = "polygon"
        self.stage = 0
        self.circle_temp = []
        self.initUI()
        self.image_label.pressed.connect(self.on_press)
        self.image_label.moved.connect(self.on_move)
        self.image_label.released.connect(self.on_release)
        self.image_label.clicked.connect(self.on_click)
        self.showMaximized()
        QtCore.QTimer.singleShot(0, self.update_display)

    def initUI(self):
        self.setWindowTitle("Add Crosswalk Pack")
        main_layout = QtWidgets.QHBoxLayout(self)
        left = QtWidgets.QVBoxLayout()
        self.image_label = ClickableLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        left.addWidget(self.image_label)
        main_layout.addLayout(left, 4)

        right = QtWidgets.QVBoxLayout()
        self.stage_label = QtWidgets.QLabel()
        right.addWidget(self.stage_label)
        self.finalize_btn = QtWidgets.QPushButton("Finalize")
        self.finalize_btn.clicked.connect(self.finalize)
        right.addWidget(self.finalize_btn)
        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_temp)
        right.addWidget(self.clear_btn)
        self.next_btn = QtWidgets.QPushButton("Next")
        self.next_btn.clicked.connect(self.next_phase)
        right.addWidget(self.next_btn)
        self.add_light_btn = QtWidgets.QPushButton("Add Traffic Light")
        self.add_light_btn.clicked.connect(self.start_light)
        self.add_light_btn.setVisible(False)
        right.addWidget(self.add_light_btn)

        save_btn = QtWidgets.QPushButton("Save & Close")
        save_btn.clicked.connect(self.save_and_close)
        right.addWidget(save_btn)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        right.addWidget(cancel_btn)
        right.addStretch()

        panel = QtWidgets.QWidget()
        panel.setLayout(right)
        panel.setFixedWidth(250)
        main_layout.addWidget(panel)

    def showEvent(self, event):
        super().showEvent(event)
        self.update_display()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_display()

    def map_coords(self, x, y):
        w, h = self.image_label.width(), self.image_label.height()
        ih, iw = self.frozen_frame.shape[:2]
        scale = min(w / iw, h / ih)
        x0, y0 = (w - iw * scale) / 2, (h - ih * scale) / 2
        return int((x - x0) / scale), int((y - y0) / scale)

    def on_click(self, x, y):
        if self.mode == "polygon":
            self.current_points.append(self.map_coords(x, y))
            self.update_display()

    def on_press(self, x, y):
        if self.mode == "light":
            pt = self.map_coords(x, y)
            self.circle_temp = [pt, pt]

    def on_move(self, x, y):
        if self.mode == "light" and self.circle_temp:
            self.circle_temp[1] = self.map_coords(x, y)
            self.update_display()

    def on_release(self, x, y):
        if self.mode == "light" and self.circle_temp:
            self.circle_temp[1] = self.map_coords(x, y)
            self.update_display()

    def update_display(self):
        img = self.frozen_frame.copy()
        img = self.manager.overlay_regions(img, alpha=0.4)

        cols = {
            "crosswalk": (0, 255, 255),
            "car_wait": (255, 102, 102),
            "pedes_wait": (0, 153, 0)
        }
        phases = ["crosswalk", "car_wait", "pedes_wait"]

        # 1) Draw completed polygons
        for key in phases:
            for poly in self.polygons[key]:
                pts = np.array(poly, np.int32).reshape(-1, 1, 2)
                cv2.polylines(img, [pts], True, cols[key], 2)

        # 2) Draw finished traffic-light groups
        for lt in self.polygons["traffic_lights"]:
            for c in lt["lights"].values():
                cv2.circle(img, tuple(c["center"]), c["radius"], (0, 0, 255), 2)

        # 3) Draw any circles in the current_light
        if self.mode == "light" and getattr(self, "current_light", None):
            for c in self.current_light["lights"].values():
                cv2.circle(img, tuple(c["center"]), c["radius"], (0, 0, 255), 2)

        # 4) In-progress polygon
        if self.mode == "polygon" and self.stage < len(phases) and self.current_points:
            key = phases[self.stage]
            pts = np.array(self.current_points, np.int32).reshape(-1, 1, 2)
            cv2.polylines(img, [pts], False, cols[key], 2)
            for p in self.current_points:
                cv2.circle(img, tuple(p), 5, cols[key], -1)

        # 5) In-progress circle
        if self.mode == "light" and len(self.circle_temp) == 2:
            c1, c2 = self.circle_temp
            r = int(math.hypot(c2[0] - c1[0], c2[1] - c1[1]))
            cv2.circle(img, c1, r, (0, 0, 255), 2)

        # 6) Blit to label
        qimg = QtGui.QImage(
            img.data, img.shape[1], img.shape[0], img.strides[0],
            QtGui.QImage.Format_BGR888
        )
        pix = QtGui.QPixmap.fromImage(qimg).scaled(
            self.image_label.size(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
        self.image_label.setPixmap(pix)

        # 7) Update status text
        if self.mode == "polygon":
            if self.stage < len(phases):
                key = phases[self.stage]
                drawn = len(self.polygons[key])
                self.stage_label.setText(f"Draw {key} — {drawn}/{self._max_counts[key]} completed")
            else:
                # we've somehow gone past, show ready for lights
                self.stage_label.setText("Ready for Traffic Lights")
        else:
            # light mode
            if getattr(self, "current_light", None):
                colors = (
                    ["red", "yellow", "green"]
                    if self.current_light["type"] == "vehicle"
                    else ["red", "green"]
                )
                placed = len(self.current_light["lights"])
                total = len(colors)
                if placed < total:
                    nc = colors[placed]
                    self.stage_label.setText(f"Draw {nc} circle ({placed}/{total})")
                else:
                    self.stage_label.setText("All circles done — click Finalize")
            else:
                self.stage_label.setText("Click ‘Add Traffic Light’ to begin")

    def next_phase(self):
        # Only applies in polygon‐mode
        if self.mode != "polygon":
            return

        key_list = ["crosswalk", "car_wait", "pedes_wait"]
        key = key_list[self.stage]

        # If there are any un‐finalized points, commit them now
        if self.current_points:
            self.polygons[key].append(list(self.current_points))
        self.current_points.clear()

        # Enforce the per‐stage rules (min/max) before advancing...
        cnt = len(self.polygons[key])
        # crosswalk: must have exactly 1
        if key == "crosswalk" and cnt != 1:
            QtWidgets.QMessageBox.warning(self, "Warning", "Draw exactly one crosswalk.")
            return
        # car_wait: can be 0–2
        if key == "car_wait" and cnt > self._max_counts[key]:
            QtWidgets.QMessageBox.warning(self, "Warning", "At most 2 car_wait regions allowed.")
            return
        # pedes_wait: must have 1–2
        if key == "pedes_wait" and (cnt < 1 or cnt > self._max_counts[key]):
            QtWidgets.QMessageBox.warning(self, "Warning", "Draw 1–2 pedestrian_wait regions.")
            return

        # Advance stage
        self.stage += 1
        if self.stage >= len(key_list):
            # Enter traffic‐light mode
            self.mode = "light"
            self.add_light_btn.setVisible(True)
        self.update_display()

    def start_light(self):
        dlg = QtWidgets.QInputDialog(self)
        dlg.setComboBoxItems(["vehicle", "pedestrian"])
        dlg.setWindowTitle("Choose Type")
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        self.light_type = dlg.textValue()
        self.req_count = 3 if self.light_type == "vehicle" else 2
        self.current_light = {"id": None, "type": self.light_type, "lights": {}}
        self.mode = "light"
        self.add_light_btn.setVisible(False)
        self.update_display()

    def finalize(self):
        # POLYGON MODE
        if self.mode == "polygon":
            phases = ["crosswalk", "car_wait", "pedes_wait"]
            key = phases[self.stage]

            # need 3+ points
            if len(self.current_points) < 3:
                QtWidgets.QMessageBox.warning(self, "Warning",
                                              "Need at least 3 points to finalize polygon.")
                return

            # don't exceed max
            if len(self.polygons[key]) >= self._max_counts[key]:
                QtWidgets.QMessageBox.warning(self, "Warning",
                                              f"At most {self._max_counts[key]} {key} region(s) allowed.")
                return

            # commit
            self.polygons[key].append(self.current_points.copy())
            self.current_points.clear()

            # if we've hit the max for this stage, auto-advance
            if len(self.polygons[key]) >= self._max_counts[key]:
                self.next_phase()
            else:
                self.update_display()
            return

        # LIGHT MODE
        if self.mode == "light":
            if len(self.circle_temp) != 2:
                QtWidgets.QMessageBox.warning(self, "Warning",
                                              "Draw a circle first.")
                return

            c1, c2 = self.circle_temp
            r = int(math.hypot(c2[0] - c1[0], c2[1] - c1[1]))
            colors = ["red", "yellow", "green"] if self.current_light["type"] == "vehicle" else ["red", "green"]
            idx = len(self.current_light["lights"])
            sc = colors[idx]

            # add circle
            self.current_light["lights"][sc] = {"center": c1, "radius": r}
            self.circle_temp.clear()

            # if that was the last circle, finalize the light
            if len(self.current_light["lights"]) >= len(colors):
                self.polygons["traffic_lights"].append(self.current_light)
                self.current_light = None
                # remain in light mode so you can add N lights
                self.add_light_btn.setVisible(True)

            self.update_display()
            return

    def clear_temp(self):
        if self.mode == "polygon":
            self.current_points.clear()
        else:
            self.circle_temp.clear()
        self.update_display()

    def save_and_close(self):
        pack = self.manager.new_pack()
        # set crosswalk
        cw_list = self.polygons.get("crosswalk", [])
        if cw_list:
            pack.set_crosswalk(cw_list[0])
        # set car_wait regions
        for pts in self.polygons.get("car_wait", []):
            pack.add_car_wait(pts)
        # set pedes_wait regions
        for pts in self.polygons.get("pedes_wait", []):
            pack.add_pedes_wait(pts)
        # set traffic_light groups, using pack.add_traffic_light_group()
        for lt in self.polygons.get("traffic_lights", []):
            pack.add_traffic_light_group(lt["type"], lt["lights"])
        # persist and close
        self.manager.save_polygons()
        self.accept()
