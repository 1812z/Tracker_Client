import requests
import time
from threading import Thread
import win32gui
import win32process
import win32api
import win32con
import json
import ctypes
import uuid
from ctypes import wintypes

# Define GUID structure for power notifications
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8)
    ]
    def __eq__(self, other):
        return (self.Data1 == other.Data1 and
                self.Data2 == other.Data2 and
                self.Data3 == other.Data3 and
                bytes(self.Data4) == bytes(other.Data4))

GUID_MONITOR_POWER_ON = GUID()
u = uuid.UUID("{02731015-4510-4526-99e6-e5a17ebd1aea}")
GUID_MONITOR_POWER_ON.Data1 = u.time_low
GUID_MONITOR_POWER_ON.Data2 = u.time_mid
GUID_MONITOR_POWER_ON.Data3 = u.time_hi_version
GUID_MONITOR_POWER_ON.Data4[:] = u.bytes[8:]

class POWERBROADCAST_SETTING(ctypes.Structure):
    _fields_ = [
        ("PowerSetting", GUID),
        ("DataLength", wintypes.DWORD),
        ("Data", ctypes.c_byte * 1)
    ]

# Define RegisterPowerSettingNotification function prototype from user32.dll
user32 = ctypes.windll.user32
user32.RegisterPowerSettingNotification.argtypes = [wintypes.HANDLE, ctypes.POINTER(GUID), wintypes.DWORD]
user32.RegisterPowerSettingNotification.restype = wintypes.HANDLE

# Define UnregisterPowerSettingNotification function prototype
user32.UnregisterPowerSettingNotification.argtypes = [wintypes.HANDLE]
user32.UnregisterPowerSettingNotification.restype = wintypes.BOOL

# 配置参数
API_URL = "https://api-usage.1812z.top/api"  # 替换为实际的API地址
SECRET_KEY = "3"  # 替换为实际的密钥
DEVICE_ID = "电脑"  # 替换为实际的设备ID

# 上一次记录的应用程序名称
last_app = None
# 记录系统是否处于休眠状态
system_suspended = False
# 记录屏幕是否关闭的状态
screen_off = False

class WindowHook:
    def __init__(self):
        self.message_map = {
            win32con.WM_QUERYENDSESSION: self.on_shutdown,
            win32con.WM_POWERBROADCAST: self.on_power_event
        }
        self.hwnd = win32gui.CreateWindowEx(
            0, "STATIC", "ShutdownMonitor", 0, 0, 0, 0, 0, None, None, None, None)
        win32gui.SetWindowLong(self.hwnd, win32con.GWL_WNDPROC, self.wnd_proc)
        self.h_power_notify = user32.RegisterPowerSettingNotification(self.hwnd, ctypes.byref(GUID_MONITOR_POWER_ON), win32con.DEVICE_NOTIFY_WINDOW_HANDLE)

    def wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg in self.message_map:
            return self.message_map[msg](wparam, lparam)
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def on_shutdown(self, wparam, lparam):
        # 上报关机状态
        report_system_status("设备关机", False)
        # 允许关机
        return True

    def on_power_event(self, wparam, lparam):
        """处理电源事件"""
        global system_suspended, screen_off
        
        # PBT_APMSUSPEND: 系统正在挂起（休眠/睡眠）
        if wparam == 0x0004: # PBT_APMSUSPEND
            system_suspended = True
            report_system_status("设备待机", False)
            print("系统进入休眠状态")
        # PBT_APMRESUMESUSPEND: 系统从挂起状态恢复
        elif wparam == 0x0007: # PBT_APMRESUMESUSPEND
            system_suspended = False
            report_system_status("系统恢复", True)
            print("系统从休眠状态恢复")
        # PBT_POWERSETTINGCHANGE: 电源设置改变事件
        elif wparam == 0x8013: # PBT_POWERSETTINGCHANGE
            settings = ctypes.cast(lparam, ctypes.POINTER(POWERBROADCAST_SETTING)).contents
            if settings.PowerSetting == GUID_MONITOR_POWER_ON:
                if settings.Data[0] == 0:  # 屏幕关闭
                    if not screen_off:
                        screen_off = True
                        print("屏幕关闭")
                elif settings.Data[0] == 1:  # 屏幕开启
                    if screen_off:
                        screen_off = False
                        print("屏幕开启")
        
        return True

app_mapping = {}
try:
    with open('apps.json', 'r', encoding='utf-8') as f:
        original_mapping = json.load(f)
        app_mapping = {k.lower(): v for k, v in original_mapping.items()}
    print("读取成功")
