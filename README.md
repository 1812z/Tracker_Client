# 使用说明

## Android 端配置步骤

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

## Win 端配置步骤
暂时可以用[main.py](Win_py/main.py)，不完善没有自启动

## Linux端
下次一定
