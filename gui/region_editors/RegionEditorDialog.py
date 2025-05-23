import os
import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from gui.region_editors.CrosswalkPackEditorDialog import CrosswalkPackEditorDialog
from utils.RegionManager import RegionManager


class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal(int, int)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit(event.x(), event.y())
        super().mousePressEvent(event)


class RegionEditorDialog(QtWidgets.QDialog):
    def __init__(self, frozen_frame, parent=None, region_editor: RegionManager = None):
        super().__init__(parent)
        self.editor = region_editor
        self.highlight = None
        self.setWindowTitle("Region Editing")

        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.WindowSystemMenuHint |
            QtCore.Qt.WindowMinimizeButtonHint |
            QtCore.Qt.WindowMaximizeButtonHint |
            QtCore.Qt.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(True)

        self.frozen_frame = frozen_frame.copy()
        self.current_points = []
        self.current_region_type = "detection_blackout"

        self.initUI()
        self.refresh_poly_list()
        self.update_display()
        self.showMaximized()

    def initUI(self):
        main_layout = QtWidgets.QHBoxLayout(self)

        # Left: Image display
        left_layout = QtWidgets.QVBoxLayout()
        self.image_label = ClickableLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        self.image_label.clicked.connect(self.on_click)
        left_layout.addWidget(self.image_label)
        main_layout.addLayout(left_layout, 4)

        # Right: Controls and tree list
        right_layout = QtWidgets.QVBoxLayout()

        # Region type selection
        region_type_group = QtWidgets.QGroupBox("Select Region Type")
        grid = QtWidgets.QGridLayout()
        types = [
            ("Detection Blackout", "detection_blackout"),
            ("Road", "road"),
            ("Sidewalk", "sidewalk"),
            ("Deletion Area", "deletion_area"),
            ("Deletion Line", "deletion_line")
        ]
        for i, (txt, t) in enumerate(types):
            btn = QtWidgets.QPushButton(txt)
            btn.clicked.connect(lambda _, r=t: self.set_region_type(r))
            grid.addWidget(btn, i // 2, i % 2)
        pack_btn = QtWidgets.QPushButton("Add Crosswalk Pack")
        pack_btn.clicked.connect(self.open_crosswalk_pack_editor)
        grid.addWidget(pack_btn, (len(types)) // 2, (len(types)) % 2)
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

        # Tree list of existing polygons and packs
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Group", "ID"])
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.itemClicked.connect(self.on_tree_item_click)
        right_layout.addWidget(self.tree, 1)

        # Delete button handles both single and pack deletion
        del_btn = QtWidgets.QPushButton("Delete Selected")
        del_btn.clicked.connect(self.delete_selected_polygon)
        right_layout.addWidget(del_btn)

        # Exit button
        exit_btn = QtWidgets.QPushButton("Exit Editing")
        exit_btn.clicked.connect(self.accept)
        right_layout.addWidget(exit_btn)
        right_layout.addStretch()

        # Container for controls
        container = QtWidgets.QWidget()
        container.setLayout(right_layout)
        container.setFixedWidth(250)
        main_layout.addWidget(container, stretch=0)

    def on_tree_item_click(self, item, column):
        """
        Store the selected region's data tuple so we can highlight it.
        UserRole data is (rtype, poly_id, pack_id).
        """
        self.highlight = item.data(0, QtCore.Qt.UserRole)
        self.update_display()

    def refresh_poly_list(self):
        self.tree.clear()
        for pack in self.editor.crosswalk_packs:
            parent = QtWidgets.QTreeWidgetItem(self.tree, [f"Pack {pack.id}", ""])
            parent.setData(0, QtCore.Qt.UserRole, ("pack", pack.id))
            if pack.crosswalk:
                cw = pack.crosswalk
                item = QtWidgets.QTreeWidgetItem(parent, ["crosswalk", str(cw["id"])])
                item.setData(0, QtCore.Qt.UserRole, ("crosswalk", cw["id"], pack.id))
            for p in pack.pedes_wait:
                item = QtWidgets.QTreeWidgetItem(parent, ["pedes_wait", str(p["id"])])
                item.setData(0, QtCore.Qt.UserRole, ("pedes_wait", p["id"], pack.id))
            for p in pack.car_wait:
                item = QtWidgets.QTreeWidgetItem(parent, ["car_wait", str(p["id"])])
                item.setData(0, QtCore.Qt.UserRole, ("car_wait", p["id"], pack.id))
            groups = {}
            for tl in pack.traffic_light:
                groups.setdefault(tl["id"], []).append(tl)
            for gid, items in groups.items():
                tl_item = QtWidgets.QTreeWidgetItem(parent, ["traffic_light", str(gid)])
                tl_item.setData(0, QtCore.Qt.UserRole, ("traffic_light", gid, pack.id))
                for tl in items:
                    ci = QtWidgets.QTreeWidgetItem(tl_item, [tl["signal_color"], ""])
                    ci.setData(0, QtCore.Qt.UserRole, ("traffic_light", gid, pack.id))
        for rtype, regions in self.editor.other_regions.items():
            parent = QtWidgets.QTreeWidgetItem(self.tree, [rtype, ""])
            parent.setData(0, QtCore.Qt.UserRole, (rtype, None, None))
            for reg in regions:
                item = QtWidgets.QTreeWidgetItem(parent, [rtype, str(reg["id"])])
                item.setData(0, QtCore.Qt.UserRole, (rtype, reg["id"], None))
        self.tree.expandAll()

    def delete_selected_polygon(self):
        item = self.tree.currentItem()
        if not item:
            QtWidgets.QMessageBox.information(self, "Info", "No item selected.")
            return
        data = item.data(0, QtCore.Qt.UserRole)
        if not data:
            return
        # if a pack header, delete the entire pack
        if data[0] == "pack":
            pack_id = data[1]
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm Deletion",
                f"Delete entire Pack {pack_id} and all its polygons?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                if self.editor.delete_pack(pack_id):
                    self.editor.save_polygons()
                    self.refresh_poly_list()
                    self.update_display()
            return
        # otherwise delete a single polygon
        rtype, pid, pack_id = data
        if self.editor.delete_polygon(rtype, pid, pack_id):
            self.editor.save_polygons()
            self.refresh_poly_list()
            self.update_display()

    def reset_polygons(self):
        self.editor.clear_all()
        if self.editor.polygons_file and os.path.exists(self.editor.polygons_file):
            os.remove(self.editor.polygons_file)
        self.refresh_poly_list()
        self.update_display()

    def on_click(self, x, y):
        lw, lh = self.image_label.width(), self.image_label.height()
        ih, iw = self.frozen_frame.shape[:2]
        scale = min(lw / iw, lh / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        x0, y0 = (lw - nw) // 2, (lh - nh) // 2
        if x < x0 or x > x0 + nw or y < y0 or y > y0 + nh:
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
        dlg = CrosswalkPackEditorDialog(
            self.frozen_frame,
            parent=self,
            region_manager=self.editor
        )
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.refresh_poly_list()
            self.update_display()

    def update_display(self):
        img = self.frozen_frame.copy()
        img = self.editor.overlay_regions(img, alpha=0.4)

        # draw in-progress polygon points and lines
        for pt in self.current_points:
            cv2.circle(img, (int(pt[0]), int(pt[1])), 5, (0, 0, 255), -1)
        if len(self.current_points) > 1:
            pts = np.array(self.current_points, np.int32).reshape(-1, 1, 2)
            if self.current_region_type == "deletion_line":
                cv2.polylines(img, [pts], False, (0, 255, 255), 3)
            else:
                cv2.polylines(img, [pts], False, (0, 0, 255), 1)

        pack_cols = {
            "crosswalk": (0, 255, 255),
            "pedes_wait": (0, 153, 0),
            "car_wait": (255, 102, 102)
        }
        other_cols = {
            "detection_blackout": (50, 50, 50),
            "road": (50, 50, 50),
            "sidewalk": (255, 255, 0),
            "deletion_area": (255, 0, 255),
            "deletion_line": (0, 255, 255)  # CYAN
        }

        for pack in self.editor.crosswalk_packs:
            if pack.crosswalk:
                cw = pack.crosswalk
                pts = np.array(cw["points"], np.int32).reshape(-1, 1, 2)
                cv2.polylines(img, [pts], True, pack_cols["crosswalk"], 2)
                cx = int(sum(p[0] for p in cw["points"]) / len(cw["points"]))
                cy = int(sum(p[1] for p in cw["points"]) / len(cw["points"]))
                cv2.putText(img, f"{pack.id}-{cw['id']}", (cx, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                if self.highlight == ("crosswalk", cw["id"], pack.id):
                    cv2.polylines(img, [pts], True, (0, 0, 255), 4)

            for p in pack.pedes_wait:
                pts = np.array(p["points"], np.int32).reshape(-1, 1, 2)
                cv2.polylines(img, [pts], True, pack_cols["pedes_wait"], 2)
                cx = int(sum(pt[0] for pt in p["points"]) / len(p["points"]))
                cy = int(sum(pt[1] for pt in p["points"]) / len(p["points"]))
                cv2.putText(img, f"{pack.id}-{p['id']}", (cx, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                if self.highlight == ("pedes_wait", p["id"], pack.id):
                    cv2.polylines(img, [pts], True, (0, 0, 255), 4)

            for p in pack.car_wait:
                pts = np.array(p["points"], np.int32).reshape(-1, 1, 2)
                cv2.polylines(img, [pts], True, pack_cols["car_wait"], 2)
                cx = int(sum(pt[0] for pt in p["points"]) / len(p["points"]))
                cy = int(sum(pt[1] for pt in p["points"]) / len(p["points"]))
                cv2.putText(img, f"{pack.id}-{p['id']}", (cx, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                if self.highlight == ("car_wait", p["id"], pack.id):
                    cv2.polylines(img, [pts], True, (0, 0, 255), 4)

            groups = {}
            for tl in pack.traffic_light:
                groups.setdefault(tl["id"], []).append(tl)
            for gid, lights in groups.items():
                cx = int(sum(l["center"][0] for l in lights) / len(lights))
                cy = int(sum(l["center"][1] for l in lights) / len(lights))
                cv2.putText(img, f"{pack.id}-{gid}", (cx, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                if self.highlight == ("traffic_light", gid, pack.id):
                    cv2.circle(img, (cx, cy), 20, (0, 0, 255), 3)
                for lt in lights:
                    cv2.circle(img, tuple(lt["center"]), lt["radius"], (0, 0, 255), 2)

        for rtype, regs in self.editor.other_regions.items():
            col = other_cols.get(rtype, (255, 255, 255))
            for poly in regs:
                pts = np.array(poly["points"], np.int32).reshape(-1, 1, 2)
                if rtype == "deletion_line":
                    cv2.polylines(img, [pts], False, col, 3)
                else:
                    cv2.polylines(img, [pts], True, col, 2)
                cx = int(sum(pt[0] for pt in poly["points"]) / len(poly["points"]))
                cy = int(sum(pt[1] for pt in poly["points"]) / len(poly["points"]))
                cv2.putText(img, f"{rtype}-{poly['id']}", (cx, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                if self.highlight == (rtype, poly["id"], None):
                    if rtype == "deletion_line":
                        cv2.polylines(img, [pts], False, (0, 0, 255), 4)
                    else:
                        cv2.polylines(img, [pts], True, (0, 0, 255), 4)
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

    def finalize_polygon(self):
        min_points = 2 if self.current_region_type == "deletion_line" else 3
        if len(self.current_points) < min_points:
            QtWidgets.QMessageBox.warning(self, "Warning", f"Need at least {min_points} points.")
            return
        poly = {
            "type": self.current_region_type,
            "points": self.current_points.copy()
        }
        self.editor.add_polygon(poly)
        self.editor.save_polygons()
        self.current_points.clear()
        self.refresh_poly_list()
        self.update_display()


    def clear_points(self):
        self.current_points.clear()
        self.update_display()

    def resizeEvent(self, event):
        self.update_display()
        super().resizeEvent(event)
