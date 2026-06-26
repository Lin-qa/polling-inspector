# 轮询巡检工具

一个独立的接口巡检工具，按 xlsx 配置持续轮询接口，并通过企业微信群机器人通知异常和恢复。

## 第一版功能

- xlsx 配置驱动，不依赖压测工具结构
- 支持多个巡检接口独立轮询
- 支持请求头和请求参数变量替换，例如 `${token}`
- 支持 GET、POST 等 HTTP 方法
- 支持成功判断：`status=200`、`code=0`、`data.count>=1`
- 每个接口按 xlsx 的 `轮询间隔秒` 巡检，生产建议 `3600`
- 已告警接口按 xlsx 的 `异常后轮询间隔秒` 额外巡检，生产建议 `600`
- 单次请求按 xlsx 的 `超时时间ms` 判断，生产建议 `5000`
- 单轮巡检失败后立即重试，最多请求 3 次
- 同一轮 3 次都失败后，发送企业微信群通知
- 已告警接口恢复成功后，发送恢复通知
- 程序启动后发送一次启动通知
- 单次执行完成后发送一条执行报告到企业微信
- 每天 18:00 发送前一天 18:00 至当天 18:00 的巡检日报
- 通知内容自动脱敏 token、ticket、cookie、手机号、身份证、长密钥等信息
- 支持 Docker 部署

## 告警规则

固定规则：

- 每个接口按 xlsx 的 `轮询间隔秒` 执行一轮巡检
- 一轮巡检内，第 1 次失败后立即重试
- 最多请求 3 次
- 任意一次成功，本轮判定成功，不通知
- 3 次全部失败，本轮判定失败，发送企业微信群异常通知
- 已通知异常后，这个异常接口会按 `异常后轮询间隔秒` 单独巡检，直到恢复
- 异常后单独巡检不影响正常 `轮询间隔秒` 的下一轮巡检时间
- 已通知异常后，如果后续巡检成功，发送恢复通知
- 已经处于异常状态时，后续继续失败不重复刷屏；恢复后再次失败才重新通知
- 单次请求超过 xlsx 的 `超时时间ms`，按失败处理。生产建议填写 `5000`
- 程序启动后，会向所有已配置通知组发送一次启动通知
- 每天 18:00 会向所有已配置通知组发送巡检日报，统计周期为前一天 18:00:00 至当天 18:00:00
- 巡检日报包含巡检次数、成功次数、失败次数、成功率、平均响应时间、最大响应时间和失败接口摘要

## xlsx 配置

配置文件默认路径：

```bash
config/巡检配置.xlsx
```

仓库内提供脱敏示例模板：

```bash
config/巡检配置_示例.xlsx
```

实际使用时可以复制一份并改名为 `config/巡检配置.xlsx`，再填写真实接口和企业微信 webhook。真实配置文件不会提交到 git。

生成模板：

```bash
python main.py init-config
```

### 巡检接口

| 列名 | 说明 |
|---|---|
| 是否启用 | `是` 执行，`否` 跳过 |
| 场景名称 | 业务场景，例如会员首页巡检 |
| 接口名称 | 接口中文名 |
| 请求方式 | GET、POST 等 |
| URL | 完整接口地址，支持 `${变量}` |
| 请求头JSON | JSON 对象，例如 `{"Authorization":"Bearer ${token}"}` |
| 请求参数 | JSON、`key=value&key2=value2` 或 `无` |
| 成功判断 | 支持多条件，用英文分号隔开，例如 `status=200; code=0` |
| 轮询间隔秒 | 两轮巡检之间的间隔，单位秒。1 小时填写 `3600` |
| 异常后轮询间隔秒 | 接口已告警后额外恢复巡检间隔，单位秒。10 分钟填写 `600` |
| 超时时间ms | 单次请求超时时间，单位毫秒。5 秒填写 `5000` |
| 通知组 | 对应“通知配置”sheet |

### 前置变量

| 列名 | 说明 |
|---|---|
| 变量名 | 例如 `token` |
| 变量值 | 实际变量值 |
| 是否敏感 | `是` 表示日志和通知中需要脱敏 |
| 说明 | 备注 |

注意：真实 token、ticket、cookie 不要提交到 git。项目已默认忽略 `*.xlsx`。

### 通知配置

| 列名 | 说明 |
|---|---|
| 通知组 | 与巡检接口中的通知组对应 |
| 企业微信Webhook | 企业微信群机器人 webhook |
| 是否@所有人 | `是` 则通知时 @all |
| 备注 | 说明 |

## 本地运行

安装依赖：

