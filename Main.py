import sys
import threading
import os

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import QThread

from gui.MainWindow import MainWindow
from utils.PathUpdater import dynamic_task_processor, task_queue
from database.DBManager import DBManager

from utils.benchmark.MetricSignals   import signals
from utils.benchmark.MetricReporter  import MetricReporter

import qdarkstyle

def main():

    # db = DBManager()
    # pool_size = 4
    #
    # task_processor_thread = threading.Thread(
    #     target=dynamic_task_processor, args=(db, pool_size)
    # )
    #
    # task_processor_thread.daemon = True
    # task_processor_thread.start()
    # print("path DB recorder started")


    metrics_thread = QThread()
    reporter = MetricReporter()
    reporter.moveToThread(metrics_thread)

    signals.frame_logged.connect(     reporter.on_frame)
    signals.detection_logged.connect( reporter.on_detection)
    signals.inspection_logged.connect(reporter.on_inspection)
    signals.delay_logged.connect(     reporter.on_delay)

    metrics_thread.start()


    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

    # Set application icon
    icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'pedestrian_cross_icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QtGui.QIcon(icon_path))
    else:
        print("Icon not found at:", icon_path)

    window = MainWindow()

    def shutdown():

        # for _ in range(pool_size):
        #     task_queue.put(None)
        #
        # task_processor_thread.join()
        # db.close()

        metrics_thread.quit()
        metrics_thread.wait()


    app.aboutToQuit.connect(shutdown)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
