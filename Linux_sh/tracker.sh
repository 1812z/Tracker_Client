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

# 获取当前状态
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

get_app() {
    local raw_app=""
    
    # 检查是否为 Wayland 会话
    if [ "$XDG_SESSION_TYPE" = "wayland" ] || [ -n "$WAYLAND_DISPLAY" ]; then
        local desktop=$(echo "$XDG_CURRENT_DESKTOP" | tr '[:upper:]' '[:lower:]')
        
        if [[ "$desktop" == *"hyprland"* ]] && command -v hyprctl >/dev/null 2>&1; then
            # Hyprland
            raw_app=$(hyprctl activewindow | grep "class:" | awk '{print $2}')
        elif [[ "$desktop" == *"sway"* ]] && command -v swaymsg >/dev/null 2>&1; then
            # Sway
            raw_app=$(swaymsg -t get_tree 2>/dev/null | grep -Po '"focused": true.*?,"app_id": "[^"]*"' | grep -Po '(?<="app_id": ")[^"]*')
        elif [[ "$desktop" == *"niri"* ]] || command -v niri >/dev/null 2>&1; then
            # Niri
            raw_app=$(niri msg --json focused-window 2>/dev/null | sed -n 's/.*"app_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
        elif [[ "$desktop" == *"kde"* ]] && command -v qdbus >/dev/null 2>&1; then
            # KDE Plasma Wayland (存在一定局限性，最新版本 KWin 安全策略限制)
            raw_app=$(qdbus org.kde.KWin /KWin org.kde.KWin.activeWindow 2>/dev/null)
        elif [[ "$desktop" == *"gnome"* ]] && command -v gdbus >/dev/null 2>&1; then
            # GNOME Wayland (受限：仅在允许 unsafe-mode 的 dbus Eval，或安装了暴露 API 的扩展时工作)
            raw_app=$(gdbus call -e -d org.gnome.Shell -o /org/gnome/Shell -m org.gnome.Shell.Eval "global.display.focus_window ? global.display.focus_window.get_wm_class() : ''" 2>/dev/null | cut -d'"' -f2)
        fi
        
        # wlroots 通用 Fallback (需安装 lswt 工具)
        if [ -z "$raw_app" ] && command -v lswt >/dev/null 2>&1; then
            raw_app=$(lswt -f json 2>/dev/null | grep -Po '"focused": true.*?,"app-id": "[^"]*"' | grep -Po '(?<="app-id": ")[^"]*')
        fi
        
        # XWayland Fallback (兼容运行在 XWayland 中的传统应用)
        if [ -z "$raw_app" ] && command -v xdotool >/dev/null 2>&1; then
            raw_app=$(xprop -id $(xdotool getactivewindow 2>/dev/null) WM_CLASS 2>/dev/null | cut -d'"' -f2)
        fi
    else
        # X11 环境
        if command -v xdotool >/dev/null 2>&1; then
            raw_app=$(xprop -id $(xdotool getactivewindow 2>/dev/null) WM_CLASS 2>/dev/null | cut -d'"' -f2)
        fi
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
    
    curl -s -X POST "$API_URL" \
        -H "Content-Type: application/json" \
        -d "{
            \"secret\": \"$SECRET\",
            \"device\": \"$DEVICE\",
            \"app_name\": \"$app\",
            \"running\": true,
            \"batteryLevel\": $battery,
            \"isCharging\": $charging
        }"
    
    echo " [$(date '+%H:%M:%S')] 上报: app=$app, battery=$battery%, charging=$charging"
}

# 主循环
echo "🚀 监控启动 (Ctrl+C 退出)"
echo "📡 上报地址: $API_URL"
echo "-----------------------------------"

while true; do
    current_app=$(get_app)
    current_battery=$(get_battery)
    current_charging=$(get_charging)
    
    # 检测变化
    changed=false
    if [[ "$current_app" != "$last_app" ]] || \
       [[ "$current_battery" != "$last_battery" ]] || \
       [[ "$current_charging" != "$last_charging" ]]; then
        changed=true
    fi
    
    if $changed; then
        echo "📝 检测到变化，准备上报..."
        report "$current_app" "$current_battery" "$current_charging"
        
        last_app="$current_app"
        last_battery="$current_battery"
        last_charging="$current_charging"
    fi
    
    sleep $INTERVAL
done