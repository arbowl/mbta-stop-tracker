import json
import os
from configparser import ConfigParser
from datetime import datetime, timedelta, timezone
from math import ceil
from queue import Queue
from time import sleep
from typing import Union
from urllib import request
from urllib.error import URLError

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMainWindow

from mbta_tracker_gui import Ui_mbta_tracker_window


class MBTAStop:
    """An object which contains the information needed to find the T arrival time for a stop
    """
    def __init__(self, route: str, stop: str, direction: str, method: str):
        self.route = route
        self.name = stop
        self.stop = conversion_dict[stop]
        self.direction = direction_dict[direction]
        self.method = method.lower()
        self.sort = 'arrival_time' if self.method == 'predictions' else 'departure_time'

    @property
    def generate_url(self) -> str:
        """Creates and returns a URL based on the object's properties

        Returns:
            str: base url + parameters of the trip + api key
        """
        return ''.join([
                f'https://api-v3.mbta.com/{self.method}',
                f'?filter[stop]={self.stop}',
                f'&route={self.route}',
                f'&direction_id={self.direction}',
                f'&sort={self.sort}',
                f'&api_key={API_KEY}',
        ])


class RideTracker(QObject):
    """The worker thread that pulls data from the MBTA and sends signals to the GUI containing the
    data to update it with
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
        self.ride_labels = [
                self.ride_1_label, 
                self.ride_2_label,
                self.ride_3_label
        ]
        self.ride_boxes = [
                self.ride_1_sig_1,
                self.ride_1_sig_2,
                self.ride_2_sig_1,
                self.ride_2_sig_2,
                self.ride_3_sig_1,
                self.ride_3_sig_2
        ]
    
    @pyqtSlot()
    def run(self) -> None:
        """Manages the queue, MBTA stop objects, and signals to the GUI. Refresh rate is based on the
        presence of the API key.
        """
        while True:
            self.updating_sig.emit('Refreshes in:')
            for stop in range(rides.qsize()):
                mbta_stop: MBTAStop = rides.queue[rides.qsize() - stop - 1]
                self.ride_labels[stop].emit(mbta_stop.name)
                try:
                    api_url = mbta_stop.generate_url
                except URLError:
                    sleep(1)
                    continue
                api_list_of_rides = json.load(request.urlopen(api_url))['data']
                current_api_list_index = 0
                for row_of_gui in range(2):
                    time_until_arrival, current_api_list_index = calculate_stop_times(
                            row_of_gui,
                            api_list_of_rides,
                            mbta_stop,
                            current_api_list_index
                    )
                    self.ride_boxes[stop * 2 + row_of_gui].emit(time_until_arrival)
            lcd_value = 3 if API_KEY else 15
            for decrement in range(lcd_value + 1):
                self.timer_update.emit(lcd_value - decrement)
                sleep(1)


def calculate_stop_times(gui_row: int, list_of_rides: dict, stop_info: MBTAStop, prev_index: int) -> Union[str, int]:
    """Handles everything related to finding the next availale ride info based on whether it's the first
    or second ride available, whether it's stopped or skipped, arriving, or already passed.
    """
    current_index = 0
    total_number_of_rides = len(list_of_rides)
    if total_number_of_rides == 0:
        return 'No stops', current_index
    if 0 < total_number_of_rides < gui_row + prev_index + 1:
        return '', current_index
    for current_index in range(prev_index, total_number_of_rides):
        alert = list_of_rides[gui_row + current_index]['attributes']
        if 'status' in alert and alert['status']:
            return ' '.join(alert['status'].split(' ')[1:])
        if 'schedule_relationship' in alert and alert['schedule_relationship'] == 'SKIPPED':
            continue
        target_time = alert[stop_info.sort]
        if not target_time:
            break
        display_time_in_seconds = format_time(target_time)
        if display_time_in_seconds < 0:
            continue
        if display_time_in_seconds > 30:
            display_time_in_minutes = ceil(display_time_in_seconds / 60)
            plural = '' if display_time_in_minutes == 1 else 's'
            return str(display_time_in_minutes) + f' minute{plural}', current_index
        return 'Arriving', current_index


def format_time(terminal_time: str) -> float:
    """Converts the arrival/departure time from a timestamp to seconds from arrival
    """
    if not terminal_time:
        return 0
    time_offset = int(terminal_time[-4])
    formatted_time = datetime.fromisoformat(terminal_time.replace('T', ' ')[:-6] + '+00:00')
    formatted_time -= (datetime.now(timezone.utc) - timedelta(hours=time_offset, minutes=0))
    return formatted_time.total_seconds()


def generate_stop() -> None:
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
    if rides.full():
        rides.get()
    rides.put(MBTAStop(
            gui.route_box.currentText(),
            gui.stop_box.currentText(),
            gui.direction_box.currentText(),
            gui.method_box.currentText(),
    ))
    for label in ride_boxes:
        if label.title() != 'Loading...':
            label.setTitle('Loading...')
            break


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


def populate_methods() -> None:
    """A way to prevent users from selecting a "prediction" for a terminus--terminuses only launch
    rides on a schedule and thus don't have predictions.
    """
    gui.method_box.clear()
    stop = gui.stop_box.currentIndex()
    first_stop = 0
    final_stop = gui.stop_box.count() - 1
    if stop != first_stop and stop != final_stop:
        gui.method_box.addItem('Predictions')
    gui.method_box.addItem('Schedules')
    

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
    config['Reload'] = {'Conversions': str(conversion_dict)}
    config['Saved'] = {}
    for idx, item in enumerate(save_list):
        config['Saved'][f'Ride{idx + 1}'] = str(item)
    with open('favorites.ini', 'w') as new_config_settings:
        config.write(new_config_settings)


def load_saved_rides() -> None:
    """Loads rides from a text file and parses the existing dictionary
    """
    if not os.path.exists('favorites.ini'):
        return
    ride_boxes = [
            gui.ride_1,
            gui.ride_2,
            gui.ride_3
    ]
    gui.refreshes_in.setText('Loading saved rides...')
    for _ in range(rides.qsize()):
        rides.get()
    config.read('favorites.ini')
    for label in range(len(config['Saved'].keys())):
        ride_boxes[label].setTitle('Loading...')
    if 'Reload' in config:
        loaded_dict = {}
        reload_data = config['Reload']['conversions']
        stripped_line = reload_data.strip('[]\n')
        name_code_pairs = stripped_line.split(', ')
        for pair in name_code_pairs:
            raw_key = pair.split(': ')[0]
            stripped_key = raw_key[1:-1]
            raw_value = pair.split(': ')[1]
            stripped_value = raw_value[1:-1]
            loaded_dict[stripped_key] = stripped_value
        conversion_dict.update(loaded_dict)
    if not 'Saved' in config:
        return
    for ride in ['ride1', 'ride2', 'ride3']:
        if not ride in config['Saved']:
            continue
        stripped_line = config['Saved'][ride].strip('[]\n')
        mbta_stop_data = [data[1:-1] for data in stripped_line.split(', ')]
        mbta_stop_data[2] = direction_dict[mbta_stop_data[2]]
        idx = int(ride.replace('ride', ''))
        if mbta_stop_data[1] not in conversion_dict.keys():
            ride_boxes[idx - 1].setTitle(f'Ride {idx}')
            continue
        rides.put(MBTAStop(
                mbta_stop_data[0],
                mbta_stop_data[1],
                mbta_stop_data[2],
                mbta_stop_data[3]
        ))


def draw_gui_and_start_execution() -> None:
    """Handles the creation of the GUI and the test execution loop
    """
    app = QApplication([])
    window = QMainWindow()
    gui.setupUi(window)
    app.setWindowIcon(QIcon('icon.ico'))
    window.setWindowIcon(QIcon('icon.ico'))
    gui.route_box.addItems(total_routes)
    populate_stops()
    gui.route_box.currentTextChanged.connect(populate_stops)
    gui.direction_box.addItems(['Inbound', 'Outbound'])
    populate_methods()
    gui.stop_box.currentTextChanged.connect(populate_methods)
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


if __name__ == '__main__':
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
    API_KEY = ''
    if os.path.exists('api_key.env'):
        with open('api_key.env', 'r') as env_file:
            API_KEY = env_file.readlines()[0]
    rides = Queue(maxsize=3)
    conversion_dict = {}
    direction_dict = {
            '0' : 'Outbound',
            '1' : 'Inbound',
            'Outbound' : '0',
            'Inbound' : '1'
    }
    route_url = 'https://api-v3.mbta.com/routes'
    total_routes = []
    while True:
        try:
            with request.urlopen(route_url) as url:
                routes = json.load(url)
            break
        except:
            pass
    for route in range(len(routes['data'])):
        total_routes.append(routes['data'][route]['id'])
    config = ConfigParser()
    gui = Ui_mbta_tracker_window()
    draw_gui_and_start_execution()
