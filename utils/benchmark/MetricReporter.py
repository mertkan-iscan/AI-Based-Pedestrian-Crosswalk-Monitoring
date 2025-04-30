# utils/benchmark/MetricReporter.py
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

    # NEW slots:
    @pyqtSlot(float)
    def on_queue_wait(self, dt):
        Benchmark.instance().log_queue_wait(dt)

    @pyqtSlot(float)
    def on_postproc(self, dt):
        Benchmark.instance().log_postproc(dt)

    @pyqtSlot(float)
    def on_scheduling(self, dt):
        Benchmark.instance().log_scheduling_delay(dt)

    @pyqtSlot(float)
    def on_total_latency(self, dt):
        Benchmark.instance().log_total_latency(dt)

    @pyqtSlot(float)
    def on_consumer(self, dt):
        Benchmark.instance().log_consumer_latency(dt)
