# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import _pickle as cPickle
import base64
import ctypes
import hashlib
import itertools
import operator
import os
import psutil
import re
import shelve
import socket
import stat
import struct
import subprocess
import sys
import threading
import time
import urllib
import win32file
import win32pipe
import zlib

from operator import itemgetter


def kill_existing_instances():
    pid = int(os.getpid())
    cwd = os.path.split(__file__)[0]
    for p in psutil.process_iter():
        try:
            p.cwd()
        except Exception:
            continue
        if p.pid != pid and p.cwd() == cwd and p.name().lower() in ('python.exe', 'pythonw.exe',):
            # only SIGTERM, CTRL_C_EVENT, CTRL_BREAK_EVENT signals on Windows Platform.
            # p.send_signal(signal.SIGTERM)
            p.terminate()


def get_hostname():
    return socket.gethostname()


def get_external_ip():
    site = urllib.urlopen('http://checkip.dyndns.org/').read()
    grab = re.findall(r'\d{2,3}.\d{2,3}.\d{2,3}.\d{2,3}', site)
    return grab[0]


def get_hddserial():
    import wmi
    c = wmi.WMI()
    hddserial = list()
    for pm in c.Win32_PhysicalMedia():
        hddserial.append(pm.SerialNumber.strip())
        # hddserial.append((pm.Tag.strip('.\\'), pm.SerialNumber.strip()))
    hddserial.sort(key=itemgetter(0))
    return hddserial


def get_macaddress(host='localhost'):
    # Returns the MAC address of a network host, requires >= WIN2K
    # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/347812
    # import ctypes, socket, struct
    # Check for api availability
    try:
        SendARP = ctypes.windll.Iphlpapi.SendARP
    except Exception:
        raise NotImplementedError('Usage only on Windows 2000 and above')
    # Doesn't work with loopbacks, but let's try and help.
    if host == '127.0.0.1' or host.lower() == 'localhost':
        host = socket.gethostname()
    # gethostbyname blocks, so use it wisely.
    try:
        inetaddr = ctypes.windll.wsock32.inet_addr(host)
        if inetaddr in (0, -1):
            raise Exception
    except Exception:
        hostip = socket.gethostbyname(host)
        inetaddr = ctypes.windll.wsock32.inet_addr(hostip)
    buffer = ctypes.c_buffer(6)
    addlen = ctypes.c_ulong(ctypes.sizeof(buffer))
    if SendARP(inetaddr, 0, ctypes.byref(buffer), ctypes.byref(addlen)) != 0:
        raise WindowsError('Retreival of mac address(%s) - failed' % host)
    # Convert binary data into a string.
    macaddr = ''
    for intval in struct.unpack('BBBBBB', buffer):
        if intval > 15:
            replacestr = '0x'
        else:
            replacestr = 'x'
        if macaddr != '':
            macaddr = ':'.join([macaddr, hex(intval).replace(replacestr, '')])
        else:
            macaddr = ''.join([macaddr, hex(intval).replace(replacestr, '')])
    return macaddr.upper()


class Struct():

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

    def items(self):
        return self.__dict__.items()

    def values(self):
        return self.__dict__.values()

    def keys(self):
        return self.__dict__.keys()


def dict_to_struct(data):
    result = Struct()
    for key in data.keys():
        exec('result.%s = data["%s"]' % (key, key))
    return result


def struct_to_dict(data):
    result = dict()
    for key in data.keys():
        exec('result["%s"] = data.%s' % (key, key))
    return result


def rgb2clr(rgba):
    try:
        r, g, b, alpha = rgba
        return [c / 255.0 for c in tuple((r, g, b, alpha))]
    except Exception:
        pass
    r, g, b = rgba
    return [c / 255.0 for c in tuple((r, g, b))]


def clr2rgb(clra):
    try:
        c, l, r, alpha = clra
        return [f * 255.0 for f in tuple((c, l, r, alpha))]
    except Exception:
        pass
    c, l, r = clra
    return [f * 255.0 for f in tuple((c, l, r))]


