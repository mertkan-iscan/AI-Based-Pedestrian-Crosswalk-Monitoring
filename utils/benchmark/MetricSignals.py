from PyQt5.QtCore import QObject, pyqtSignal

class MetricSignals(QObject):
    frame_logged      = pyqtSignal()
    detection_logged  = pyqtSignal(float)   # dt
    inspection_logged = pyqtSignal(float)   # dt
    delay_logged      = pyqtSignal(float)   # dt

signals = MetricSignals()