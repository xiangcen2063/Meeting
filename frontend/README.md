# 会面地点推荐 - 前端

基于 React + TypeScript + Vite 构建的语音交互前端应用。

## 功能

- 麦克风录音：录制用户描述双方位置的语音
- 音频预览：录音完成后可预览、重录或发送
- 响应播放：自动播放后端返回的语音回答

## 启动步骤

1. 安装依赖：

```bash
npm install
```

2. 启动开发服务器：

```bash
npm run dev
```

前端将运行在 http://localhost:5177

## 配置

- 前端端口：5177（在 `vite.config.ts` 中配置）
- 后端代理：所有 `/api` 请求将被代理到 `http://localhost:8013`

## API 接口

前端调用后端接口：

- `POST /api/meeting/recommend`
  - 请求：`multipart/form-data`，包含 `audio` 字段（音频文件）
  - 响应：`{ success, textResponse?, audioUrl?, error? }`
