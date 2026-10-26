from app.foreground import resolve_title


def test_specific_rules_win_over_generic_ones():
    assert resolve_title("计算器 - 设置") == "计算器"
    assert resolve_title("任务管理器") == "任务管理器"


def test_chinese_and_english_titles():
    assert resolve_title("Calculator") == "计算器"
    assert resolve_title("打开设置") == "系统设置"
    assert resolve_title("Windows PowerShell") == "PowerShell"


def test_unknown_and_empty():
    assert resolve_title("某个未知窗口") is None
    assert resolve_title("") is None
