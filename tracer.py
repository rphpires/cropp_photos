import os
import glob
import traceback
import threading

from datetime import datetime


htmlPageHeader = """<!DOCTYPE html>
<meta content="text/html;charset=utf-8" http-equiv="Content-Type">
<script>
var original_html = null;
var filter = '';
function filter_log()
{
    document.body.style.cursor = 'wait';
    if (original_html == null) {
        original_html = document.body.innerHTML;
    }
    if (filter == '') {
        document.body.innerHTML = original_html;
    } else {
        l = original_html.split("<br>");
        var pattern = new RegExp(".*" + filter.replace('"', '\\"') + ".*", "i");
        final_html = '';
        for(var i=0; i<l.length; i++){
            if (pattern.test(l[i]))
                final_html += l[i] + '<br>';
        }
        document.body.innerHTML = final_html;
    }
    document.body.style.cursor = 'default';
}

document.onkeydown = function(event) {
    if (event.keyCode == 76) {
        var ret = prompt("Enter the filter regular expression. Examples:\\n\\n\\
CheckFirmwareUpdate'\\n\\n'ID=1 |ID=2 \\n\\nID=2 .*Got message\\n\\n2012-08-31 16:.*(ID=1 |ID=2 )\\n\\n", filter);
        if (ret != null) {
            filter = ret;
            filter_log();
        }
        return false;
    }
}
</script>
<STYLE TYPE="text/css">
<!--
BODY
{
  color:white;
  background-color:black;
  font-family:monospace, sans-serif;
}
-->
</STYLE>
<body bgcolor="black" text="white">
<font color="white">"""


LOG_MAX_SIZE = 5_000_000  # 5MB
MAX_FILES = 15


class LogFile:
    def __init__(self, filename, max_size=LOG_MAX_SIZE):
        self.filename = filename
        self.max_size = max_size
        self.current_size = os.path.getsize(filename) if os.path.exists(filename) else 0
        self.file = None

    def _open_file(self):
        self.file = open(self.filename, 'a', encoding="utf-8")

    def _close_file(self):
        if self.file:
            self.file.close()
            self.file = None

    def _rotate_file(self):
        self._close_file()
        current_date = datetime.now().strftime('%Y-%m-%d_%H_%M_%S')
        new_filename = f'{current_date}_{self.filename}'
        os.rename(self.filename, new_filename)
        self._open_file()

    def write(self, data):
        if not self.file:
            self._open_file()

        if self.current_size + len(data) > self.max_size:
            self._rotate_file()
            self.current_size = 0

        self.file.write(data)
        self.current_size += len(data)

    def close(self):
        self._close_file()
        self.current_size = 0


def create_html_log_file(log_filename):
    with open(log_filename, "w", encoding="utf-8") as log_file:
        log_file.write(htmlPageHeader)


def get_log_files(folder_name):
    files = glob.glob(os.path.join(folder_name, '*.html'))
    files.sort(key=os.path.getctime)
    return files


def remove_oldest_log_file(folder_name):
    log_files = get_log_files(folder_name)
    if len(log_files) >= MAX_FILES:
        oldest_file = log_files[0]
        os.remove(oldest_file)


def trace(Message, userID='', color='white'):
    print(f"{userID} - {Message}")
    executableName = 'Integra'
    folderName = 'Trace ' + executableName

    enabled_trace = os.path.isfile('TraceEnable.txt')
    enabled_trace_1 = os.path.isfile('TraceIntegraEnable.txt')
    enabled_trace_2 = os.path.isfile('Trace.txt')

    if not any((enabled_trace, enabled_trace_1, enabled_trace_2)):
        return

    os.makedirs(folderName, exist_ok=True)
    log_filename = os.path.join(folderName, 'trace.html')

    if not os.path.exists(log_filename):
        create_html_log_file(log_filename)

    remove_oldest_log_file(folderName)

    log_file = LogFile(log_filename, max_size=LOG_MAX_SIZE)

    log_entry = f'\n<br></font><font color="{color}">{datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]} - {userID} - {Message}'
    try:
        log_file.write(log_entry)
    except IOError:
        log_file.close()
        Current_Date = datetime.now().strftime('%Y-%m-%d_%H_%M_%S')
        new_filename = os.path.join(folderName, f'{Current_Date} - trace.html')
        os.rename(log_filename, new_filename)
        create_html_log_file(log_filename)
        log_file = LogFile(log_filename, max_size=LOG_MAX_SIZE)
        log_file.write(log_entry)


def report_exception(e):
    try:
        t = "{}".format(type(threading.currentThread())).split("'")[1].split('.')[1]
    except IndexError:
        t = 'UNKNOWN'

    trace("", f"Bypassing exception at {t} ({e})", color="red")
    trace("", f"**** Exception: <code>{traceback.format_exc()}</code>", color="red")


def error(msg):
    trace(f'** {msg}', color='red')


def trace_session_error(msg):
    trace(f'** {msg}', color='LightSalmon')
