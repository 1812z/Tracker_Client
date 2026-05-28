#!/bin/bash

# 配置
API_URL="https://api-usage.1812z.top/api"  # 替换为实际的API地址
SECRET="your-secret-key-here"          # 替换为实际的密钥
DEVICE=$(grep PRETTY_NAME /etc/os-release | cut -d'"' -f2)    # 设备ID 自动获取系统名字 可手动改
INTERVAL=2                  # 检测间隔(秒)

# 上次状态
last_app=""
last_battery=""
last_charging=""
last_running=""

# 获取当前状态
get_running() {
    local percent=$(( $(brightnessctl get 2>/dev/null || echo 100) * 100 / $(brightnessctl max 2>/dev/null || echo 100) ))
    if [ "$percent" -lt 1 ]; then
        echo "false"
    else
        echo "true"
    fi
}

get_battery() {
    cat /sys/class/power_supply/BAT0/capacity 2>/dev/null || echo "0"
}

get_charging() {
    local ac_path=""
    if [ -f /sys/class/power_supply/ACAD/online ]; then
        ac_path="/sys/class/power_supply/ACAD/online"
    elif [ -f /sys/class/power_supply/AC/online ]; then
        ac_path="/sys/class/power_supply/AC/online"
    fi
    
    if [ -n "$ac_path" ] && [ "$(cat "$ac_path" 2>/dev/null)" = "1" ]; then
        echo "true"
    else
        echo "false"
    fi
}

# 检测系统是否处于休眠/锁屏状态
is_idle_or_locked() {
    # 检测锁屏状态
    # 方法1: 检查 logind 会话状态
    local session_id=$(loginctl | grep "$(whoami)" | awk '{print $1}' | head -1)
    if [ -n "$session_id" ]; then
        local state=$(loginctl show-session "$session_id" -p State --value 2>/dev/null)
        if [ "$state" = "locking" ] || [ "$state" = "active" ]; then
            return 1  # 未锁定
        fi
    fi
    
    # 方法2: 检测屏幕是否为空（Wayland）
    if [ "$XDG_SESSION_TYPE" = "wayland" ]; then
        local desktop=$(echo "$XDG_CURRENT_DESKTOP" | tr '[:upper:]' '[:lower:]')
        
        if [[ "$desktop" == *"hyprland"* ]] && command -v hyprctl >/dev/null 2>&1; then
            local idle=$(hyprctl getoption animations:0 2>/dev/null)
            # Hyprland 可以通过检查活动窗口判断
            local active_win=$(hyprctl activewindow 2>/dev/null)
            if [ -z "$active_win" ] || [ "$active_win" = "Invalid" ]; then
                return 0  # 空闲/锁屏
            fi
        fi
    fi
    
    # 方法3: 检测 idle 时间（X11）
    if command -v xprintidle >/dev/null 2>&1; then
        local idle_time=$(xprintidle 2>/dev/null)
        # 如果 idle 时间超过 5 秒，认为是锁屏/休眠状态
        if [ -n "$idle_time" ] && [ "$idle_time" -gt 5000 ]; then
            return 0  # 空闲/锁屏
        fi
    fi
    
    # 方法4: 检测 gnome-screensaver
    if command -v gnome-screensaver-command >/dev/null 2>&1; then
        if gnome-screensaver-command -q 2>/dev/null | grep -q "is active"; then
            return 0  # 锁屏
        fi
    fi
    
    # 方法5: 检测 xdg-screensaver
    if command -v xdg-screensaver >/dev/null 2>&1; then
        if xdg-screensaver status 2>/dev/null | grep -q "active"; then
            return 0  # 锁屏
        fi
    fi
    
    return 1  # 未锁定
}