def rgb_hex2dec(rgb):
    if rgb.startswith('#'):
        rgb = rgb[1:]
    return tuple([int(rgb[i:i + 2], 16) for i in range(0, 6, 2)])


def rgb_dec2hex(rgb):
    v = 0
    rgb = [hex(v)[2:] for v in rgb]
    for i in range(len(rgb)):
        if len(rgb[i]) == 1:
            rgb[i] = '0' + str(v)
    return ''.join(rgb)


def win32_unicode_argv():
    """
    Uses shell32.GetCommandLineArgvW to get sys.argv as a list of Unicode strings.
    Example usage:
    >>> def main(argv=None):
    ...    if argv is None:
    ...        argv = win32_unicode_argv() or sys.argv
    ...
    """
    try:
        from ctypes import POINTER, byref, cdll, c_int, windll
        from ctypes.wintypes import LPCWSTR, LPWSTR

        GetCommandLineW = cdll.kernel32.GetCommandLineW
        GetCommandLineW.argtypes = []
        GetCommandLineW.restype = LPCWSTR

        CommandLineToArgvW = windll.shell32.CommandLineToArgvW
        CommandLineToArgvW.argtypes = [LPCWSTR, POINTER(c_int)]
        CommandLineToArgvW.restype = POINTER(LPWSTR)

        cmd = GetCommandLineW()
        argc = c_int(0)
        argv = CommandLineToArgvW(cmd, byref(argc))
        if argc.value > 0:
            # Remove Python executable if present
            if argc.value - len(sys.argv) == 1:
                start = 1
            else:
                start = 0
            return [unicode(argv[i]) for i in
                    xrange(start, argc.value)]
    except Exception:
        pass


def get_most_common_element(values):
    sorted_list = sorted((x, i) for i, x in enumerate(values))
    groups = itertools.groupby(sorted_list, key=operator.itemgetter(0))

    def auxfun(g):
        item, iterable = g
        count = 0
        min_index = len(values)
        for _, where in iterable:
            count += 1
            min_index = min(min_index, where)
        return count, -min_index
    return max(groups, key=auxfun)[0]


def makemdx(path, created_time=None):
    if created_time is None:
        try:
            stats = os.stat(path)
        except Exception:
            return None
        created_time = stats[stat.ST_CTIME]
    # path = os.path.abspath(path).encode(sys.getfilesystemencoding())
    path = os.path.abspath(path)
    value = ''.join([path, str(created_time)])
    value = value.encode(sys.getfilesystemencoding())
    # mdx = string2md5(value)
    # return mdx.encode('utf-8')
    return string2md5(value)


def file2md5(filename):
    md5 = hashlib.md5()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), ''):
            md5.update(chunk)
    return md5.hexdigest()


def string2md5(content):
    md5 = hashlib.md5()
    md5.update(content)
    return md5.hexdigest()


def compress_object(data, level=9):
    if data is None:
        return 'null'
    return base64.b64encode(zlib.compress(cPickle.dumps(data), level)).decode('utf-8')


def decompress_object(data):
    if data == 'null':
        return None
    return cPickle.loads(zlib.decompress(base64.b64decode(data.encode('utf-8'))))


def save_shelve(key, value, shelve_path):
    db = shelve.open(shelve_path)
    db[key] = compress_object(value)
    db.close()


def save_shelves(keyvalues, shelve_path):
    db = shelve.open(shelve_path)
    for keyvalue in keyvalues:
        key, value = keyvalue
        db[key] = compress_object(value)
    db.close()


def open_shelve(key, shelve_path):
    db = shelve.open(shelve_path)
    flag = key in db
    if flag is False:
        data = None
    else:
        data = decompress_object(db[key])
    db.close()
    return data


def open_shelves(keys, shelve_path):
    db = shelve.open(shelve_path)
    data = []
    for key in keys:
        flag = key in db
        if flag is False:
            data += [None]
        else:
            data += [decompress_object(db[key])]
    db.close()
    return data


# set_master_path() to main entry and get_master_path() from anywhere


