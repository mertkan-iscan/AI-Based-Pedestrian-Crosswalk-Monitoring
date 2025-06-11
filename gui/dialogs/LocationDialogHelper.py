import os
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QFileDialog

from gui.dialogs.CropDialog import CropDialog
from gui.dialogs.HomographySetterDialog import HomographySetterDialog
from stream.SingleFrameExtractor import SingleFrameExtractor

class LocationDialogHelper:
    def browse_video_file(self, line_edit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mkv *.mov)"
        )
        if path:
            line_edit.setText(path)

    def browse_bird_image(self, preview_label, set_path_attr='bird_image_path'):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Bird’s-Eye Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return
        dlg = CropDialog(path, self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        cropped = dlg.getCropped()
        name, ext = os.path.splitext(os.path.basename(path))
        save_dir = os.path.join(os.getcwd(), "resources", "satellite_images")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"{name}_cropped{ext}")
        cropped.save(save_path)
        setattr(self, set_path_attr, save_path)
        preview_label.setPixmap(QtGui.QPixmap(save_path))

    def set_homography(self, video_radio, video_path_edit, stream_edit, bird_image_path, status_label, set_matrix_attr='homography_matrix', location=None):
        if not getattr(self, bird_image_path):
            QtWidgets.QMessageBox.critical(self, "Error", "Upload a bird’s-eye image first.")
            return
        if video_radio.isChecked():
            if location is not None:
                video_path = location.get("video_path", "")
            else:
                video_path = video_path_edit.text().strip()
            frame = SingleFrameExtractor.get_single_frame_from_file(video_path)
        else:
            if location is not None:
                stream_url = location.get("stream_url", "")
            else:
                stream_url = stream_edit.text().strip()
            frame = SingleFrameExtractor.get_single_frame_from_stream(stream_url)
        if frame is None:
            QtWidgets.QMessageBox.critical(self, "Error", "Cannot grab camera frame.")
            return
        dlg = HomographySetterDialog(frame, getattr(self, bird_image_path), self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            setattr(self, set_matrix_attr, dlg.get_homography())
            status_label.setText("Homography set.")
        else:
            status_label.setText("Homography not set.")
