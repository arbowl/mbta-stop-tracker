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


class RideTracker(QObject):
    
    def __init__(self):
        super().__init__()
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
        

def populate_stops():
    stop = gui.route_box.currentText()
    stops_url = 'https://api-v3.mbta.com/stops?filter[route]=' + stop
    list_of_stops = []
    with request.urlopen(stops_url) as url:
        stops = json.load(url)
        for stop in range(len(stops['data'])):
            list_of_stops.append(stops['data'][stop]['attributes']['name'])
    gui.stop_box.clear()
    gui.stop_box.addItems(list_of_stops)


if __name__ == '__main__':
    app = QApplication([])
    window = QMainWindow()
    gui = Ui_mbta_tracker_window()
    gui.setupUi(window)
    
    route_url = 'https://api-v3.mbta.com/routes'
    list_of_routes = []
    
    with request.urlopen(route_url) as url:
        routes = json.load(url)
        for route in range(len(routes['data'])):
            list_of_routes.append(routes['data'][route]['id'])
    gui.route_box.addItems(list_of_routes)
    gui.route_box.currentTextChanged.connect(populate_stops)
    gui.direction_box.addItems(['Inbound', 'Outbound'])
    gui.method_box.addItems(['Schedules', 'Predictions'])
            
    #gui.route_box.addItems(json.load(open('stops.json')))
    
    gui.thread = QThread()
    gui.worker = RideTracker()
    gui.worker.moveToThread(gui.thread)
    gui.thread.started.connect(gui.worker.run)
    gui.thread.start()
    window.show()
    app.exec()