def set_master_path():
    filename = 'macroboxplayer'
    # filename = 'macroboxplayer.db'
    shelve_path = os.path.join(get_user_docapp_path(), filename)
    save_shelve('master_path', os.getcwd(), shelve_path)


def get_master_path():
    filename = 'macroboxplayer'
    # filename = 'macroboxplayer.db'
    shelve_path = os.path.join(get_user_docapp_path(), filename)
    return open_shelve('master_path', shelve_path)


def get_user_docapp_path():
    path = os.path.join(get_user_document_path(), 'muteklab')
    if os.path.isdir(path) is False:
        os.mkdir(path)
    return path


def get_user_document_path():
    if sys.platform.startswith('win'):
        path = os.path.abspath(os.path.join(
            os.path.expanduser(r'~'), r'Documents'))
        if os.path.isdir(path):
            return path
        path = os.path.abspath(os.path.join(
            os.path.expanduser(r'~'), r'My Documents'))
        if os.path.isdir(path):
            return path
        return None
    elif sys.platform.startswith('darwin'):
        path = os.path.abspath(os.path.join(
            os.path.expanduser(r'~'), r'Documents'))
        if os.path.isdir(path):
            return path
        return None


def get_path_where_iamin():
    return os.path.dirname(os.path.abspath(__name__))


def kill_self_process():
    kill_process_by_pid(os.getpid())


def kill_process_by_pid(pid):
    if sys.platform.startswith('win'):
        PROCESS_TERMINATE = 1
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_TERMINATE, False, pid)
        ctypes.windll.kernel32.TerminateProcess(handle, -1)
        ctypes.windll.kernel32.CloseHandle(handle)
    elif sys.platform.startswith('darwin'):
        cmd = ['kill', '-9', '%s' % (pid)]
        try:
            run_hidden_subprocess(cmd)
        except Exception:
            pass


def kill_ghost_process(ghost_name):
    current_pid = os.getpid()
    procs = psutil.get_process_list()
    tasklist = [(proc.name, int(proc.pid),) for proc in procs]
    pids = [pid for image_name, pid in tasklist
            if image_name == ghost_name and pid != current_pid]
    if pids == []:
        return
    for pid in pids:
        kill_process_by_pid(pid)


def is_ghost_runnung(ghost_name):
    selfpid = os.getpid()
    ps = [pid for pid, name in get_active_processes()
          if pid != selfpid and name == ghost_name]
    if ps == []:
        return False
    return True

# def is_ghost_runnung(ghost_name):
#   selfpid = os.getpid()
#   ghost_name = """%s""" % (ghost_name)
#   ps = filter(lambda p: ghost_name in str(p.name), psutil.process_iter())
#   if ps == 1: return False
#   return True


def get_active_processes():
    # http://code.activestate.com/recipes/305279/
    psapi = ctypes.windll.psapi  # PSAPI.DLL
    kernel = ctypes.windll.kernel32  # Kernel32.DLL
    arr = ctypes.c_ulong * 256
    lpidProcess = arr()
    cb = ctypes.sizeof(lpidProcess)
    cbNeeded = ctypes.c_ulong()
    hModule = ctypes.c_ulong()
    count = ctypes.c_ulong()
    modname = ctypes.c_buffer(260)
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    # Call Enumprocesses to get hold of process id's
    psapi.EnumProcesses(ctypes.byref(lpidProcess), cb, ctypes.byref(cbNeeded))
    # Number of processes returned
    nReturned = cbNeeded.value / ctypes.sizeof(ctypes.c_ulong())
    pidProcess = [i for i in lpidProcess][:nReturned]
    running_process = list()
    for pid in pidProcess:
        # Get handle to the process based on PID
        hProcess = kernel.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if hProcess:
            psapi.EnumProcessModules(hProcess, ctypes.byref(hModule), ctypes.sizeof(hModule), ctypes.byref(count))
            psapi.GetModuleBaseNameA(hProcess, hModule.value, modname, ctypes.sizeof(modname))
            running_process += [(pid, ''.join(
                [i for i in modname if i != '\x00']))]
            # Clean up
            for i in range(modname._length_):
                modname[i] = '\x00'
            kernel.CloseHandle(hProcess)
    return running_process


