"""
阿里云百炼平台 ASR 语音识别服务

使用 Qwen3-ASR-Flash 模型，通过 HTTP 请求调用 OpenAI 兼容模式 API
"""

import os
import base64
import json
from pathlib import Path
from dataclasses import dataclass

import httpx

import config


def clear_proxy_env_vars():
    """清除所有代理相关的环境变量"""
    proxy_vars = [
        "http_proxy", "HTTP_PROXY",
        "https_proxy", "HTTPS_PROXY",
        "all_proxy", "ALL_PROXY",
        "no_proxy", "NO_PROXY",
        "ftp_proxy", "FTP_PROXY",
        "socks_proxy", "SOCKS_PROXY",
    ]
    for var in proxy_vars:
        if var in os.environ:
            del os.environ[var]


@dataclass
class ASRResult:
    """ASR 识别结果"""
    success: bool
    text: str = ""
    language: str = ""
    emotion: str = ""
    duration_seconds: int = 0
    error: str = ""


class ASRService:
    """阿里云百炼 ASR 服务"""

    API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    MODEL = "qwen3-asr-flash"

    def __init__(self):
        clear_proxy_env_vars()
        self.api_key = config.DASHSCOPE_API_KEY
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY 未配置")

    def _get_mime_type(self, file_path: Path) -> str:
        """根据文件扩展名获取 MIME 类型"""
        suffix = file_path.suffix.lower()
        mime_map = {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".webm": "audio/webm",
            ".ogg": "audio/ogg",
            ".m4a": "audio/mp4",
            ".flac": "audio/flac",
        }
        return mime_map.get(suffix, "audio/webm")

    def _encode_audio_to_base64(self, audio_path: Path) -> str:
        """将音频文件编码为 Base64 Data URI"""
        audio_bytes = audio_path.read_bytes()
        base64_str = base64.b64encode(audio_bytes).decode("utf-8")
        mime_type = self._get_mime_type(audio_path)
        return f"data:{mime_type};base64,{base64_str}"

    def _encode_audio_bytes_to_base64(self, audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
        """将音频字节编码为 Base64 Data URI"""
        base64_str = base64.b64encode(audio_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{base64_str}"

    def recognize_from_file(self, audio_path: Path, language: str = "zh") -> ASRResult:
        """
        从音频文件识别语音
        
        Args:
            audio_path: 音频文件路径
            language: 语种代码（zh/en/ja 等），默认中文
            
        Returns:
            ASRResult 识别结果
        """
        if not audio_path.exists():
            return ASRResult(success=False, error=f"音频文件不存在: {audio_path}")

        data_uri = self._encode_audio_to_base64(audio_path)
        return self._call_asr_api(data_uri, language)

    def recognize_from_bytes(self, audio_bytes: bytes, mime_type: str = "audio/webm", language: str = "zh") -> ASRResult:
        """
        从音频字节数据识别语音
        
        Args:
            audio_bytes: 音频字节数据
            mime_type: 音频 MIME 类型
            language: 语种代码
            
        Returns:
            ASRResult 识别结果
        """
        data_uri = self._encode_audio_bytes_to_base64(audio_bytes, mime_type)
        return self._call_asr_api(data_uri, language)

    def _call_asr_api(self, data_uri: str, language: str = "zh") -> ASRResult:
        """调用百炼 ASR API"""
        clear_proxy_env_vars()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": data_uri
                            }
                        }
                    ]
                }
            ],
            "stream": False,
            "asr_options": {
                "language": language,
                "enable_itn": True
            }
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload
                )

            if response.status_code != 200:
                error_msg = f"ASR API 请求失败: HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        error_msg = f"{error_msg} - {error_data['error'].get('message', '')}"
                except Exception:
                    error_msg = f"{error_msg} - {response.text}"
                return ASRResult(success=False, error=error_msg)

            result = response.json()
            
            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            
            annotations = message.get("annotations", [{}])
            audio_info = next((a for a in annotations if a.get("type") == "audio_info"), {})
            
            usage = result.get("usage", {})
            duration = usage.get("seconds", 0)

            return ASRResult(
                success=True,
                text=content,
                language=audio_info.get("language", language),
                emotion=audio_info.get("emotion", "neutral"),
                duration_seconds=duration
            )

        except httpx.TimeoutException:
            return ASRResult(success=False, error="ASR API 请求超时")
        except httpx.RequestError as e:
            return ASRResult(success=False, error=f"ASR API 请求错误: {str(e)}")
        except Exception as e:
            return ASRResult(success=False, error=f"ASR 处理异常: {str(e)}")


def save_asr_result(result: ASRResult, audio_filename: str, storage_dir: Path) -> Path:
    """
    保存 ASR 识别结果到 Storage 目录
    
    Args:
        result: ASR 识别结果
        audio_filename: 原始音频文件名
        storage_dir: 存储目录
        
    Returns:
        保存的 JSON 文件路径
    """
    json_filename = Path(audio_filename).stem + "_asr.json"
    json_path = storage_dir / json_filename

    result_data = {
        "audio_file": audio_filename,
        "success": result.success,
        "text": result.text,
        "language": result.language,
        "emotion": result.emotion,
        "duration_seconds": result.duration_seconds,
        "error": result.error
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    return json_path
