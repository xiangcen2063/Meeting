"""
Deepseek 槽位提取服务

从 ASR 识别结果中提取地址位置信息
"""

import json
from dataclasses import dataclass
from pathlib import Path

import httpx

import config
from utils.logger import logger, save_json_log


@dataclass
class LocationSlot:
    """提取的位置槽位"""
    location1: str = ""
    location2: str = ""
    city: str = ""
    raw_text: str = ""
    success: bool = False
    error: str = ""


class DeepseekService:
    """Deepseek API 服务"""
    
    API_URL = "https://api.deepseek.com/chat/completions"
    MODEL = "deepseek-v4-flash"
    
    SYSTEM_PROMPT = """你是一个专业的地址信息提取助手。
你的任务是从用户的描述中提取两个地址位置。

要求：
1. 识别用户描述中的两个地点（通常是"我"的位置和"朋友/对方"的位置）
2. 尽可能保留完整的地址信息
3. 如果提到城市，提取城市信息
4. 如果只有一个地点，location2 设为空字符串
5. 如果没有明确地点，所有字段设为空字符串

必须返回标准 JSON 格式（不要有任何其他内容）：
{
  "location1": "第一个地点",
  "location2": "第二个地点",
  "city": "城市名称"
}"""
    
    def __init__(self):
        # 清除代理设置
        import os
        for var in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']:
            if var in os.environ:
                del os.environ[var]
        
        self.api_key = config.DEEPSEEK_API_KEY
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未配置")
        logger.info("Deepseek", "服务初始化成功")
    
    def extract_locations(self, text: str) -> LocationSlot:
        """
        从文本中提取位置信息
        
        Args:
            text: ASR 识别的文本
            
        Returns:
            LocationSlot 槽位信息
        """
        logger.info("Deepseek", f"开始提取地址槽位")
        logger.debug("Deepseek", f"输入文本: {text}")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            "response_format": {
                "type": "json_object"
            },
            "temperature": 0.3,
            "stream": False
        }
        
        # 尝试最多 3 次
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.warning("Deepseek", f"重试第 {attempt} 次...")
                
                # 创建 httpx 客户端，禁用 HTTP/2 和配置 SSL
                with httpx.Client(
                    timeout=30.0,
                    http2=False,  # 禁用 HTTP/2 可能解决某些 SSL 问题
                    verify=True,  # 保持 SSL 验证
                    follow_redirects=True
                ) as client:
                    response = client.post(
                        self.API_URL,
                        headers=headers,
                        json=payload
                    )
                
                if response.status_code != 200:
                    error_msg = f"Deepseek API 请求失败: HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_msg = f"{error_msg} - {error_data['error'].get('message', '')}"
                    except Exception:
                        error_msg = f"{error_msg} - {response.text}"
                    
                    logger.error("Deepseek", error_msg)
                    return LocationSlot(raw_text=text, success=False, error=error_msg)
                
                result = response.json()
                
                # 提取生成的内容
                content = result["choices"][0]["message"]["content"]
                logger.debug("Deepseek", f"原始响应: {content}")
                
                # 解析 JSON
                try:
                    locations_data = json.loads(content)
                except json.JSONDecodeError as e:
                    error_msg = f"JSON 解析失败: {str(e)}"
                    logger.error("Deepseek", error_msg)
                    return LocationSlot(raw_text=text, success=False, error=error_msg)
                
                # 构建结果
                slot = LocationSlot(
                    location1=locations_data.get("location1", ""),
                    location2=locations_data.get("location2", ""),
                    city=locations_data.get("city", ""),
                    raw_text=text,
                    success=True
                )
                
                logger.success("Deepseek", f"槽位提取成功")
                logger.info("Deepseek", f"  位置1: {slot.location1}")
                logger.info("Deepseek", f"  位置2: {slot.location2}")
                if slot.city:
                    logger.info("Deepseek", f"  城市: {slot.city}")
                
                return slot
                
            except httpx.TimeoutException:
                last_error = "Deepseek API 请求超时"
                logger.warning("Deepseek", last_error)
                if attempt < max_retries - 1:
                    continue
            except httpx.RequestError as e:
                last_error = f"Deepseek API 请求错误: {str(e)}"
                logger.warning("Deepseek", last_error)
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)  # 等待 1 秒后重试
                    continue
            except Exception as e:
                last_error = f"Deepseek 处理异常: {str(e)}"
                logger.warning("Deepseek", last_error)
                if attempt < max_retries - 1:
                    continue
        
        # 所有重试都失败
        logger.error("Deepseek", f"经过 {max_retries} 次重试后仍然失败: {last_error}")
        return LocationSlot(raw_text=text, success=False, error=last_error)
    
    def generate_response(
        self,
        location1: str,
        location2: str,
        meeting_places: list,
        distance: float
    ) -> str:
        """
        根据高德 MCP 结果生成自然语言回复
        
        Args:
            location1: 第一个地点
            location2: 第二个地点
            meeting_places: 推荐的会面地点列表
            distance: 两地距离
            
        Returns:
            自然语言回复文本
        """
        logger.info("Deepseek", f"开始生成自然语言回复")
        
        # 构建上下文
        if meeting_places:
            places_text = "、".join([p['name'] for p in meeting_places[:3]])
            context = f"用户在{location1}，朋友在{location2}，两地距离{distance:.0f}米。推荐的会面地点有：{places_text}。"
        else:
            context = f"用户在{location1}，朋友在{location2}，两地距离{distance:.0f}米。"
        
        system_prompt = """你是一个友好的会面地点推荐助手。
根据提供的位置信息和推荐地点，生成一段自然、友好的语音回复。

要求：
1. 语气自然、友好
2. 简洁明了，不超过100字
3. 突出推荐的地点
4. 可以适当加入建议（如交通方式等）
5. 直接输出回复文本，不要有任何多余的格式"""
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": context
                }
            ],
            "temperature": 0.7,
            "stream": False
        }
        
        try:
            with httpx.Client(
                timeout=30.0,
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
                error_msg = f"Deepseek API 请求失败: HTTP {response.status_code}"
                logger.error("Deepseek", error_msg)
                return f"根据您的位置，推荐在{location1}和{location2}之间的{meeting_places[0]['name'] if meeting_places else '中点'}会面。"
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            logger.success("Deepseek", f"自然语言回复生成成功")
            logger.debug("Deepseek", f"回复: {content}")
            
            return content
            
        except Exception as e:
            logger.error("Deepseek", f"生成回复异常: {str(e)}")
            # 返回兜底回复
            return f"根据您的位置，推荐在{location1}和{location2}之间的{meeting_places[0]['name'] if meeting_places else '中点'}会面。"


def save_slot_result(slot: LocationSlot, request_id: str, storage_dir: Path) -> Path:
    """
    保存槽位提取结果
    
    Args:
        slot: 槽位提取结果
        request_id: 请求ID
        storage_dir: 存储目录
        
    Returns:
        保存的文件路径
    """
    filename = f"{request_id}_slot.json"
    
    data = {
        "request_id": request_id,
        "success": slot.success,
        "raw_text": slot.raw_text,
        "extracted": {
            "location1": slot.location1,
            "location2": slot.location2,
            "city": slot.city
        },
        "error": slot.error
    }
    
    return save_json_log(data, filename, storage_dir)
