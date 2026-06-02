"""
阿里云百炼平台 TTS 语音合成服务

使用 Qwen3-TTS-Flash 模型，将文本转换为语音
"""

import os
from dataclasses import dataclass
from pathlib import Path

import httpx

import config
from utils.logger import logger, save_json_log


@dataclass
class TTSResult:
    """TTS 合成结果"""
    success: bool
    audio_url: str = ""
    text: str = ""
    voice: str = ""
    error: str = ""


class TTSService:
    """阿里云百炼 TTS 服务"""
    
    API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    MODEL = "qwen3-tts-flash"
    
    def __init__(self):
        # 清除代理设置
        for var in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']:
            if var in os.environ:
                del os.environ[var]
        
        self.api_key = config.DASHSCOPE_API_KEY
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY 未配置")
        logger.info("TTS", "服务初始化成功")
    
    def synthesize(
        self,
        text: str,
        voice: str = "Cherry",
        language_type: str = "Chinese"
    ) -> TTSResult:
        """
        文本转语音
        
        Args:
            text: 要合成的文本
            voice: 音色 (Cherry/Stella/Emily/Richard等)
            language_type: 语言类型 (Chinese/English)
            
        Returns:
            TTSResult 合成结果
        """
        logger.info("TTS", f"开始语音合成")
        logger.debug("TTS", f"文本: {text[:50]}...")
        logger.debug("TTS", f"音色: {voice}")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.MODEL,
            "input": {
                "text": text,
                "voice": voice,
                "language_type": language_type
            }
        }
        
        # 尝试最多 2 次
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.warning("TTS", f"重试第 {attempt} 次...")
                
                with httpx.Client(
                    timeout=60.0,
                    http2=False,
                    verify=True,
                    follow_redirects=True
                ) as client:
                    response = client.post(
                        self.API_URL,
                        headers=headers,
                        json=payload
                    )
                
                if response.status_code != 200:
                    error_msg = f"TTS API 请求失败: HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_msg = f"{error_msg} - {error_data['message']}"
                    except Exception:
                        error_msg = f"{error_msg} - {response.text}"
                    
                    logger.error("TTS", error_msg)
                    return TTSResult(success=False, text=text, error=error_msg)
                
                result = response.json()
                
                # 提取音频 URL
                audio_url = result.get("output", {}).get("audio", {}).get("url", "")
                
                if not audio_url:
                    error_msg = "TTS 返回结果中没有音频 URL"
                    logger.error("TTS", error_msg)
                    return TTSResult(success=False, text=text, error=error_msg)
                
                logger.success("TTS", f"语音合成成功")
                logger.info("TTS", f"  音频URL: {audio_url[:50]}...")
                logger.info("TTS", f"  文本长度: {len(text)} 字符")
                
                return TTSResult(
                    success=True,
                    audio_url=audio_url,
                    text=text,
                    voice=voice
                )
                
            except httpx.TimeoutException:
                last_error = "TTS API 请求超时"
                logger.warning("TTS", last_error)
                if attempt < max_retries - 1:
                    continue
            except httpx.RequestError as e:
                last_error = f"TTS API 请求错误: {str(e)}"
                logger.warning("TTS", last_error)
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)
                    continue
            except Exception as e:
                last_error = f"TTS 处理异常: {str(e)}"
                logger.warning("TTS", last_error)
                if attempt < max_retries - 1:
                    continue
        
        # 所有重试都失败
        logger.error("TTS", f"经过 {max_retries} 次重试后仍然失败: {last_error}")
        return TTSResult(success=False, text=text, error=last_error)


def save_tts_result(result: TTSResult, request_id: str, storage_dir: Path) -> Path:
    """
    保存 TTS 合成结果
    
    Args:
        result: TTS 合成结果
        request_id: 请求ID
        storage_dir: 存储目录
        
    Returns:
        保存的文件路径
    """
    filename = f"{request_id}_tts.json"
    
    data = {
        "request_id": request_id,
        "success": result.success,
        "text": result.text,
        "voice": result.voice,
        "audio_url": result.audio_url,
        "error": result.error
    }
    
    return save_json_log(data, filename, storage_dir)
