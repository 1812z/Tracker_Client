#!/bin/bash

# 需要将该文件放到如下路径 /storage/emulated/0/TimeTracker/battery.sh
# 然后填写如下信息
URL="https://api-usage.1812z.top/api"
SECRET="your-secret"
# 检查是否传入了足够的参数
if [ "$#" -lt 3 ]; then
    echo "使用方法: $0 <设备名称> <电量> <充电状态(true/false)>"
    exit 1
fi

DEVICE=$1
BATTERY_LEVEL=$2
CHARGING=$3

# 执行curl请求
curl -X POST "$URL" \
-H "Content-Type: application/json" \
-d '{
  "secret": "'"$SECRET"'",
  "device": "'"$DEVICE"'",
  "batteryLevel": "'"$BATTERY_LEVEL"'",
  "isCharging": '"$CHARGING"'
}'
