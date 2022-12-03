import json
import os
import time
from datetime import datetime, timedelta, timezone
from math import floor
from queue import Queue
from urllib import request

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication, QMainWindow

from mbta_tracker_gui import Ui_mbta_tracker_window

os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
try:
    with open('api_key.env', 'r') as f:
        API_KEY = f.readlines()[0]
        print(API_KEY)
except FileNotFoundError:
    API_KEY = ''
    
rides = Queue(maxsize=3)


class MBTAStop:
    def __init__(self, route, stop, direction, method):
        stop_converter = json.load(open('stops.json'))
        self.route = route
        self.name = stop
        self.stop = stop_converter[stop]
        self.method = method.lower()
        
        if self.method == 'predictions':
            self.sort = 'departure_time'
        elif self.method == 'schedules':
            self.sort = 'arrival_time'
            
        if direction == 'Inbound':
            self.direction = '0'
        elif direction == 'Outbound':
            self.direction = '1'

    def generate_url(self):
        return (
                'https://api-v3.mbta.com/'
                + self.method
                + '?filter[stop]='
                + self.stop
                + '&route='
                + self.route
                + '&direction_id='
                + self.direction
                + '&sort='
                + self.sort
                + '&api_key='
                + API_KEY
        )
        


class RideTracker(QObject):
    ride_1_sig_1 = pyqtSignal(str)
    ride_1_sig_2 = pyqtSignal(str)
    ride_2_sig_1 = pyqtSignal(str)
    ride_2_sig_2 = pyqtSignal(str)
    ride_3_sig_1 = pyqtSignal(str)
    ride_3_sig_2 = pyqtSignal(str)
    ride_1_label = pyqtSignal(str)
    ride_2_label = pyqtSignal(str)
    ride_3_label = pyqtSignal(str)
    timer_update = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self.ride_1_sig_1.connect(gui.ride_1_box_1.setPlainText)
        self.ride_1_sig_2.connect(gui.ride_1_box_2.setPlainText)
        self.ride_2_sig_1.connect(gui.ride_2_box_1.setPlainText)
        self.ride_2_sig_2.connect(gui.ride_2_box_2.setPlainText)
        self.ride_3_sig_1.connect(gui.ride_3_box_1.setPlainText)
        self.ride_3_sig_2.connect(gui.ride_3_box_2.setPlainText)
        self.ride_1_label.connect(gui.ride_1.setTitle)
        self.ride_2_label.connect(gui.ride_2.setTitle)
        self.ride_3_label.connect(gui.ride_3.setTitle)
        self.timer_update.connect(gui.refresh_lcd.display)
        
        self.ride_labels = [
                self.ride_1_label,
                self.ride_2_label,
                self.ride_3_label
        ]
        
        self.box_signals = [
                self.ride_1_sig_1,
                self.ride_1_sig_2,
                self.ride_2_sig_1,
                self.ride_2_sig_2,
                self.ride_3_sig_1,
                self.ride_3_sig_2
        ]
    
    @pyqtSlot()
    def run(self):
        while True:
            for station in range(rides.qsize()):
                ride_name = rides.queue[station].name
                self.ride_labels[station].emit(ride_name)
                api_url = rides.queue[station].generate_url()
                with request.urlopen(api_url) as url:
                    mbta_info = json.load(url)
                k = 0
                break_flag = None
                try:
                    for col in range(2):
                        if break_flag:
                            break
                        status = mbta_info['data'][col]['attributes']['status']
                        while True:
                            departure_time = mbta_info['data'][col + k]['attributes']['departure_time']
                            dt = datetime.now(timezone.utc) - timedelta(hours=5, minutes=0)
                            try:
                                formatted_time = datetime.fromisoformat(
                                        departure_time.replace('T', ' ')[:-6]
                                        + '+00:00'
                                )
                            except AttributeError:
                                continue
                            formatted_time -= dt
                            display_time = floor(formatted_time.total_seconds() / 60)
                            if display_time < 0:
                                k += 1
                            else:
                                break
                        if not status:
                            if display_time > 0:
                                minute = ' minute' if display_time == 1 else ' minutes'
                                self.box_signals[station * 2 + col].emit(
                                        ' '
                                        + str(display_time)
                                        + minute
                                )
                            else:
                                self.box_signals[station * 2 + col].emit(' Arriving')
                            
                except IndexError:
                    continue
                    
            lcd_value = 3
            while lcd_value > 0:
                self.timer_update.emit(lcd_value)
                lcd_value -= 1
                time.sleep(1)


def generate_stop():
    if rides.qsize() == 3:
        rides.get()
    rides.put(MBTAStop(
            gui.route_box.currentText(),
            gui.stop_box.currentText(),
            gui.direction_box.currentText(),
            gui.method_box.currentText()
    ))  


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
    populate_stops()
    gui.route_box.currentTextChanged.connect(populate_stops)
    gui.direction_box.addItems(['Inbound', 'Outbound'])
    gui.method_box.addItems(['Schedules', 'Predictions'])
    gui.display_button.clicked.connect(generate_stop)
    
    gui.thread = QThread()
    gui.worker = RideTracker()
    gui.worker.moveToThread(gui.thread)
    gui.thread.started.connect(gui.worker.run)
    gui.thread.start()
    window.show()
    app.exec()