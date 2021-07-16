# Distributed Monitoring System

_By FarukOzderim_

The monitoring application takes a file containing the list of the workers as input
and connects to all the workers in the given file. 
Then collects memory usage logs in a async way.
The input file has the following format:
The output is plotted graphs.

```
host_ip1:host_port1
host_ip2:host_port2
...
```


# Dependiencies
- psutil


# Example Run
```
python main.py example_input.txt
```


# Usage
```
import InputReader, Monitor from main

my_monitor = Monitor(input_path, second_refresh_rate, sensitivity)
```