except FileNotFoundError:
    print("错误：文件未找到")
except json.JSONDecodeError:
    print("错误：JSON格式不正确")
except Exception as e:
    print(f"未知错误：{str(e)}")

def get_mapped_app_name(exe_name):
    """根据对照表获取映射的应用名称"""
    exe_name_lower = exe_name.lower()
    return app_mapping.get(exe_name_lower, exe_name)

def report_system_status(app_name, running):
    """上报系统状态"""
    try:
        payload = {
            "secret": SECRET_KEY,
            "device": DEVICE_ID,
            "app_name": app_name,
            "running": running
        }
        response = requests.post(API_URL, json=payload, timeout=5)
        print(f"状态上报成功: {app_name}, running: {running}, 状态码: {response.status_code}")
        return True
    except Exception as e:
        print(f"状态上报失败: {app_name}, 错误: {str(e)}")
        return False

def report_app_change(current_app):
    """上报应用程序变化"""
    global last_app

    if current_app != last_app:
        # 根据应用名称判断 running 状态
        # 如果是待机、关机、屏幕关闭等状态，running 为 False，否则为 True
        running_status = True
        if current_app in ["设备待机", "设备关机", "系统休眠", "屏幕关闭"]:
            running_status = False
        
        try:
            payload = {
                "secret": SECRET_KEY,
                "device": DEVICE_ID,
                "app_name": current_app,
                "running": running_status
            }

            response = requests.post(API_URL, json=payload)

            if response.status_code == 200:
                print(f"成功上报: {current_app}, running: {running_status}")
                last_app = current_app
            else:
                print(f"上报失败: {response.text}")

        except Exception as e:
            print(f"发生错误: {str(e)}")

def get_foreground_app():
    """使用win32api获取前台应用窗口"""
    global system_suspended, screen_off
    
    # 如果系统处于休眠状态，直接返回待机状态
    if system_suspended:
        return "设备待机"
    
    # 如果屏幕关闭，返回屏幕关闭
    if screen_off:
        return "屏幕关闭"

    try:
        # 获取前台窗口句柄
        window = win32gui.GetForegroundWindow()
        if not window:
            return "桌面"
        
        # 获取窗口标题
        window_title = win32gui.GetWindowText(window)
        # 获取进程ID
        _, pid = win32process.GetWindowThreadProcessId(window)
        
        if not pid:
            return "桌面"
            
        # 打开进程获取exe名称
        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
        if not handle:
            return "系统进程"
            
        exe_name = win32process.GetModuleFileNameEx(handle, 0)
        win32api.CloseHandle(handle)  # 关闭句柄释放资源

        # 提取exe文件名并获取映射名称
        exe_filename = exe_name.split('\\')[-1]
        mapped_name = get_mapped_app_name(exe_filename)

        return mapped_name
    except Exception as e:
        # 如果出现特定错误，可能是系统休眠导致的
        error_code = win32api.GetLastError()
        if error_code in (5, 87, 1008):  # 访问拒绝、参数错误、无效句柄
            system_suspended = True
            report_system_status("设备待机", False)
            return "设备待机"
        print(f"获取前台应用错误: {str(e)}, 错误代码: {error_code}")
        return "未知"

def monitor_app_changes():
    """监控应用变化"""
    while True:
        try:
            current_app = get_foreground_app()
            report_app_change(current_app)
            time.sleep(1)  # 每秒检查一次
        except Exception as e:
            print(f"监控线程错误: {str(e)}")
            time.sleep(1)

if __name__ == "__main__":
    shutdown_hook = WindowHook()

    print("开始监控应用变化...")
    monitor_thread = Thread(target=monitor_app_changes)
    monitor_thread.daemon = True
    monitor_thread.start()

    try:
        # 消息循环，确保能接收到电源事件
        msg = wintypes.MSG()
        while True:
            result = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == 0:  # WM_QUIT
                break
            elif result == -1:  # 错误
                break
            else:
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        print("停止监控")
    finally:
        if 'shutdown_hook' in locals() and shutdown_hook:
            if hasattr(shutdown_hook, 'h_power_notify') and shutdown_hook.h_power_notify:
                user32.UnregisterPowerSettingNotification(shutdown_hook.h_power_notify)
            if hasattr(shutdown_hook, 'hwnd') and shutdown_hook.hwnd and win32gui.IsWindow(shutdown_hook.hwnd):
                win32gui.DestroyWindow(shutdown_hook.hwnd)
