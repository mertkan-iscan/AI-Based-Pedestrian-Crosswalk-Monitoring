from PyQt5.QtCore import QObject, pyqtSignal

class MetricSignals(QObject):
    frame_logged         = pyqtSignal()
    detection_logged     = pyqtSignal(float)   # inference time
    inspection_logged    = pyqtSignal(float)   # existing region-inspection
    delay_logged         = pyqtSignal(float)   # GUI display delay

    # NEW signals:
    queue_wait_logged    = pyqtSignal(float)   # time in detection queue
    postproc_logged      = pyqtSignal(float)   # tracker + object-build
    scheduling_logged    = pyqtSignal(float)   # time spent in wait_until(self.delay)
    total_latency_logged = pyqtSignal(float)   # capture → post-schedule emit
    consumer_logged      = pyqtSignal(float)   # video consumer QImage + paint

signals = MetricSignals()
