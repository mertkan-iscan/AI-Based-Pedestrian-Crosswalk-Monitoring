# metrics/MetricReporter.py
from PyQt5.QtCore import QObject, pyqtSlot
from utils.benchmark.Benchmark import Benchmark


class MetricReporter(QObject):
    @pyqtSlot()
    def on_frame(self):
        Benchmark.instance().log_frame()

    @pyqtSlot(float)
    def on_detection(self, dt):
        Benchmark.instance().log_detection(dt)

    @pyqtSlot(float)
    def on_inspection(self, dt):
        Benchmark.instance().log_inspection(dt)

    @pyqtSlot(float)
    def on_delay(self, dt):
        Benchmark.instance().log_delay(dt)
