import os
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
from services.asr_service import ASRService, save_asr_result, clear_proxy_env_vars
from services.deepseek_service import DeepseekService, save_slot_result
from services.amap_mcp_service import AmapMCPClient
from services.tts_service import TTSService, save_tts_result
from utils.logger import logger

clear_proxy_env_vars()

app = FastAPI(
    title="会面地点推荐服务",
    description="语音驱动的会面地点推荐 API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

asr_service: ASRService | None = None
deepseek_service: DeepseekService | None = None
amap_mcp_client: AmapMCPClient | None = None
tts_service: TTSService | None = None


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化服务"""
    global asr_service, deepseek_service, amap_mcp_client, tts_service
    
    clear_proxy_env_vars()
    logger.section("服务初始化")
    
    # 初始化 ASR 服务
    try:
        asr_service = ASRService()
        logger.success("启动", "ASR 服务已就绪")
    except ValueError as e:
        logger.warning("启动", f"ASR 服务初始化失败: {e}")
    
    # 初始化 Deepseek 服务
    try:
        deepseek_service = DeepseekService()
        logger.success("启动", "Deepseek 服务已就绪")
    except ValueError as e:
        logger.warning("启动", f"Deepseek 服务初始化失败: {e}")
    
    # 初始化高德 MCP 客户端
    try:
        amap_mcp_client = AmapMCPClient()
        logger.success("启动", "高德 MCP 客户端已就绪")
    except ValueError as e:
        logger.warning("启动", f"高德 MCP 客户端初始化失败: {e}")
    
    # 初始化 TTS 服务
    try:
        tts_service = TTSService()
        logger.success("启动", "TTS 服务已就绪")
    except ValueError as e:
        logger.warning("启动", f"TTS 服务初始化失败: {e}")
    
    logger.info("启动", f"服务运行在 http://{config.SERVER_HOST}:{config.SERVER_PORT}")


class MeetingResponse(BaseModel):
    success: bool
    textResponse: str | None = None
    audioUrl: str | None = None
    error: str | None = None
    slots: dict[str, str] | None = None


class TextMeetingRequest(BaseModel):
    text: str


def generate_filename(original_filename: str) -> str:
    """生成唯一的文件名"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    ext = Path(original_filename).suffix or ".webm"
    return f"audio_{timestamp}_{unique_id}{ext}"


def generate_request_id() -> str:
    """生成请求ID"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return f"req_{timestamp}_{unique_id}"


def get_request_storage_dir(request_id: str) -> Path:
    """按日期和请求 ID 创建本次请求的存储目录。"""
    parts = request_id.split("_")
    date_part = parts[1] if len(parts) >= 3 else datetime.now().strftime("%Y%m%d")
    request_dir = config.STORAGE_DIR / date_part / request_id
    request_dir.mkdir(parents=True, exist_ok=True)
    return request_dir


def get_storage_display_path(path: Path) -> str:
    """返回便于日志和前端文本展示的 Storage 相对路径。"""
    try:
        return str(path.relative_to(config.STORAGE_DIR))
    except ValueError:
        return str(path)


async def process_location_text(
    recognized_text: str,
    request_id: str,
    source_label: str,
    request_storage_dir: Path,
    asr_log_path: Path | None = None
) -> MeetingResponse:
    """根据一段位置描述文本完成推荐流程。"""
    # ========== 步骤 3: Deepseek 槽位提取 ==========
    if deepseek_service is None:
        return MeetingResponse(
            success=False,
            error="Deepseek 服务未初始化，请检查 DEEPSEEK_API_KEY 配置"
        )

    logger.step(3, 6, "槽位提取 (Deepseek)")
    slot_result = deepseek_service.extract_locations(recognized_text)

    slot_json_path = save_slot_result(slot_result, request_id, request_storage_dir)
    logger.info("槽位", f"结果已保存: {get_storage_display_path(slot_json_path)}")

    if not slot_result.success:
        return MeetingResponse(
            success=False,
            error=f"槽位提取失败: {slot_result.error}"
        )

    if not slot_result.location1 or not slot_result.location2:
        return MeetingResponse(
            success=False,
            error="未能从描述中提取到两个有效的地址位置"
        )

    # ========== 步骤 4: 高德 MCP 会面地点推荐 ==========
    if amap_mcp_client is None:
        return MeetingResponse(
            success=False,
            error="高德 MCP 客户端未初始化，请检查 AMAP_API_KEY 配置"
        )

    logger.step(4, 6, "会面地点推荐 (高德 MCP)")

    meeting_result = await amap_mcp_client.find_meeting_point(
        location1=slot_result.location1,
        location2=slot_result.location2,
        city=slot_result.city,
        request_id=request_id
    )

    mcp_json_path = amap_mcp_client.save_mcp_log(request_storage_dir)
    logger.info("MCP", f"调用日志已保存: {get_storage_display_path(mcp_json_path)}")

    if not meeting_result.success:
        return MeetingResponse(
            success=False,
            error=f"会面地点推荐失败: {meeting_result.error}"
        )

    # ========== 步骤 5: Deepseek 生成自然语言回复 ==========
    logger.step(5, 6, "生成自然语言回复 (Deepseek)")

    recommended_places = []
    mcp_log_path = request_storage_dir / f"{request_id}_mcp.json"
    if mcp_log_path.exists():
        import json
        with open(mcp_log_path, 'r', encoding='utf-8') as f:
            mcp_data = json.load(f)
            recommended_places = mcp_data.get("normalized_result", {}).get("recommended_places", [])

    natural_response = deepseek_service.generate_response(
        location1=slot_result.location1,
        location2=slot_result.location2,
        meeting_places=recommended_places,
        distance=meeting_result.distance
    )

    logger.success("回复生成", f"自然语言回复: {natural_response[:50]}...")

    # ========== 步骤 6: TTS 语音合成 ==========
    tts_json_path = None
    if tts_service is None:
        logger.warning("TTS", "TTS 服务未初始化，跳过语音合成")
        audio_url = None
    else:
        logger.step(6, 6, "语音合成 (TTS)")

        tts_result = tts_service.synthesize(
            text=natural_response,
            voice="Cherry",
            language_type="Chinese"
        )

        tts_json_path = save_tts_result(tts_result, request_id, request_storage_dir)
        logger.info("TTS", f"结果已保存: {get_storage_display_path(tts_json_path)}")

        if not tts_result.success:
            logger.warning("TTS", f"语音合成失败: {tts_result.error}")
            audio_url = None
        else:
            audio_url = tts_result.audio_url
            logger.success("TTS", "语音合成成功")

    response_text = f"""🎯 会面地点推荐

📍 位置信息：
  你的位置: {meeting_result.location1_info.formatted_address if meeting_result.location1_info else slot_result.location1}
  朋友位置: {meeting_result.location2_info.formatted_address if meeting_result.location2_info else slot_result.location2}

✨ 推荐方案：
{natural_response}

📊 详细信息已保存到 Storage 目录
  - 请求目录: {get_storage_display_path(request_storage_dir)}
  - 输入来源: {source_label}
  - 语音识别: {get_storage_display_path(asr_log_path) if asr_log_path else 'N/A'}
  - 槽位提取: {get_storage_display_path(slot_json_path)}
  - MCP调用: {get_storage_display_path(mcp_json_path)}
  - TTS合成: {get_storage_display_path(tts_json_path) if tts_json_path else 'N/A'}
"""

    logger.success("完成", "会面地点推荐成功")
    logger.info("结果", f"\n{response_text}")

    return MeetingResponse(
        success=True,
        textResponse=response_text,
        audioUrl=audio_url,
        error=None,
        slots={
            "location1": slot_result.location1,
            "location2": slot_result.location2,
            "city": slot_result.city,
            "location1Formatted": meeting_result.location1_info.formatted_address if meeting_result.location1_info else "",
            "location2Formatted": meeting_result.location2_info.formatted_address if meeting_result.location2_info else "",
        }
    )


@app.get("/")
async def root():
    return {"message": "会面地点推荐服务运行中", "version": "1.0.0"}


@app.post("/api/meeting/recommend", response_model=MeetingResponse)
async def recommend_meeting_point(audio: UploadFile = File(...)):
    """
    接收音频文件，处理后返回会面地点推荐
    
    完整处理流程:
    1. 保存音频文件到 Storage 目录
    2. 调用百炼 ASR 服务识别语音
    3. 调用 Deepseek 提取地址槽位
    4. 调用高德 MCP 服务计算会面地点
    5. 调用 Deepseek 生成自然语言回复
    6. 调用百炼 TTS 服务生成语音
    """
    request_id = generate_request_id()
    request_storage_dir = get_request_storage_dir(request_id)
    
    logger.section(f"新请求: {request_id}")
    
    try:
        # ========== 步骤 1: 保存音频 ==========
        if not audio.filename:
            raise HTTPException(status_code=400, detail="未提供音频文件")
        
        logger.step(1, 4, "保存音频文件")
        filename = generate_filename(audio.filename)
        file_path = request_storage_dir / filename
        
        content = await audio.read()
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        
        file_size_kb = len(content) / 1024
        logger.success("音频", f"已保存: {get_storage_display_path(file_path)} ({file_size_kb:.1f} KB)")
        
        # ========== 步骤 2: ASR 语音识别 ==========
        if asr_service is None:
            return MeetingResponse(
                success=False,
                error="ASR 服务未初始化，请检查 DASHSCOPE_API_KEY 配置"
            )
        
        logger.step(2, 4, "语音识别 (ASR)")
        asr_result = asr_service.recognize_from_file(file_path, language="zh")
        
        asr_json_path = save_asr_result(asr_result, filename, request_storage_dir)
        logger.info("ASR", f"结果已保存: {get_storage_display_path(asr_json_path)}")
        
        if not asr_result.success:
            return MeetingResponse(
                success=False,
                error=f"语音识别失败: {asr_result.error}"
            )
        
        recognized_text = asr_result.text
        logger.success("ASR", f"识别文本: {recognized_text}")

        return await process_location_text(
            recognized_text=recognized_text,
            request_id=request_id,
            source_label="语音",
            request_storage_dir=request_storage_dir,
            asr_log_path=asr_json_path
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"处理请求时发生错误: {str(e)}"
        logger.error("错误", error_msg)
        return MeetingResponse(
            success=False,
            error=error_msg
        )


@app.post("/api/meeting/recommend-text", response_model=MeetingResponse)
async def recommend_meeting_point_by_text(payload: TextMeetingRequest):
    """
    接收文字位置描述，返回会面地点推荐。

    这个接口用于不方便访问麦克风的环境，例如 Codex 内置浏览器。
    """
    request_id = generate_request_id()
    request_storage_dir = get_request_storage_dir(request_id)
    logger.section(f"新文字请求: {request_id}")

    try:
        text = payload.text.strip()
        if not text:
            return MeetingResponse(
                success=False,
                error="请输入你和朋友的位置"
            )

        logger.step(1, 6, "接收文字描述")
        logger.info("文字输入", text)

        return await process_location_text(
            recognized_text=text,
            request_id=request_id,
            source_label="文字",
            request_storage_dir=request_storage_dir,
            asr_log_path=None
        )

    except Exception as e:
        error_msg = f"处理文字请求时发生错误: {str(e)}"
        logger.error("错误", error_msg)
        return MeetingResponse(
            success=False,
            error=error_msg
        )


@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "storage_dir": str(config.STORAGE_DIR),
        "storage_exists": config.STORAGE_DIR.exists(),
        "services": {
            "asr": "ready" if asr_service else "not initialized",
            "deepseek": "ready" if deepseek_service else "not initialized",
            "amap_mcp": "ready" if amap_mcp_client else "not initialized",
            "tts": "ready" if tts_service else "not initialized"
        }
    }


if __name__ == "__main__":
    import uvicorn
    clear_proxy_env_vars()
    
    # 设置日志文件
    today = datetime.now().strftime("%Y%m%d")
    log_file = config.STORAGE_DIR / today / f"service_{today}.log"
    logger.set_log_file(log_file)
    
    uvicorn.run(
        "main:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=config.SERVER_RELOAD
    )
