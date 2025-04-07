import cv2
from PyQt5 import QtCore, QtGui
from stream.LiveStream import VideoStreamProcessor

class VideoStreamThread(QtCore.QThread):
    frame_ready = QtCore.pyqtSignal(QtGui.QImage)
    objects_ready = QtCore.pyqtSignal(list)
    latency_info = QtCore.pyqtSignal(float, float)  # New signal: (frame timing latency, inference latency)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, stream_url, polygons_file, parent=None):
        super(VideoStreamThread, self).__init__(parent)
        self.stream_url = stream_url
        self.polygons_file = polygons_file
        self._is_running = True

    def run(self):
        try:
            processor = VideoStreamProcessor(self.stream_url, self.polygons_file)
            for img, detected_objects, frame_latency, inference_latency in processor.stream_generator():
                if not self._is_running:
                    break

                # Convert BGR to RGB for Qt.
                rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                height, width, channel = rgb_image.shape
                bytes_per_line = 3 * width
                q_img = QtGui.QImage(rgb_image.data, width, height, bytes_per_line,
                                     QtGui.QImage.Format_RGB888).copy()

                self.frame_ready.emit(q_img)
                self.objects_ready.emit(detected_objects)
                self.latency_info.emit(frame_latency, inference_latency)
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()
