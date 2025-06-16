from PyQt5.QtCore import QObject, pyqtSignal

class MetricSignals(QObject):
    frame_logged         = pyqtSignal()
    detection_logged     = pyqtSignal(float)
    inspection_logged    = pyqtSignal(float)
    delay_logged         = pyqtSignal(float)

    queue_wait_logged    = pyqtSignal(float)
    postproc_logged      = pyqtSignal(float)
    scheduling_logged    = pyqtSignal(float)
    total_latency_logged = pyqtSignal(float)
    consumer_logged      = pyqtSignal(float)

signals = MetricSignals()