def run_hidden_subprocess(command, resp=False):
    # http://stackoverflow.com/questions/12790328/
    # how-to-silence-sys-excepthook-is-missing-error
    if sys.platform.startswith('win'):
        sys.getwindowsversion()
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    else:
        startupinfo = None
    if resp is False:
        proc = subprocess.Popen(command, shell=False, bufsize=-1, startupinfo=startupinfo)
        return
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=False, bufsize=-1, startupinfo=startupinfo)
    resp = proc.communicate()[0]
    proc.terminate()
    return resp


def get_memory_by_pid(pid):
    p = psutil.Process(pid)
    memory = p.get_memory_info().vms  # rss
    return memory


def is_process_running_by_pid(pid):
    procs = psutil.get_pid_list()
    return pid in procs


def is_process_running_by_name(name):
    selfpid = os.getpid()
    name = """name=u'%s'""" % (name)
    ps = filter(lambda p: name in str(p.name) and p.pid != selfpid, psutil.process_iter())
    if ps == []:
        return False
    return True


def get_tasklist():
    resps = run_hidden_subprocess('tasklist', resp=True)
    regexp = [r'^([\w|\s|\.]{1,}[\w|\.]{1})[\s]{1,}([\d]+)[\s]{1,}']
    regexp += [r'([\w]{1,})[\s]{1,}([\d|\,]{1,})[\s]{1,}([\d|\,]{1,})\sK$']
    regexp = r''.join(regexp)
    tasklist = []
    if resps is None:
        return []
    for task in resps.split(os.linesep):
        task = re.findall(regexp, task)
        if task == []:
            continue
        image_name, pid, session_name, session, memory = task[0]
        memory = memory.replace(',', '')
        tasklist += [(image_name, int(pid),
                      session_name, int(session), int(memory),)]
    return tasklist

    procs = psutil.get_process_list()
    # print time.time()-tic
    procs = sorted(procs, key=lambda proc: proc.name)
    tasklist = []
    for proc in procs:
        # image_name, pid, session_name, session, memory
        name = proc.name
        # cpu_percent = proc.get_cpu_percent()
        mem_percent = proc.get_memory_percent()
        # rss, vms = proc.get_memory_info()
        pid = proc.pid
        session_name = ''
        session = 0
        tasklist += [(name, int(pid), session_name, int(session), mem_percent,)]
    return tasklist


def set_process_priority(priority):
    # http://code.activestate.com/recipes/496767/
    if sys.platform.startswith('win'):
        import win32api
        import win32process
        import win32con
        pid = win32api.GetCurrentProcessId()
        handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
        if priority == 1:
            pv = win32process.REALTIME_PRIORITY_CLASS
        if priority == 2:
            pv = win32process.HIGH_PRIORITY_CLASS
        if priority == 3:
            pv = win32process.ABOVE_NORMAL_PRIORITY_CLASS
        if priority == 4:
            pv = win32process.NORMAL_PRIORITY_CLASS
        if priority == 5:
            pv = win32process.BELOW_NORMAL_PRIORITY_CLASS
        if priority == 6:
            pv = win32process.IDLE_PRIORITY_CLASS
        win32process.SetPriorityClass(handle, pv)
    else:
        os.nice(priority)  # priority is 1~10


def is_packaged():
    if os.path.isfile('python27.dll'):
        return True
    return False


SOCKET_ERROR_CODE = (0,)  # 10


def send_socket_message(message, address):
    sender = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sender.connect(address)
        resp = sender.send(compress_object(message))
    except Exception:
        resp = 0
    sender.close()
    return resp


class SocketReceiver(threading.Thread):

    def __init__(self, address):
        threading.Thread.__init__(self)
        self.loop = True
        self.received = []
        self.receiver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.receiver.bind(address)
        self.receiver.listen(1)

    def run(self):
        while self.loop:
            connection, address = self.receiver.accept()
            try:
                data = connection.recv(8192)
                received = decompress_object(data)
                self.received += [(received, address)]
            except Exception:
                pass
            connection.close()

    def pop_message(self, idx=0):
        return self.received.pop(idx)

    def get_message(self):
        return self.received

    def has_message(self):
        return self.received != []

    def del_message(self):
        self.received = []

    def terminate(self):
        self.loop = False
        self.receiver.close()

    def __del__(self):
        self.terminate()


