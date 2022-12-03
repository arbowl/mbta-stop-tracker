import ast
import json
import os
import time
from datetime import datetime, timedelta, timezone
from math import floor
from queue import Queue
from threading import Lock
from urllib import request

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication, QMainWindow

from mbta_tracker_gui import Ui_mbta_tracker_window

# Resizes for different sized screens
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
# Loads the API key
try:
    with open('api_key.env', 'r') as f:
        API_KEY = f.readlines()[0]
        API = True
except FileNotFoundError:
    API_KEY = ''
    API = None

# Creates the queue and the lock to prevent race conditions
rides = Queue(maxsize=3)
mutex = Lock()

# Translator from readable stops to stop codes
conversion_dict = {}


class MBTAStop:
    """An object which contains the information needed
    to find the T arrival time for a specific stop
    """
    def __init__(self, route, stop, direction, method):
        self.route = route
        self.name = stop
        self.stop = conversion_dict[stop]
        self.method = method.lower()
        
        # Scheduled stations use departure time
        if self.method == 'predictions':
            self.sort = 'arrival_time'
        elif self.method == 'schedules':
            self.sort = 'departure_time'
        
        # Convert direction name to direction ID
        if direction == 'Inbound':
            self.direction = '1'
        elif direction == 'Outbound':
            self.direction = '0'

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
    """The worker thread that pulls data from the MBTA and sends
    signals to the GUI containing the data to update it with
    """
    updating_sig = pyqtSignal(str)
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
        # Establishes the QObject and connects signals
        super().__init__()
        self.updating_sig.connect(gui.refreshes_in.setText)
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
        
        # The order of GUI elements to iterate through
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
            self.updating_sig.emit('Refreshes in:')
            for station in range(rides.qsize()):
                # This variable makes the additions more visually pleasing
                rides_cycle = rides.qsize() - 1
                ride_name = rides.queue[rides_cycle - station].name
                self.ride_labels[station].emit(ride_name)
                api_url = rides.queue[rides_cycle - station].generate_url()
                with request.urlopen(api_url) as url:
                    mbta_info = json.load(url)
                k = 0
                try:
                    for col in range(2):
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
            # Controls the refresh rate
            if API:
                lcd_value = 5
            else:
                lcd_value = 30
            while lcd_value > 0:
                self.timer_update.emit(lcd_value)
                lcd_value -= 1
                time.sleep(1)


def generate_stop():
    """Creates and enqueues a stop object
    """
    ride_boxes = [
            gui.ride_1,
            gui.ride_2,
            gui.ride_3
    ]
    if gui.refreshes_in.text() == 'Refreshes in:':
        gui.refreshes_in.setText('Adding stop in:')
    else:
        gui.refreshes_in.setText('Adding stops in:')
        
    mutex.acquire()
    try:
        if rides.full():
            rides.get()
        rides.put(MBTAStop(
                gui.route_box.currentText(),
                gui.stop_box.currentText(),
                gui.direction_box.currentText(),
                gui.method_box.currentText(),
        ))
        if rides.full():
            ride_boxes[0].setTitle('Loading...')
        else:
            ride_boxes[rides.qsize() - 1].setTitle('Loading...')
    finally:
        mutex.release()


def populate_stops():
    """Generates the dropdown list of stops from the line chosen
    """
    stop = gui.route_box.currentText()
    stops_url = 'https://api-v3.mbta.com/stops?filter[route]=' + stop
    list_of_stops = []
    with request.urlopen(stops_url) as url:
        stops = json.load(url)
    for stop in range(len(stops['data'])):
        stop_name = stops['data'][stop]['attributes']['name']
        stop_id = stops['data'][stop]['id']
        list_of_stops.append(stop_name)
        conversion_dict[stop_name] = stop_id
    gui.stop_box.clear()
    gui.stop_box.addItems(list_of_stops)
    

def save_current_ride():
    """Saves the current stop info for however many GUI elements
    """
    save_list = []
    for item in range(rides.qsize()):
        save_list.append([
                rides.queue[item].route,
                rides.queue[item].name,
                rides.queue[item].direction,
                rides.queue[item].method
        ])
    with open('favorites.asc', 'w') as file_to_save:
        file_to_save.write(str(conversion_dict) + '\n')
        for item in save_list:
            file_to_save.write(str(item) + '\n')


def load_saved_rides():
    """Loads rides from a text file and parses
    """
    mutex.acquire()
    for _ in range(rides.qsize()):
        rides.get()
    try:
        with open('favorites.asc', 'r') as file_to_read:
            favorites = file_to_read.readlines()
        for idx, line in enumerate(favorites):
            if idx == 0:
                global conversion_dict
                conversion_dict = ast.literal_eval(line)
            else:
                line = ast.literal_eval(line)
                line[2] = 'Inbound' if line[2] == '1' else 'Outbound'
                rides.put(MBTAStop(
                        line[0],
                        line[1],
                        line[2],
                        line[3]
                ))
    except FileNotFoundError:
        pass
    finally:
        mutex.release()


if __name__ == '__main__':
    app = QApplication([])
    window = QMainWindow()
    gui = Ui_mbta_tracker_window()
    gui.setupUi(window)
    
    # Populates the dropdowns
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
    gui.method_box.addItems(['Predictions', 'Schedules'])
    
    # Initializes the buttons
    gui.display_button.clicked.connect(generate_stop)
    gui.favorites_button.clicked.connect(save_current_ride)
    gui.restore_button.clicked.connect(load_saved_rides)
    
    gui.thread = QThread()
    gui.worker = RideTracker()
    gui.worker.moveToThread(gui.thread)
    gui.thread.started.connect(gui.worker.run)
    gui.thread.start()
    window.show()
    app.exec()
