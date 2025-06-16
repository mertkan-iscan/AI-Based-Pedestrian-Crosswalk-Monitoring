import sys

from PyQt5 import QtWidgets
from PyQt5.QtCore import QThread

from gui.windows.MainWindow import MainWindow

from utils.benchmark.MetricSignals   import signals
from utils.benchmark.MetricReporter  import MetricReporter


def main():

    metrics_thread = QThread()
    reporter = MetricReporter()
    reporter.moveToThread(metrics_thread)

    signals.frame_logged.connect(     reporter.on_frame)
    signals.detection_logged.connect( reporter.on_detection)
    signals.inspection_logged.connect(reporter.on_inspection)
    signals.delay_logged.connect(     reporter.on_delay)

    metrics_thread.start()

    app = QtWidgets.QApplication(sys.argv)

    window = MainWindow()

    def shutdown():

        metrics_thread.quit()
        metrics_thread.wait()


    app.aboutToQuit.connect(shutdown)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
