# 使用说明

## Android （自动任务）端配置步骤
### ADB级别后台保活，常驻后台运行，但需要Shizuku（重启后需要重新打开，如果不想多次启动可以看下面方案）
### 1. 安装必要软件
- [自动任务 (AutoTask)](https://github.com/xjunz/AutoTask)
- [Shizuku](https://github.com/RikkaApps/Shizuku)
- 任意文件管理器

### 2. 部署脚本文件
1. 下载 [app.sh](Android_%E8%87%AA%E5%8A%A8%E4%BB%BB%E5%8A%A1/app.sh)
2. 放置到设备路径：`/storage/emulated/0/TimeTracker/app.sh`
3. 编辑脚本文件，修改以下常量配置：
   - `URL` - API地址
   - `SECRET` - 认证密钥

### 3. 配置自动任务
1. 导入任务配置文件：
   - [应用上报.xtsk](Android_%E8%87%AA%E5%8A%A8%E4%BB%BB%E5%8A%A1/%E5%BA%94%E7%94%A8%E4%B8%8A%E6%8A%A5.xtsk)
   - [息屏.xtsk](Android_%E8%87%AA%E5%8A%A8%E4%BB%BB%E5%8A%A1/%E6%81%AF%E5%B1%8F.xtsk)
2. 激活自动任务

### 4. 验证配置
确保所有服务正常运行，数据能正确上报

## Android （Macrodroid）端配置步骤
### 无障碍+自启动保活，一般情况不会被杀后台，使用更方便
1. 导入配置文件：
    - [设备信息上报.category](Android_Macrodroid/%E8%AE%BE%E5%A4%87%E4%BF%A1%E6%81%AF%E4%B8%8A%E6%8A%A5.category)[应用上报.xtsk]([设备信息上报.category](Android_Macrodroid/%E8%AE%BE%E5%A4%87%E4%BF%A1%E6%81%AF%E4%B8%8A%E6%8A%A5.category))

2. 转到 主页/变量/新建，新建变量SECRET和DEVICE_ID，类型为字符串，分别是密钥和设备名
3. 激活宏，请给予相关权限（无障碍，读取应用列表等）

## Win 端配置步骤
暂时可以用[main.py](Win_py/main.py)，不完善没有自启动
如果您也在使用这个工具接入Hass，只需要打开前台软件监听即可[PCTools](https://github.com/1812z/PCTools)

## Linux端
下次一定
