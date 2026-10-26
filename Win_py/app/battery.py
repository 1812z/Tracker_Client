"""电池状态读取。"""

import ctypes
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


def get_battery_status() -> Tuple[Optional[int], Optional[bool]]:
    """返回 (电量, 是否充电)。

    - (-1, False): 无电池
    - (None, None): 读取失败或电量未知
    """
    try:
        kernel32 = ctypes.windll.kernel32
    except AttributeError:
        return None, None

    status = SYSTEM_POWER_STATUS()
    try:
        kernel32.GetSystemPowerStatus.argtypes = [ctypes.POINTER(SYSTEM_POWER_STATUS)]
        kernel32.GetSystemPowerStatus.restype = ctypes.c_int
        if not kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return None, None
    except Exception as exc:
        logger.debug("读取电池状态失败: %s", exc)
        return None, None

    if status.BatteryFlag == 128:
        return -1, False
    if status.BatteryFlag == 255 or status.BatteryLifePercent == 255:
        return None, None

    return int(status.BatteryLifePercent), status.ACLineStatus == 1
