#!/system/bin/sh

# 需要将该文件放到如下路径 /storage/emulated/0/TimeTracker/tracker.sh
# 然后填写如下信息
URL="https://api-usage.1812z.top/api"
SECRET="your-secret"
DEVICE="手机"

FILE="/storage/emulated/0/TimeTracker/tracker.txt"

# 创建目录和文件（如果不存在）
mkdir -p "$(dirname "$FILE")"
if [ ! -f "$FILE" ]; then
    touch "$FILE"
    echo "系统桌面,100,false,true" > "$FILE"
fi

TYPE="$1"
VALUE="$2"

# 读取文件内容
CONTENT=$(cat "$FILE")

# 解析字段
APP_NAME=$(echo "$CONTENT" | cut -d',' -f1)
BATTERY_LEVEL=$(echo "$CONTENT" | cut -d',' -f2)
IS_CHARGING=$(echo "$CONTENT" | cut -d',' -f3)
RUNNING=$(echo "$CONTENT" | cut -d',' -f4)

# 根据类型处理
case "$TYPE" in
    "app_name")
        APP_NAME="$VALUE"
        echo "$APP_NAME,$BATTERY_LEVEL,$IS_CHARGING,$RUNNING" > "$FILE"
        ;;
    "batteryLevel")
        BATTERY_LEVEL="$VALUE"
        echo "$APP_NAME,$BATTERY_LEVEL,$IS_CHARGING,$RUNNING" > "$FILE"
        ;;
    "isCharging")
        IS_CHARGING="$VALUE"
        echo "$APP_NAME,$BATTERY_LEVEL,$IS_CHARGING,$RUNNING" > "$FILE"
        ;;
    "running")
        RUNNING="$VALUE"
        echo "$APP_NAME,$BATTERY_LEVEL,$IS_CHARGING,$RUNNING" > "$FILE"
        ;;
    "report")
        # 将字符串转为布尔值
        if [ "$RUNNING" = "true" ]; then
            RUNNING_BOOL="true"
        else
            RUNNING_BOOL="false"
        fi
    
        if [ "$IS_CHARGING" = "true" ]; then
            IS_CHARGING_BOOL="true"
        else
            IS_CHARGING_BOOL="false"
        fi
    
        curl -X POST "$URL" \
            -H "Content-Type: application/json" \
            -d '{
              "secret": "'"$SECRET"'",
              "device": "'"$DEVICE"'",
              "app_name": "'"$APP_NAME"'",
              "running": '"$RUNNING_BOOL"',
              "batteryLevel": "'"$BATTERY_LEVEL"'",
              "isCharging": '"$IS_CHARGING_BOOL"'
            }'
        ;;
    *)
        echo "未知类型: $TYPE"
        exit 1
        ;;
esac
