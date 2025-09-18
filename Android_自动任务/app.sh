#!/bin/bash

# 需要将该文件放到如下路径 /storage/emulated/0/TimeTracker/app.sh
# 然后填写如下信息
URL="https://api-usage.1812z.top/api"
SECRET="your-secret-here"
# 检查是否传入了足够的参数
if [ "$#" -lt 3 ]; then
    echo "使用方法: $0 <设备名称> <应用名称> <running状态(true/false)> <设备电量>"
    exit 1
fi

DEVICE=$1
APP_NAME=$2
RUNNING=$3
BATTERY=$4

# 验证running参数只能是true或false
if [ "$RUNNING" != "true" ] && [ "$RUNNING" != "false" ]; then
    echo "错误: running状态必须是true或false"
    exit 1
fi

# 执行curl请求
curl -X POST "$URL" \
-H "Content-Type: application/json" \
-d '{
  "secret": "'"$SECRET"'",
  "device": "'"$DEVICE"'",
  "app_name": "'"$APP_NAME"'",
  "running": '"$RUNNING"',
  "batteryLevel": "'"$BATTERY"'"
}'
