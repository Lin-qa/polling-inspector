# 轮询巡检工具

一个独立的接口巡检工具，按 xlsx 配置持续轮询接口，并通过企业微信群机器人通知异常和恢复。

## 第一版功能

- xlsx 配置驱动，不依赖压测工具结构
- 支持多个巡检接口独立轮询
- 支持请求头和请求参数变量替换，例如 `${token}`
- 支持 GET、POST 等 HTTP 方法
- 支持成功判断：`status=200`、`code=0`、`data.count>=1`
- 每个接口按 xlsx 的 `轮询间隔ms` 巡检，生产建议 `3600000`
- 单次请求按 xlsx 的 `超时时间ms` 判断，生产建议 `5000`
- 单轮巡检失败后立即重试，最多请求 3 次
- 同一轮 3 次都失败后，发送企业微信群通知
- 已告警接口恢复成功后，发送恢复通知
- 通知内容自动脱敏 token、ticket、cookie、手机号、身份证、长密钥等信息
- 支持 Docker 部署

## 告警规则

固定规则：

- 每个接口按 xlsx 的 `轮询间隔ms` 执行一轮巡检
- 一轮巡检内，第 1 次失败后立即重试
- 最多请求 3 次
- 任意一次成功，本轮判定成功，不通知
- 3 次全部失败，本轮判定失败，发送企业微信群异常通知
- 已通知异常后，如果后续某一轮巡检成功，发送恢复通知
- 已经处于异常状态时，后续继续失败不重复刷屏；恢复后再次失败才重新通知
- 单次请求超过 xlsx 的 `超时时间ms`，按失败处理。生产建议填写 `5000`

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
| 轮询间隔ms | 两轮巡检之间的间隔，单位毫秒。1 小时填写 `3600000` |
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

只执行一轮，用于验证配置：

```bash
python main.py run --once
```

常驻轮询：

```bash
python main.py run
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

查看日志：

```bash
docker compose logs -f
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

## 安全规则

- 不上传 `config/巡检配置.xlsx`
- 不上传任何真实 token、cookie、ticket、手机号、身份证、生产接口密钥
- 通知和日志会做脱敏，但配置文件本身仍应当视为敏感文件
- 企业微信 webhook 属于敏感配置，不要提交到 git

## 验证

```bash
python -m unittest
```
