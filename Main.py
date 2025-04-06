import sys
import threading
from PyQt5 import QtWidgets
from gui.MainWindow import MainWindow
from detection.PathUpdater import dynamic_task_processor, task_queue
from database.DBManager import DBManager
import qdarkstyle

def main():
    db = DBManager()
    pool_size = 4

    task_processor_thread = threading.Thread(
        target=dynamic_task_processor, args=(db, pool_size)
    )

    task_processor_thread.daemon = True
    task_processor_thread.start()
    print("path DB recorder started")

    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    window = MainWindow()

    def shutdown():

        for _ in range(pool_size):
            task_queue.put(None)
        task_processor_thread.join()
        db.close()

    app.aboutToQuit.connect(shutdown)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
