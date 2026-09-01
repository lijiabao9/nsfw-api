# NSFW 图像检测 HTTP API

基于深度学习的色情/成人内容图像检测服务，提供 REST API 接口。

## 项目简介

本项目提供一个开箱即用的 REST API 服务，用于判断图片是否包含不适宜工作（NSFW）的成人内容。服务基于深度神经网络模型，返回 0~1 之间的置信度分数，分数越高表示包含成人内容的可能性越大。

### 参考项目

本项目基于以下两个开源项目构建：

- **[open_nsfw](https://github.com/yahoo/open_nsfw)**：Yahoo 开源的 NSFW 图像分类 Caffe 模型，提供预训练的 ResNet-50 架构神经网络。
- **[nsfw_api](https://github.com/EugenCepoi/nsfw_api)**：将 open_nsfw 封装为 REST API 的 Web 服务，提供单张和批量图片检测接口。

本项目在以上两个项目的基础上，进行了 **ARM 架构适配**（如 Oracle ARM 服务器）和 **Python 3 兼容性改造**，支持在 ARM64 平台上部署运行。

## 功能特性

- **单张图片检测**：通过 GET 请求传入图片 URL，实时返回检测分数
- **批量图片检测**：通过 POST 请求传入多张图片 URL，支持流式返回结果
- **健康检查**：提供 `/health` 端点用于监控服务状态
- **简单鉴权**：所有业务接口均需携带 `key` 参数，可通过环境变量 `API_KEY` 配置（除非配置关闭鉴权时可不传）
- **ARM 架构支持**：适配 ARM64 平台（如 Oracle ARM 实例）
- **Docker 容器化部署**：一键构建和启动，便于生产环境部署
- **流式响应**：批量接口支持流式输出，可边处理边返回结果

## 系统要求

- Docker（推荐）或 Python 3.11+ 环境
- ARM64 或 x86_64 架构

## 快速开始

### 使用 Docker 部署

#### 1. 克隆项目

```bash
git clone https://github.com/lijiabao9/nsfw-api
cd nsfw-api
```

#### 2. 构建 Docker 镜像

```bash
docker build -t nsfw_api:latest .
```

#### 3. 启动服务（需设置 API_KEY 环境变量）

```bash
docker run -d -p 5000:5000 \
  -e TZ=Asia/Shanghai \
  -e API_KEY=your_secret_key \
  --name nsfw_api \
  nsfw_api:latest
```

服务启动后，API 端点地址为：`http://<服务器IP>:5000`

### 使用 docker-compose（推荐）

```bash
docker-compose up -d
```

默认会在 `5000` 端口启动服务，并配置好时区和 API_KEY（见 `docker-compose.yml`）。

### 目录结构

```
nsfw-api/
├── Dockerfile              # Docker 构建文件（ARM 适配）
├── docker-compose.yml      # Docker Compose 编排文件
├── requirements.txt        # Python 依赖
├── open_nsfw/              # open_nsfw 模型和脚本
│   ├── classify_nsfw.py    # NSFW 分类核心脚本（Python 3 适配）
│   └── nsfw_model/         # 预训练模型文件
│       ├── deploy.prototxt
│       └── resnet_50_1by2_nsfw.caffemodel
└── web/
    └── app.py              # Flask API 服务（Python 3 适配）
```

## API 接口说明

> **鉴权说明**：除 `/health` 外，所有业务接口均需在 URL 查询参数中携带 `key` 字段，其值需与服务器环境变量 `API_KEY` 一致，否则返回 `401` 错误。
> 若设置 `AUTH_ENABLE=false`（不区分大小写）可关闭鉴权（仅建议在内部测试环境使用）。

### 0. 健康检查

**端点**：`GET /health`

无需鉴权，用于检查服务是否运行正常。

**请求示例**：

```bash
curl http://localhost:5000/health
```

**响应示例**：

```json
{
  "status": "UP",
  "time": "2026-09-02 10:30:45"
}
```

---

### 1. 单张图片检测

**端点**：`GET /`

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | 是 | 图片的 URL 地址（支持 HTTP/HTTPS） |
| `key` | string | 是 | API 密钥 |

**请求示例**：

```bash
curl "http://localhost:5000/?url=https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png&key=your_secret_key"
```

**响应示例（成功）**：

```json
{
  "score": 0.00015177072782535106,
  "url": "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png"
}
```

**响应示例（鉴权失败）**：

```json
{"error": "Invalid API key"}
```

**响应示例（下载失败）**：

```json
{
  "error_code": 500,
  "error_reason": "Name or service not known",
  "url": "https://invalid-domain.example/image.jpg"
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `score` | float | NSFW 置信度分数，范围 0~1。分数 < 0.2 表示安全，> 0.8 表示高度可能为 NSFW |
| `error_code` | int | 错误码（仅在失败时返回） |
| `error_reason` | string | 错误原因描述（仅在失败时返回） |

---

### 2. 批量图片检测

**端点**：`POST /batch-classify`

**请求头**：`Content-Type: application/json`

**请求体格式**：

支持两种输入格式，**均需在 URL 中附带 `key` 参数**。

**格式一（推荐，支持附加字段）**：

```json
{
  "images": [
    {"url": "https://example.com/image1.jpg", "id": 1, "extra_props": {"foo": "bar"}},
    {"url": "https://example.com/image2.jpg", "id": 2}
  ]
}
```

**格式二（简写）**：

```json
{
  "urls": ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
}
```

**请求示例**：

```bash
curl -X POST -H 'Content-Type: application/json' \
  -d '{
    "images": [
      {"url": "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png", "id": 1},
      {"url": "https://example.com/nsfw_image.jpg", "id": 2}
    ]
  }' \
  "http://localhost:5000/batch-classify?key=your_secret_key"
```

**响应示例**：

```json
{"predictions": [
    {"url": "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png", "score": 0.00015177072782535106, "id": 1},
    {"url": "https://example.com/nsfw_image.jpg", "score": 0.923456789, "id": 2}
]}
```

**响应说明**：

- 响应以流式 JSON 格式返回（Server-Sent Events 风格）
- 每个条目的响应包含原始请求中的所有附加字段（如 `id`、`extra_props` 等）
- 如果某张图片处理失败，该条目返回 `error_code` 和 `error_reason`，不影响其他图片的处理
- 响应格式为 `{"predictions": [ ... ]}`，每个预测结果占一行

---

## 配置说明

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `API_KEY` | 用于鉴权的密钥 | `default_api_key_please_change`（强烈建议修改） |
| `AUTH_ENABLE` | 是否开启接口鉴权。只有明确设置为 `false`（不区分大小写）时才关闭鉴权，其他值（包括未设置）均视为开启 | `True`（即开启） |
| `TZ` | 时区，如 `Asia/Shanghai` | 无（默认 UTC） |
| `PORT` | 服务监听端口 | `5000` |

## 注意事项

1. **性能考虑**：图像分类为计算密集型操作，单次请求耗时较长（通常几百毫秒到数秒），不适合实时低延迟场景。建议通过批量接口异步处理。

2. **阈值选择**：分数 < 0.2 表示图片很可能安全，分数 > 0.8 表示高度可能为 NSFW。中间范围的分数可根据具体业务场景选择合适的阈值。

3. **模型局限性**：该模型仅针对色情图片训练，不适用于检测暴力、血腥、卡通或文字等其他类型的 NSFW 内容。

4. **准确率**：本项目不保证 100% 准确率，建议结合人工审核处理边界情况。