get_app() {
    # 动态获取显示器环境变量（解决服务早于桌面启动的问题）
    if [ -z "$DISPLAY" ]; then
        export DISPLAY=$(systemctl --user show-environment 2>/dev/null | grep '^DISPLAY=' | cut -d= -f2-)
    fi
    if [ -z "$XAUTHORITY" ]; then
        export XAUTHORITY=$(systemctl --user show-environment 2>/dev/null | grep '^XAUTHORITY=' | cut -d= -f2-)
    fi
    
    # 检测是否空闲/锁屏
    if is_idle_or_locked; then
        echo "锁屏"
        return
    fi
    
    local raw_app=""
    
    # 检查是否为 Wayland 会话
    if [ "$XDG_SESSION_TYPE" = "wayland" ] || [ -n "$WAYLAND_DISPLAY" ]; then
        local desktop=$(echo "$XDG_CURRENT_DESKTOP" | tr '[:upper:]' '[:lower:]')
        local handled=false
        
        if [[ "$desktop" == *"hyprland"* ]] && command -v hyprctl >/dev/null 2>&1; then
            # Hyprland
            raw_app=$(hyprctl activewindow | grep "class:" | awk '{print $2}')
            handled=true
        elif [[ "$desktop" == *"sway"* ]] && command -v swaymsg >/dev/null 2>&1; then
            # Sway
            raw_app=$(swaymsg -t get_tree 2>/dev/null | grep -Po '"focused": true.*?,"app_id": "[^"]*"' | grep -Po '(?<="app_id": ")[^"]*')
            handled=true
        elif [[ "$desktop" == *"niri"* ]] || command -v niri >/dev/null 2>&1; then
            # Niri
            raw_app=$(niri msg --json focused-window 2>/dev/null | sed -n 's/.*"app_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
            handled=true
        elif [[ "$desktop" == *"kde"* ]] && command -v qdbus >/dev/null 2>&1; then
            # KDE Plasma Wayland (存在一定局限性，最新版本 KWin 安全策略限制)
            raw_app=$(qdbus org.kde.KWin /KWin org.kde.KWin.activeWindow 2>/dev/null)
            handled=true
        elif [[ "$desktop" == *"gnome"* ]] && command -v gdbus >/dev/null 2>&1; then
            # GNOME Wayland (受限：仅在允许 unsafe-mode 的 dbus Eval，或安装了暴露 API 的扩展时工作)
            raw_app=$(gdbus call -e -d org.gnome.Shell -o /org/gnome/Shell -m org.gnome.Shell.Eval "global.display.focus_window ? global.display.focus_window.get_wm_class() : ''" 2>/dev/null | cut -d'"' -f2)
            handled=true
        fi
        
        # 如果未被原生支持的桌面环境捕获，才尝试通用 Fallback
        if [ "$handled" = false ]; then
            # wlroots 通用 Fallback (需安装 lswt 工具)
            if [ -z "$raw_app" ] && command -v lswt >/dev/null 2>&1; then
                raw_app=$(lswt -f json 2>/dev/null | grep -Po '"focused": true.*?,"app-id": "[^"]*"' | grep -Po '(?<="app-id": ")[^"]*')
            fi
            
            # XWayland Fallback (兼容运行在 XWayland 中的传统应用)
            if [ -z "$raw_app" ] && command -v xdotool >/dev/null 2>&1; then
                raw_app=$(xdotool getactivewindow 2>/dev/null | xargs -I{} xprop -id {} WM_CLASS 2>/dev/null | cut -d'"' -f2)
            fi
        fi
    else
        # X11 环境
        if command -v xdotool >/dev/null 2>&1; then
            raw_app=$(xdotool getactivewindow 2>/dev/null | xargs -I{} xprop -id {} WM_CLASS 2>/dev/null | cut -d'"' -f2)
        fi
    fi

    # 处理空窗口或异常返回值（比如在桌面未打开任何应用时）
    # Hyprland 会返回 "Invalid"，部分工具可能返回 "null"、"nil" 或干脆为空
    if [ -z "$raw_app" ] || [ "$raw_app" = "null" ] || [ "$raw_app" = "Invalid" ] || [ "$raw_app" = "nil" ]; then
        raw_app="桌面"
    fi

    local apps_txt="$(dirname "$0")/apps.txt"
    
    if [ -n "$raw_app" ] && [ -f "$apps_txt" ]; then
        local mapped_app=$(grep -i "^${raw_app}=" "$apps_txt" | head -n 1 | cut -d'=' -f2-)
        
        if [ -n "$mapped_app" ]; then
            echo "$mapped_app"
        else
            echo "$raw_app"
        fi
    else
        echo "$raw_app"
    fi
}

# 上报数据
report() {
    local app="$1"
    local battery="$2"
    local charging="$3"
    local running="$4"
    
    curl -s -X POST "$API_URL" \
        -H "Content-Type: application/json" \
        -d "{
            \"secret\": \"$SECRET\",
            \"device\": \"$DEVICE\",
            \"app_name\": \"$app\",
            \"running\": $running,
            \"batteryLevel\": $battery,
            \"isCharging\": $charging
        }"
    
    echo " [$(date '+%H:%M:%S')] 上报: app=$app, battery=$battery%, charging=$charging, running=$running"
}

# 主循环
echo "🚀 监控启动 (Ctrl+C 退出)"
echo "📡 上报地址: $API_URL"
echo "-----------------------------------"

while true; do
    current_app=$(get_app)
    current_battery=$(get_battery)
    current_charging=$(get_charging)
    current_running=$(get_running)
    
    # 检测变化
    changed=false
    if [[ "$current_app" != "$last_app" ]] || \
       [[ "$current_battery" != "$last_battery" ]] || \
       [[ "$current_charging" != "$last_charging" ]] || \
       [[ "$current_running" != "$last_running" ]]; then
        changed=true
    fi
    
    if $changed; then
        echo "📝 检测到变化，准备上报..."
        report "$current_app" "$current_battery" "$current_charging" "$current_running"
        
        last_app="$current_app"
        last_battery="$current_battery"
        last_charging="$current_charging"
        last_running="$current_running"
    fi
    
    sleep $INTERVAL
done