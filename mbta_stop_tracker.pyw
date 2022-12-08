import ast
import json
import os
import time
from datetime import datetime, timedelta, timezone
from math import floor
from queue import Queue
from urllib import request

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtGui import QIcon

from mbta_tracker_gui import Ui_mbta_tracker_window

# Resizes for different sized screens
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
# Loads the API key
try:
    with open('api_key.env', 'r') as f:
        API_KEY = f.readlines()[0]
        API = True
except:
    API_KEY = ''
    API = None

# Creates the queue and the lock to prevent race conditions
rides = Queue(maxsize=3)

# Dictionary to translate human-readable stops to MBTA API codes
conversion_dict = {}
# Two-way direction name vs. direction value dictionary
direction_dict = {
        '0' : 'Outbound',
        '1' : 'Inbound',
        'Outbound' : '0',
        'Inbound' : '1'
}


class MBTAStop:
    """An object which contains the information needed
    to find the T arrival time for a specific stop
    """
    def __init__(self, route, stop, direction, method) -> None:
        self.route = route
        self.name = stop
        self.stop = conversion_dict[stop]
        self.direction = direction_dict[direction]
        self.method = method.lower()
        
        # Scheduled stations use departure time
        if self.method == 'predictions':
            self.sort = 'arrival_time'
        elif self.method == 'schedules':
            self.sort = 'departure_time'

    def generate_url(self) -> str:
        """Creates and returns a URL based on the object's properties

        Returns:
            str: base url + parameters of the trip + api key
        """
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
    timer_update = pyqtSignal(int)
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
    
    def __init__(self) -> None:
        # Establishes the QObject and connects signals
        super().__init__()
        self.timer_update.connect(gui.refresh_lcd.display)
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
    def run(self) -> None:
        """The main logical loop of the program. Each refresh cycle, it iterates
        through the queue and downloads the data associated with each MBTA object
        and the URL associated with it. Different exceptions indicate different
        errors with the URL requested.
        """
        while True:
            self.updating_sig.emit('Refreshes in:')
            for station in range(rides.qsize()):
                # Sets up MBTA object parsing
                mbta_object = rides.queue[rides.qsize() - 1 - station]
                ride_name = mbta_object.name
                self.ride_labels[station].emit(ride_name)
                api_url = mbta_object.generate_url()

                # Gets data ready for processing
                mbta_info = json.load(request.urlopen(api_url))['data']
                num_of_rides = len(mbta_info)
                previous_status = None
                target_time = None
                display_time = None
                status = None
                # Updates each box if there is data
                for col in range(2):
                    # Length is set by size of data available
                    if num_of_rides >= col + 1:
                        for idx in range(num_of_rides):
                            # Checks stopped rides
                            if 'status' in mbta_info[col]['attributes']:
                                if mbta_info[col]['attributes']['status']:
                                    status = mbta_info[col]['attributes']['status']

                            # Skips rides that aren't stopping at this stop
                            if 'schedule_relationship' in mbta_info[col + idx]['attributes']:
                                if mbta_info[col + idx]['attributes']['schedule_relationship'] == 'SKIPPED':
                                    continue
                            
                            # Checks to see if there is a next available time for that stop
                            target_time = mbta_info[col + idx]['attributes'][mbta_object.sort]
                            if target_time:
                                formatted_time = datetime.fromisoformat(
                                        target_time.replace('T', ' ')[:-6]
                                        + '+00:00'
                                )
                            else:
                                break

                            # If a time is returned, convert it to minutes from now
                            formatted_time -= (
                                    datetime.now(timezone.utc)
                                    - timedelta(hours=5, minutes=0)
                            )
                            display_time = floor(formatted_time.total_seconds() / 60)

                            # If the converted time isn't current, skip to the next one
                            if display_time < 0:
                                continue
                            else:
                                break

                    # Logic to determine what to display for each box under each ride
                    if display_time:
                        if display_time > 0:
                            minute = ' minute' if display_time == 1 else ' minutes'
                            self.box_signals[station * 2 + col].emit(
                                    str(display_time)
                                    + minute
                            )
                        else:
                            self.box_signals[station * 2 + col].emit('Arriving')
                        if status or previous_status:
                            self.box_signals[station * 2].emit('Stopped')
                    else:
                        if num_of_rides == 0:
                            self.box_signals[station * 2 + col].emit('No data')
                        else:
                            self.box_signals[station * 2 + col].emit('')
                    previous_status = status
            
            # Refresh rate based on presence of API key
            if API:
                lcd_value = 3
            else:
                lcd_value = 15
            while lcd_value > 0:
                self.timer_update.emit(lcd_value)
                lcd_value -= 1
                time.sleep(1)


def generate_stop() -> None:
    """Creates and enqueues a stop object
    """
    ride_boxes = [
            gui.ride_1,
            gui.ride_2,
            gui.ride_3
    ]
    # Let the user know their updates are loading
    if gui.refreshes_in.text() == 'Refreshes in:':
        gui.refreshes_in.setText('Adding stop in:')
    else:
        gui.refreshes_in.setText('Adding stops in:')
    # Lock the queue so the tracker and update don't fight
    if rides.full():
        rides.get()
    rides.put(MBTAStop(
            gui.route_box.currentText(),
            gui.stop_box.currentText(),
            gui.direction_box.currentText(),
            gui.method_box.currentText(),
    ))
    # Update the boxes that will load new stations
    for label in ride_boxes:
        if label.title() != 'Loading...':
            label.setTitle('Loading...')
            break
        else:
            continue


def populate_stops() -> None:
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
    

def save_current_ride() -> None:
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


def load_saved_rides() -> None:
    """Loads rides from a text file and parses
    """
    ride_boxes = [
            gui.ride_1,
            gui.ride_2,
            gui.ride_3
    ]
    gui.refreshes_in.setText('Loading saved rides...')
    for _ in range(rides.qsize()):
        rides.get()
    try:
        with open('favorites.asc', 'r') as file_to_read:
            favorites = file_to_read.readlines()
        for label in range(len(favorites) - 1):
            ride_boxes[label].setTitle('Loading...')
        for idx, line in enumerate(favorites):
            if idx == 0:
                conversion_dict.update(ast.literal_eval(line))
            else:
                line = ast.literal_eval(line)
                line[2] = direction_dict[line[2]]
                rides.put(MBTAStop(
                        line[0],
                        line[1],
                        line[2],
                        line[3]
                ))
    # Stops users from breaking my program with invalid requests
    except FileNotFoundError:
        return


if __name__ == '__main__':
    app = QApplication([])
    window = QMainWindow()
    gui = Ui_mbta_tracker_window()
    gui.setupUi(window)
    app.setWindowIcon(QIcon('icon.ico'))
    window.setWindowIcon(QIcon('icon.ico'))
    
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
    
    # Starts the logical thread
    gui.thread = QThread()
    gui.worker = RideTracker()
    gui.worker.moveToThread(gui.thread)
    gui.thread.started.connect(gui.worker.run)
    gui.thread.start()
    
   # Launches the window
    window.show()
    app.exec()
