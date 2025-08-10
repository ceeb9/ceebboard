from enum import Enum
import datetime

class LogMessageLevel(Enum):
    INFO = 0,
    WARNING = 1,
    ERROR = 2
    
def write_log_message(message: str, level: LogMessageLevel):
    cur_time = datetime.datetime.now()
    cur_time_str = cur_time.strftime("%m-%d|%H:%M:%S")
    log_message = f"[{cur_time_str}][{level.name}] {message}"
    print(log_message)
    