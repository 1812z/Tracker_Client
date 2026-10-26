# RunTime Tracker

> 本项目由 AI 辅助开发
> 版本: 1.1.8

RunTime Tracker 是一个 Windows 设备使用情况监控工具：实时跟踪前台应用，把使用数据上报到服务端，并在客户端内查看统计、最近记录、设备状态与服务器管理信息。

## 功能特性

- 实时监控前台应用，应用变化时自动上报
- 电池状态与充电状态采集
- 使用统计：今日 24 小时分布、应用排行、周维度统计（PyQtChart）
- 最近记录：设备最近 30 条应用切换记录
- 设备总览：所有设备的当前应用、运行状态、电量与更新时间
- 服务器管理：管理员登录后可查看/修改服务端配置、重启服务、启停 AI 任务、更新账户
- 开机自启（HKCU Run）与 `--minimized` 托盘启动
- 主题切换（跟随系统、浅色、深色）
- 每日轮转日志、增量日志查看与导出
- 系统通知使用原生 Toast（首次通知时会创建开始菜单快捷方式用于注册应用标识）

## 系统要求

- Windows 10 / 11
- Python 3.8 或更高（已在 Python 3.13 验证）
- 可访问 RunTime_Tracker 服务端 API

## 安装与运行

```bash
pip install -r requirements.txt
python main.py
```

开发与打包环境：

```bash
pip install -r requirements-dev.txt
```

打包：

```bash
python build.py
```

打包产物位于 `dist/RunTimeTracker/`，运行 `RunTimeTracker.exe`。打包时不会内置 `config.json`，首次启动会自动生成默认配置。

## 数据目录

| 模式 | 目录 |
|---|---|
| 打包运行 | `%APPDATA%\RunTimeTracker\` |
| 源码运行 | 项目根目录 |

目录内包含：

- `config.json`：本地配置（API 地址、密钥、设备 ID、监控间隔、主题、自启）
- `apps.json`：应用映射（用户可编辑；首次运行从内置模板复制）
- `logs/runtime_tracker.log`：当天日志；历史文件为 `runtime_tracker.log.YYYY-MM-DD`，保留 30 天

从旧版本升级时，打包模式会把 exe 同目录的 `config.json` / `apps.json` 迁移到 `%APPDATA%\RunTimeTracker\`。

## 配置说明

在「配置」页面修改：

- **API 地址**：上报接口完整地址，例如 `https://your-server.example/api`
- **密钥**：与服务端约定的上报密钥；以掩码方式输入与显示
- **设备 ID**：设备唯一标识，留空时自动生成 `主机名-随机串`
- **监控间隔**：1–3600 秒
- **上报功能**：关闭后不再发送任何上报请求
- **日志留存**：保留天数（1–3650）与保留数量（1–1000），超出部分自动删除
- **开机自启**：写入当前用户注册表，登录后以托盘方式启动
- **测试连接**：调用 `GET /api/ip` 验证服务端可达性并显示延迟

配置保存在本机配置文件中，不会上传；管理员密码与 JWT 不会写入配置。

## 页面说明

1. **主页**：当前应用、电池状态、设备 ID
2. **统计**：选择日期查看今日总时长、24 小时分布、应用排行；切换周偏移查看周统计
3. **最近记录**：最近 30 条应用切换记录（时间转换为本地时区）
4. **设备**：所有设备的当前应用、状态、电量、应用开始时间与电量更新时间
5. **应用映射**：维护可执行文件名到显示名称的映射，增删改立即保存
6. **日志**：按日期查看、刷新、导出日志
7. **配置**：主题、API、监控、自启与连接测试
8. **管理**：登录服务端管理员账户后管理服务端配置、服务与 AI 任务
9. **关于**：版本与项目链接

## 服务端 API

客户端使用以下接口（详见服务端 Wiki）：

- 上报：`POST /api`
- 查询：`GET /api/devices`、`GET /api/recent/:deviceId`、`GET /api/stats/:deviceId`、`GET /api/weekly/:deviceId`、`GET /api/ip`
- 管理：`POST /admin/login`、`POST /admin/account/update`、`GET/POST /admin/config`、`POST /admin/restart`、`POST /admin/ai/start`、`POST /admin/ai/stop`、`POST /admin/ai/trigger/:deviceId`

查询接口按文档视为公开只读，不携带 `secret`；管理接口使用 `Authorization: Bearer <token>`。服务端实际把管理路由挂载在 `/admin` 前缀下（Wiki 中省略了该前缀）。

## 安全说明

- 管理功能要求 HTTPS；仅 `localhost` / `127.0.0.1` / `::1` 允许使用 HTTP
- 管理员 JWT 仅保存在内存，退出登录、重启服务或关闭客户端后失效
- 服务端配置中的密钥类字段在管理页以掩码显示且不可编辑
- 重启服务、停止 AI 任务等破坏性操作需要二次确认
- 上报密钥以明文存储在本地 `config.json` 中；如需更高安全性，可后续接入 Windows DPAPI

## 常见问题

### 应用无法启动

- 确认已安装 `requirements.txt` 中的全部依赖（包含 `pywin32`、`PyQtChart`）
- 查看 `logs/runtime_tracker.log`

### 数据上报失败

- 检查 API 地址、密钥、设备 ID 是否完整
- 检查网络与服务端状态；管理页可查看服务端配置
- 4xx 错误不会重试，5xx/网络异常会退避重试

### 统计 / 设备页面无数据

- 确认配置页的 API 地址与设备 ID 已保存
- 使用「测试连接」确认服务端可达
- 服务端需已有该设备的上报记录

### 管理页无法登录

- 仅支持服务端管理员账户
- 非本机地址必须使用 HTTPS

## 日志文件

日志位于 `logs/runtime_tracker.log`，每天零点轮转，历史文件命名为 `runtime_tracker.log.YYYY-MM-DD`。默认保留最近 30 天、最多 30 个历史文件，可在「配置」页面修改；超出限制的文件会在启动、保存配置以及每 6 小时自动清理时删除。可在「日志」页面查看和导出。

## 项目链接

- [GitHub - RunTime_Tracker_Client_Windows](https://github.com/CSSQY/RunTime_Tracker_Client_Windows)
- [GitHub - RunTime_Tracker (服务端)](https://github.com/1812z/RunTime_Tracker)
- [GitHub - Tracker_Client (客户端)](https://github.com/1812z/Tracker_Client)
- [GitHub - PyQt-Fluent-Widgets (UI框架)](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)

## 致谢

本项目的上报核心逻辑参考并受益于 [1812z](https://github.com/1812z) 的 [Tracker_Client](https://github.com/1812z/Tracker_Client) 项目。感谢其开源工作为本项目奠定的基础。原项目链接：[https://github.com/1812z/Tracker_Client](https://github.com/1812z/Tracker_Client)

感谢 [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) 提供的 UI 框架。

## 开源许可

本项目采用 MIT 许可证。

## 开发者

- **作者**: CSSQY

## 联系我们

- GitHub Issues: [https://github.com/CSSQY/RunTime_Tracker_Client_Windows/issues](https://github.com/CSSQY/RunTime_Tracker_Client_Windows/issues)
