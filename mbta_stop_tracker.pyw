from datetime import datetime, timedelta, timezone
import json
import os
import time
from urllib import request
from math import floor
from mbta_tracker_gui import Ui_mbta_tracker_window
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QThread, QObject, pyqtSignal, pyqtSlot

os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
try:
    with open('api_key.env', 'r') as f:
        API_KEY = f.readlines()[0]
        print(API_KEY)
except FileNotFoundError:
    API_KEY = ''


class RideTracker:
    
    def __init__(self):
        return
    
    @pyqtSlot()
    def run(self):
        return


class MBTAStop:
    
    def __init__(self, route, stop, direction, method):
        self.route = route
        self.stop = stop
        self.direction = direction
        self.method = method


if __name__ == '__main__':
    app = QApplication([])
    window = QMainWindow()
    gui = Ui_mbta_tracker_window()
    gui.setupUi(window)
    
    display_rides_index = 0
    gui.display_button.clicked.connect(lambda: )
    
    #gui.thread = QThread()
    #gui.worker = RideTracker()
    #gui.worker.moveToThread(gui.thread)
    #gui.thread.started.connect(gui.worker.run)
    #gui.thread.start()
    window.show()
    app.exec()