# 会面地点推荐 - 后端

基于 FastAPI 构建的语音处理后端服务。

## 功能

- ✅ 接收前端上传的音频文件
- ✅ 保存音频到 Storage 目录
- ✅ **ASR 语音识别**（百炼 Qwen3-ASR-Flash）
- ✅ **槽位提取**（Deepseek 提取地址信息）
- ✅ **会面地点推荐**（高德 MCP 服务）
- ⏳ TTS 语音合成（待实现）

## 技术架构

```
前端录音 → 后端API
         ↓
    保存音频文件
         ↓
    百炼 ASR 识别语音
         ↓
    Deepseek 提取地址槽位
         ↓
    高德 MCP 计算会面地点
         ↓
    (TTS 生成语音回复)
         ↓
    返回推荐结果
```

## 启动步骤

1. 创建虚拟环境（推荐）：

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 配置环境变量：

```bash
cp .env.example .env
# 编辑 .env 文件，填入实际的 API Key
```

4. 启动服务：

```bash
python main.py
```

服务将运行在 http://localhost:8013

## API 接口

### POST /api/meeting/recommend

接收音频文件，返回会面地点推荐。

**请求：**
- Content-Type: `multipart/form-data`
- Body: `audio` 字段包含音频文件

**响应：**
```json
{
  "success": true,
  "textResponse": "会面地点推荐信息...",
  "audioUrl": "音频回复的URL（待实现）",
  "error": null
}
```

### GET /api/health

健康检查接口。

## 配置说明

所有配置在 `.env` 文件中：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| SERVER_HOST | 服务监听地址 | 0.0.0.0 |
| SERVER_PORT | 服务端口 | 8013 |
| STORAGE_DIR | 运行文件与调用日志存储目录 | Storage |
| DASHSCOPE_API_KEY | 阿里云百炼 API Key | - |
| DEEPSEEK_API_KEY | Deepseek API Key | - |
| AMAP_API_KEY | 高德地图 API Key | - |
| AMAP_MCP_URL | 高德 MCP URL（可选） | - |

## 日志与调试

### 中文彩色日志

服务运行时会输出彩色的中文日志，便于跟踪：

```
[14:30:15] [信息] [ASR] 开始语音识别
[14:30:16] [成功] [ASR] 识别文本: 我在望京，我朋友在国贸
[14:30:17] [信息] [Deepseek] 槽位提取成功
[14:30:18] [信息] [高德MCP] 会面地点推荐完成
```

### Storage 目录结构

每次请求会按日期和请求 ID 整理到独立文件夹，便于按时间查看：

```
Storage/
└── 20260517/
    ├── service_20260517.log                         # 当天服务日志
    └── req_20260517_143015_abc123/
        ├── audio_20260517_143015_def45678.webm      # 原始音频
        ├── audio_20260517_143015_def45678_asr.json  # ASR识别结果
        ├── req_20260517_143015_abc123_slot.json     # 槽位提取结果
        ├── req_20260517_143015_abc123_mcp.json      # MCP调用日志
        └── req_20260517_143015_abc123_tts.json      # TTS合成结果
```

### MCP 调用日志格式

`*_mcp.json` 文件包含完整的 MCP 调用链路：

```json
{
  "request_id": "req_20260517_143015_abc123",
  "mcp_url_host": "https://mcp.amap.com/mcp",
  "mcp_enabled": true,
  "started_at": "2026-05-17T14:30:17.123456",
  "steps": [
    {
      "name": "initialize",
      "success": true,
      "error": null
    },
    {
      "name": "list_tools",
      "success": true,
      "tools": ["maps_geo", "maps_distance", ...],
      "raw_preview": {"count": 15}
    },
    {
      "name": "call_tool",
      "tool": "maps_geo",
      "arguments_preview": {"address": "望京", "city": "北京"},
      "success": true,
      "raw_preview": {"content_count": 1}
    }
  ],
  "normalized_result": {
    "meeting_point": "...",
    "distance": 5000.0,
    "location1": {...},
    "location2": {...}
  },
  "fallback_used": false,
  "fallback_reason": "",
  "finished_at": "2026-05-17T14:30:18.456789"
}
```

## 项目结构

```
backend/
├── config.py                      # 配置加载
├── main.py                        # FastAPI 主应用
├── requirements.txt               # Python 依赖
├── .env                           # 环境配置（实际使用）
├── .env.example                   # 环境配置模板
├── services/                      # 服务模块
│   ├── __init__.py
│   ├── asr_service.py            # 百炼 ASR 服务
│   ├── deepseek_service.py       # Deepseek 槽位提取
│   └── amap_mcp_service.py       # 高德 MCP 客户端
└── utils/                         # 工具模块
    ├── __init__.py
    └── logger.py                  # 中文日志系统
```

## 开发规范

### MCP 服务规范

按照 `.cursor/skills/amap-mcp-service/SKILL.md` 中的规范：

1. 使用远端 Streamable HTTP MCP
2. 必须先 `list_tools()` 再调用工具
3. 完整记录 MCP 调用链路
4. 不泄露 API Key
5. 结果解析兼容多种返回格式

### 日志规范

- 使用中文日志便于阅读
- 关键步骤使用 `logger.step()` 标记
- 成功/失败使用不同颜色
- 详细日志保存到 Storage 目录

## 故障排查

### ASR 识别失败

- 检查 `DASHSCOPE_API_KEY` 是否正确
- 查看 `*_asr.json` 文件中的错误信息
- 确认音频格式支持（webm/mp3/wav）

### Deepseek 槽位提取失败

- 检查 `DEEPSEEK_API_KEY` 是否正确
- 查看 `*_slot.json` 文件中的原始文本
- 确认语音识别结果是否包含地址信息

### MCP 调用失败

- 检查 `AMAP_API_KEY` 是否正确
- 查看 `*_mcp.json` 文件定位失败步骤
- 确认网络连接正常
- 检查代理设置是否已清除
