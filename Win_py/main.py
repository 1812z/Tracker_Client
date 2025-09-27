import requests
import time
from threading import Thread
import win32gui
import win32process
import win32api
import win32con
import json
import ctypes
from ctypes import wintypes

# 配置参数
API_URL = "https://api-usage.1812z.top/api"  # 替换为实际的API地址
SECRET_KEY = "3"  # 替换为实际的密钥
DEVICE_ID = "电脑"  # 替换为实际的设备ID

# 上一次记录的应用程序名称
last_app = None
# 记录系统是否处于休眠状态
system_suspended = False

class WindowHook:
    def __init__(self):
        self.message_map = {
            win32con.WM_QUERYENDSESSION: self.on_shutdown,
            win32con.WM_POWERBROADCAST: self.on_power_event
        }
        self.hwnd = win32gui.CreateWindowEx(
            0, "STATIC", "ShutdownMonitor", 0, 0, 0, 0, 0, None, None, None, None)
        win32gui.SetWindowLong(self.hwnd, win32con.GWL_WNDPROC, self.wnd_proc)

    def wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg in self.message_map:
            return self.message_map[msg](wparam, lparam)
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def on_shutdown(self, wparam, lparam):
        # 上报关机状态
        try:
            payload = {
                "secret": SECRET_KEY,
                "device": DEVICE_ID,
                "app_name": "设备待机",
                "running": False
            }
            response = requests.post(API_URL, json=payload)
            print(f"关机状态上报成功: {response.status_code}")
        except Exception as e:
            print(f"关机上报失败: {str(e)}")

        # 允许关机
        return True

    def on_power_event(self, wparam, lparam):
        """处理电源事件"""
        global system_suspended
        
        # PBT_APMSUSPEND: 系统正在挂起（休眠/睡眠）
        if wparam == 0x0004:
            system_suspended = True
            report_system_suspend()
            print("系统进入休眠状态")
        # PBT_APMRESUMESUSPEND: 系统从挂起状态恢复
        elif wparam == 0x0007:
            system_suspended = False
            report_system_resume()
            print("系统从休眠状态恢复")
        
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
    # 转换为小写进行匹配
    exe_name_lower = exe_name.lower()
    # 如果在对照表中则返回映射名称，否则返回原名称
    return app_mapping.get(exe_name_lower, exe_name)

def report_app_change(current_app):
    """上报应用程序变化"""
    global last_app

    if current_app != last_app:
        try:
            payload = {
                "secret": SECRET_KEY,
                "device": DEVICE_ID,
                "app_name": current_app,
                "running": True
            }

            response = requests.post(API_URL, json=payload)

            if response.status_code == 200:
                print(f"成功上报: {current_app}")
                last_app = current_app
            else:
                print(f"上报失败: {response.text}")

        except Exception as e:
            print(f"发生错误: {str(e)}")

def report_system_suspend():
    """上报系统休眠状态"""
    try:
        payload = {
            "secret": SECRET_KEY,
            "device": DEVICE_ID,
            "app_name": "设备待机",
            "running": False
        }
        response = requests.post(API_URL, json=payload, timeout=5)
        print(f"休眠状态上报成功: {response.status_code}")
    except Exception as e:
        print(f"休眠状态上报失败: {str(e)}")

def report_system_resume():
    """上报系统恢复状态"""
    try:
        payload = {
            "secret": SECRET_KEY,
            "device": DEVICE_ID,
            "app_name": "系统恢复",
            "running": True
        }
        response = requests.post(API_URL, json=payload, timeout=5)
        print(f"系统恢复上报成功: {response.status_code}")
    except Exception as e:
        print(f"系统恢复上报失败: {str(e)}")

def get_foreground_app():
    """使用win32api获取前台应用窗口"""
    global system_suspended
    
    # 如果系统处于休眠状态，直接返回待机状态
    if system_suspended:
        return "设备待机"
    
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

        # 返回映射后的应用名称
        return mapped_name
    except Exception as e:
        # 如果出现特定错误，可能是系统休眠导致的
        error_code = win32api.GetLastError()
        if error_code in (5, 87, 1008):  # 访问拒绝、参数错误、无效句柄
            system_suspended = True
            report_system_suspend()
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