```bash
pip install -r requirements.txt
```

生成配置模板：

```bash
python main.py init-config
```

只执行一轮，用于验证配置，执行完成后会向所有已配置通知组发送单次执行报告：

```bash
python main.py run --once
```

代码里也保留了单次执行入口，便于后续脚本直接调用：

```python
from pathlib import Path
from inspector.config_loader import load_config
from inspector.runner import run_once_inspection
from inspector.stats import StatsRecorder

config = load_config(Path("config/巡检配置.xlsx"))
report = run_once_inspection(config, StatsRecorder(Path("logs/inspection_stats.jsonl")))
```

常驻轮询：

```bash
python main.py run
```

默认统计文件：

```bash
logs/inspection_stats.jsonl
```

如果需要指定统计文件：

```bash
python main.py run --stats-file logs/inspection_stats.jsonl
```

如果在 PyCharm 里直接运行 `main.py`，不填写任何参数，默认等同于：

```bash
python main.py run
```

## Docker 部署

先在本地生成配置：

```bash
python main.py init-config
```

编辑 `config/巡检配置.xlsx`，填入真实接口和企业微信 webhook。

启动：

```bash
docker compose up -d --build
```

`docker-compose.yml` 已配置：

```yaml
restart: always
```

如果容器已经存在，也可以直接启动：

```bash
docker start polling-inspector
```

如果需要给已存在容器补上开机自启策略：

```bash
docker update --restart=always polling-inspector
```

查看日志：

```bash
docker compose logs -f
```

日志同时会保存到宿主机：

```bash
logs/inspection.log
logs/inspection_stats.jsonl
```

文件日志按天轮转，保留最近 7 天日志；统计文件用于每天 18:00 生成巡检日报。

### 使用 docker 命令映射指定 xlsx

如果不用 `docker compose`，也可以直接用 `docker run` 映射某一个 xlsx 文件。容器内固定读取：

```bash
/app/config/巡检配置.xlsx
```

所以宿主机上的任意配置文件，都映射到这个容器路径即可：

```bash
CONFIG_FILE="$(pwd)/config/巡检配置.xlsx"
LOG_DIR="$(pwd)/logs"

mkdir -p "$LOG_DIR"

docker build -t polling-inspector:latest .

docker rm -f polling-inspector 2>/dev/null || true

docker run -d \
  --name polling-inspector \
  --restart=always \
  -e TZ=Asia/Shanghai \
  -v "$CONFIG_FILE:/app/config/巡检配置.xlsx:ro" \
  -v "$LOG_DIR:/app/logs" \
  polling-inspector:latest
```

如果只是修改了同一个 xlsx 文件里的内容，保存后重启容器即可：

```bash
docker restart polling-inspector
```

如果要更换成另一个 xlsx 文件路径，需要重新创建容器，把新的文件路径映射进去：

```bash
CONFIG_FILE="/path/to/your/巡检配置.xlsx"
LOG_DIR="$(pwd)/logs"

mkdir -p "$LOG_DIR"

docker rm -f polling-inspector

docker run -d \
  --name polling-inspector \
  --restart=always \
  -e TZ=Asia/Shanghai \
  -v "$CONFIG_FILE:/app/config/巡检配置.xlsx:ro" \
  -v "$LOG_DIR:/app/logs" \
  polling-inspector:latest
```

停止：

```bash
docker compose down
```

## 企业微信群通知内容

异常通知包含：

- 场景名称
- 接口名称
- 异常时间
- 连续失败次数
- HTTP 状态
- 响应时间
- 异常原因
- 请求方式
- 请求地址
- 请求参数
- 响应摘要

恢复通知包含：

- 场景名称
- 接口名称
- 恢复时间
- HTTP 状态
- 响应时间
- 请求地址

启动通知包含：

- 启动接口数
- 日报发送时间
- 日报统计周期

单次执行报告包含：

- 开始时间
- 结束时间
- 巡检接口数
- 成功接口数
- 失败接口数
- 成功率
- 平均响应时间
- 最大响应时间
- 失败明细

日报通知包含：

- 统计周期
- 巡检次数
- 成功次数
- 失败次数
- 成功率
- 平均响应时间
- 最大响应时间
- 失败接口摘要

## 安全规则

- 不上传 `config/巡检配置.xlsx`
- 不上传任何真实 token、cookie、ticket、手机号、身份证、生产接口密钥
- 通知和日志会做脱敏，但配置文件本身仍应当视为敏感文件
- 企业微信 webhook 属于敏感配置，不要提交到 git

## 验证

```bash
python -m unittest
```