class SocketMessenger(threading.Thread):

    def __init__(self, address):
        threading.Thread.__init__(self)
        self.loop = True
        self.lock = False
        self.sendbox = []
        self.failed = []
        self.interval = 0.01
        self.Receiver = SocketReceiver(address)
        self.Receiver.start()

    def run(self):
        while self.loop:
            time.sleep(self.interval)
            if self.lock:
                continue
            if self.sendbox == []:
                continue
            message, address = self.sendbox.pop(0)
            resp = send_socket_message(message, address)
            if resp in SOCKET_ERROR_CODE:
                self.failed += [(message, address)]

    def resend_failed(self):
        self.freeze()
        self.sendbox = self.sendbox + self.failed
        self.failed = []
        self.thaw()

    def freeze(self):
        self.lock = True

    def thaw(self):
        self.lock = False

    def set_interval(self, value):
        self.interval = value

    def get_failed(self):
        return self.failed

    def del_failed(self):
        self.failed = []

    def has_failed(self):
        return self.failed != []

    def has_message(self):
        return self.Receiver.has_message()

    def pop_message(self, idx=0):
        return self.Receiver.pop_message(idx)

    def get_message(self):
        return self.Receiver.get_message()

    def send_message(self, message, delivering_address, urgent=False):
        if urgent:
            self.sendbox.insert(0, (message, delivering_address))
        else:
            self.sendbox.append((message, delivering_address))

    def terminate(self):
        self.loop = False
        self.Receiver.terminate()
        self.Receiver._Thread__stop()

    # def __del__(self):
    #   self.terminate()

    def __exit__(self, type, value, traceback):
        self.terminate()


def send_pipe_message(message, address):
    pipe = '\\\\.\\pipe\\%s' % (address)
    p = win32pipe.CreateNamedPipe(pipe,
                                  win32pipe.PIPE_ACCESS_DUPLEX,
                                  win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
                                  1, 65536, 65536, 300, None)
    win32pipe.ConnectNamedPipe(p, None)
    data = compress_object(message)
    win32file.WriteFile(p, data)
    win32file.CloseHandle(p)


class PipeReceiver(SocketReceiver):

    def __init__(self, address):
        threading.Thread.__init__(self)
        # SocketReceiver.__init__(self)
        self.loop = True
        self.received = []
        self.interval = 0.02
        self.address = address

    def run(self):
        while self.loop:
            time.sleep(self.interval)
            received = None
            try:
                pipe = '\\\\.\\pipe\\%s' % (self.address)
                fileHandle = win32file.CreateFile(pipe,
                                                  win32file.GENERIC_READ,
                                                  0, None, win32file.OPEN_EXISTING,
                                                  win32file.FILE_ATTRIBUTE_NORMAL, None)
                data = win32file.ReadFile(fileHandle, 1024, None)
                if data[0] == 0:
                    # path = decompress_object(data[1])
                    # print path
                    self.received += [(received, self.address)]
                win32file.CloseHandle(fileHandle)
            except Exception:
                pass
        win32file.CloseHandle(fileHandle)

    def terminate(self):
        self.loop = False


class PipeMessenger(SocketMessenger):

    def __init__(self, address):
        threading.Thread.__init__(self)
        # SocketMessenger.__init__(self)
        self.loop = True
        self.lock = False
        self.sendbox = []
        self.failed = []
        self.interval = 0.02
        self.Receiver = PipeReceiver(address)
        self.Receiver.start()

    def run(self):
        while self.loop:
            time.sleep(self.interval)
            if self.lock:
                continue
            if self.sendbox == []:
                continue
            message, address = self.sendbox.pop(0)
            resp = send_pipe_message(message, address)
            if resp in SOCKET_ERROR_CODE:
                self.failed += [(message, address)]
