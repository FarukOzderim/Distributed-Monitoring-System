from threading import Thread
import matplotlib.pyplot as plt
import math
import requests
import psutil
import subprocess
import sys
import os
import time

INPUT_PATH = None

class InputReader:
    """
    An input reader, that reads the input and extracts hostnames and ports

    Args:
        input_path: path of the input

    Returns:
        InputReader instance
    """

    def __init__(self, input_path):
        self._input_path = input_path
        self.number_of_workers = None
        self.worker_host_names = None
        self.worker_ports = None

        self.read_input()

    def read_input(self):
        file_open = open(self._input_path, 'r')
        lines_list = file_open.readlines()
        self.number_of_workers = len(lines_list)
        self.worker_host_names = [None] * self.number_of_workers
        self.worker_ports = [None] * self.number_of_workers

        for i in range(self.number_of_workers):
            line = lines_list[i]

            index_of_new_line = line.find("\n")
            if not index_of_new_line == -1:
                line = line[:line.find("\n")]  # Remove new line from end
            # Check input entry
            if not line.count(":") == 1:
                print(f"Incorrect input, there is more than 1 ':' in one entry, ({line}), "
                      f"\nExiting Now")
                sys.exit(-1)
            self.worker_host_names[i] = line[:line.find(":")]
            try:
                self.worker_ports[i] = int(line[line.find(":") + 1:])
            except ValueError:
                print(f"Incorrect input port entry({line}), "
                      f"\nExiting Now")
                sys.exit(-1)


class WorkerInstance:
    """
    A Worker Instance, that runs the worker_SNAPSHOT with the given PORT.

    Args:
        port: Port of the Worker

    Returns:
        Worker instance
    """

    def __init__(self, port):
        self.port = port
        # Run silently
        self._process = subprocess.Popen(['java', '-jar', 'worker-1.0-SNAPSHOT.jar', str(port)],
                                         stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))

    def _kill(self, pid):
        process = psutil.Process(pid)
        for proc in process.children(recursive=True):
            proc.kill()
        process.kill()

    def shutdown(self):
        """
        Shutdowns the worker

        Returns:
            None
        """
        try:
            self._process.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            self._kill(self._process.pid)


class Monitor:
    """
    A Monitor instance that monitors all given workers

    Args:
        input_reader : an input_reader instance
        second_refresh_rate : refresh_rate option, unit: second, we update the data at this rate
        milisecond_sensitivity : sensitivity option, unit: milisecond, 1 is highest sensitivity,
         example: 10 means we save data at multiples of 10 milisecond
    Returns:
        Monitor instance
    """

    def __init__(self, input_path, second_refresh_rate, milisecond_sensitivity):
        input_reader = InputReader(input_path)
        self.number_of_workers = input_reader.number_of_workers
        self.worker_host_names = input_reader.worker_host_names
        self.worker_ports = input_reader.worker_ports
        self._second_refresh_rate = second_refresh_rate
        self._milisecond_sensitivity = milisecond_sensitivity

        self.list_of_time_series_lists = []
        self._list_of_last_entry_timestamp = [-1] * self.number_of_workers
        for _ in range(self.number_of_workers):
            self.list_of_time_series_lists.append([])

        self.start_time = time.time()
        self._thread = Thread(target=self._run_in_background)
        self._running = True

    def shutdown(self):
        self._running = False

    def run(self):
        self._thread.start()

    def _run_in_background(self):
        # Runs update in refresh rate intervals
        while self._running:
            time.sleep(self._second_refresh_rate)
            self.update()

    def update(self):
        for i in range(self.number_of_workers):
            r = requests.get(f"http://{self.worker_host_names[i]}:{self.worker_ports[i]}", timeout=0.1)
            self.process_request(i, r.text)

    def process_request(self, worker_no, text):
        # Process the request and add the data points to the list
        text = text[:-1]  # Remove last new line
        splited_text = text.split("\n")
        for i in splited_text:
            timestamp = int(i[:i.find(" ")])

            value = int(i[i.find(" ") + 1:])

            # Initial data point in the graph
            if self._list_of_last_entry_timestamp[worker_no] == -1:
                self._list_of_last_entry_timestamp[worker_no] = timestamp
                self.list_of_time_series_lists[worker_no].append(value)

            number_of_data_points_to_be_added = timestamp / self._milisecond_sensitivity - \
                                                self._list_of_last_entry_timestamp[
                                                    worker_no] / self._milisecond_sensitivity

            self._list_of_last_entry_timestamp[worker_no] = timestamp

            # Assign missing data points with the new entry, sensitivity decides number of points to be added
            for _ in range(math.floor(number_of_data_points_to_be_added)):
                self.list_of_time_series_lists[worker_no].append(value)

    def get_data(self):
        """
            Returns data points for all workers
        """
        return self.number_of_workers, self._milisecond_sensitivity, self.list_of_time_series_lists


class Plotter:
    """
        A Plotter instance that plots the data taken from the monitor all given workers

        Args:
            monitor : an monitor instance
        Returns:
            Plotter instance
        """

    def __init__(self, monitor):
        self._monitor = monitor

    def plot_individual_usage(self):
        number_of_workers, milisecond_sensitivity, list_of_time_series_lists = self._monitor.get_data()

        for i in range(number_of_workers):
            plt.plot(list_of_time_series_lists[i])
            plt.title(f"{self._monitor.worker_host_names[i]}:{self._monitor.worker_ports[i]} memory usage")
            plt.xlabel(f"time(milisecond*{milisecond_sensitivity})")
            plt.ylabel('Memory usage')
            plt.show()

    def plot_total_memory(self):
        number_of_workers, milisecond_sensitivity, list_of_time_series_lists = self._monitor.get_data()
        min_length = 2**31
        for my_list in list_of_time_series_lists:
            my_length = len(my_list)
            if min_length > my_length:
                min_length = my_length

        length = min_length
        total_memory_usage = [0] * length
        for i in range(number_of_workers):
            current_list = list_of_time_series_lists[i]
            for j in range(length):
                try:
                    total_memory_usage[j] += current_list[j]
                except:
                    print(f"total memo len:{len(total_memory_usage)} current:len:{len(current_list)}")
        plt.plot(total_memory_usage)
        plt.title(f"Total memory usage")
        plt.xlabel(f"time(milisecond*{milisecond_sensitivity})")
        plt.ylabel('Memory usage')
        plt.show()


### Run ##
def main():
    # Input checks
    if not len(sys.argv) == 2:
        print("You need to give one input, "
              "\nExample:'python main.py [input.txt]'"
              "\nExiting now")
        sys.exit(-1)

    INPUT_PATH = sys.argv[1]
    if not os.path.exists(INPUT_PATH):
        print(f"The input file({INPUT_PATH}) does not exist, incorrect path, exiting now")
        sys.exit(-1)

    my_worker_instance_1 = WorkerInstance(1234)
    my_worker_instance_2 = WorkerInstance(1235)

    my_monitor_instance = Monitor(INPUT_PATH, 1, 1)
    my_monitor_instance.run()

    time.sleep(5)

    my_monitor_instance.shutdown()
    my_worker_instance_1.shutdown()
    my_worker_instance_2.shutdown()

    my_plotter_instance = Plotter(my_monitor_instance)
    my_plotter_instance.plot_individual_usage()
    my_plotter_instance.plot_total_memory()

if __name__ == '__main__':
    main()