"""
高德地图 MCP 客户端服务

连接远端 MCP Server，调用地图相关工具
"""

import json
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

import config
from utils.logger import logger, save_json_log


@dataclass
class GeoLocation:
    """地理位置信息"""
    lng: float
    lat: float
    formatted_address: str = ""
    level: str = ""
    raw: dict = None
    
    def __post_init__(self):
        if self.raw is None:
            self.raw = {}


@dataclass
class MeetingPointResult:
    """会面地点推荐结果"""
    success: bool
    meeting_point: str = ""
    distance: float = 0.0
    location1_info: GeoLocation | None = None
    location2_info: GeoLocation | None = None
    error: str = ""
    via_mcp: bool = True
    fallback_reason: str = ""


class AmapMCPClient:
    """高德地图 MCP 客户端"""
    
    def __init__(self):
        self.mcp_url = self._build_mcp_url()
        self.api_key = config.AMAP_API_KEY
        
        if not self.api_key:
            raise ValueError("AMAP_API_KEY 未配置")
        
        logger.info("高德MCP", f"MCP URL: https://mcp.amap.com/mcp")
        logger.info("高德MCP", "客户端初始化成功")
        
        self.mcp_log: dict[str, Any] = {
            "request_id": "",
            "mcp_url_host": "https://mcp.amap.com/mcp",
            "mcp_enabled": True,
            "started_at": "",
            "steps": [],
            "selected_tools": [],
            "normalized_result": {},
            "fallback_used": False,
            "fallback_reason": "",
            "finished_at": ""
        }
    
    def _build_mcp_url(self) -> str:
        """构建 MCP URL"""
        base_url = config.AMAP_MCP_URL if hasattr(config, 'AMAP_MCP_URL') and config.AMAP_MCP_URL else None
        
        if base_url:
            return base_url
        
        if not config.AMAP_API_KEY:
            raise ValueError("未配置 AMAP_MCP_URL 或 AMAP_API_KEY")
        
        return f"https://mcp.amap.com/mcp?key={config.AMAP_API_KEY}"
    
    def _log_step(self, name: str, success: bool, error: str = "", **kwargs):
        """记录 MCP 调用步骤"""
        step = {
            "name": name,
            "success": success,
            "error": error if error else None,
            **kwargs
        }
        self.mcp_log["steps"].append(step)
        
        if success:
            logger.success("高德MCP", f"✓ {name}")
        else:
            logger.error("高德MCP", f"✗ {name}: {error}")

    def _content_text(self, content: Any) -> str:
        """提取 MCP content 中的文本，兼容不同 SDK content 类型"""
        if content is None:
            return ""
        if hasattr(content, "text"):
            return content.text or ""
        return str(content)

    def _preview_text(self, text: str, limit: int = 240) -> str:
        """生成适合写入日志的响应摘要"""
        compact = " ".join((text or "").split())
        if len(compact) <= limit:
            return compact
        return f"{compact[:limit]}..."

    def _tool_result_preview(self, result: Any) -> dict[str, Any]:
        """生成 MCP 工具返回摘要，避免只记录 content_count"""
        content = getattr(result, "content", None) or []
        first = content[0] if content else None
        text = self._content_text(first)
        return {
            "content_count": len(content),
            "first_content_type": type(first).__name__ if first else None,
            "text_length": len(text),
            "text_preview": self._preview_text(text)
        }

    def _load_tool_json(self, result: Any, label: str) -> tuple[dict[str, Any], str]:
        """安全解析 MCP 工具 JSON 返回，失败时返回错误描述"""
        content = getattr(result, "content", None) or []
        first = content[0] if content else None
        text = self._content_text(first).strip()

        if not text:
            return {}, f"{label} 返回空文本"

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            preview = self._preview_text(text)
            return {}, f"{label} 返回非 JSON: {e.msg}，响应摘要: {preview or '<empty>'}"

        if not isinstance(data, dict):
            return {}, f"{label} JSON 顶层不是对象: {type(data).__name__}"

        return data, ""
    
    def _parse_geo_result(self, result: Any) -> GeoLocation | None:
        """解析地理编码结果"""
        try:
            # 尝试 MCP 形态：results[]
            if isinstance(result, dict) and "results" in result:
                results = result["results"]
                if results and len(results) > 0:
                    first = results[0]
                    location_str = first.get("location", "")
                    lng, lat = map(float, location_str.split(","))
                    
                    return GeoLocation(
                        lng=lng,
                        lat=lat,
                        formatted_address=first.get("formatted_address", ""),
                        level=first.get("level", ""),
                        raw=first
                    )
            
            # 尝试 REST 形态：geocodes[]
            if isinstance(result, dict) and "geocodes" in result:
                geocodes = result["geocodes"]
                if geocodes and len(geocodes) > 0:
                    first = geocodes[0]
                    location_str = first.get("location", "")
                    lng, lat = map(float, location_str.split(","))
                    
                    return GeoLocation(
                        lng=lng,
                        lat=lat,
                        formatted_address=first.get("formatted_address", ""),
                        level=first.get("level", ""),
                        raw=first
                    )
            
            logger.error("高德MCP", f"无法解析地理编码结果，未知格式: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            return None
            
        except Exception as e:
            logger.error("高德MCP", f"解析地理编码结果异常: {str(e)}")
            return None

    def _parse_poi_location(self, poi: dict[str, Any]) -> GeoLocation | None:
        """从 POI 对象解析经纬度"""
        location_str = poi.get("location", "")
        if not location_str:
            return None

        lng, lat = map(float, location_str.split(","))
        address = poi.get("address", "")
        if isinstance(address, list):
            address = "、".join(str(item) for item in address)

        formatted_address = address or "".join([
            str(poi.get("pname", "")),
            str(poi.get("cityname", "")),
            str(poi.get("adname", "")),
            str(poi.get("name", "")),
        ])

        return GeoLocation(
            lng=lng,
            lat=lat,
            formatted_address=formatted_address,
            level=poi.get("type", ""),
            raw=poi
        )

    def _extract_pois(self, result: Any) -> list[dict[str, Any]]:
        """提取常见 MCP/REST POI 列表"""
        if not isinstance(result, dict):
            return []

        pois = result.get("pois", []) or result.get("results", [])
        if isinstance(pois, list):
            return [poi for poi in pois if isinstance(poi, dict)]

        return []

    def _parse_text_search_result(self, result: Any) -> GeoLocation | None:
        """解析 POI 文本搜索结果，用于地理编码失败时回退"""
        try:
            pois = self._extract_pois(result)

            if not pois:
                logger.error("高德MCP", f"无法解析文本搜索结果，顶层字段: {list(result.keys()) if isinstance(result, dict) else type(result)}")
                return None

            for poi in pois:
                loc = self._parse_poi_location(poi)
                if loc:
                    return loc

            return None

        except Exception as e:
            logger.error("高德MCP", f"解析文本搜索结果异常: {str(e)}")
            return None

    async def _search_detail_location(
        self,
        session: ClientSession,
        pois: list[dict[str, Any]],
        label: str
    ) -> tuple[GeoLocation | None, str]:
        """使用 maps_search_detail 查询 POI 详情坐标"""
        for poi in pois[:3]:
            poi_id = poi.get("id", "")
            if not poi_id:
                continue

            detail_raw = await session.call_tool("maps_search_detail", arguments={"id": poi_id})
            detail_preview = self._tool_result_preview(detail_raw)

            self._log_step(
                "call_tool",
                True,
                tool="maps_search_detail",
                arguments_preview={"id": poi_id, "name": poi.get("name", "")},
                raw_preview=detail_preview
            )

            detail_data, detail_error = self._load_tool_json(detail_raw, f"{label} maps_search_detail")
            if detail_error:
                self._log_step(
                    "parse_tool_result",
                    False,
                    error=detail_error,
                    tool="maps_search_detail",
                    arguments_preview={"id": poi_id, "name": poi.get("name", "")},
                    raw_preview=detail_preview
                )
                continue

            loc = self._parse_poi_location(detail_data)
            if loc:
                return loc, ""

            loc = self._parse_text_search_result(detail_data)
            if loc:
                return loc, ""

            error = f"{label} maps_search_detail 结果无法归一化，顶层字段: {list(detail_data.keys())}"
            self._log_step(
                "parse_tool_result",
                False,
                error=error,
                tool="maps_search_detail",
                arguments_preview={"id": poi_id, "name": poi.get("name", "")},
                raw_preview=detail_preview
            )

        return None, f"{label} maps_search_detail 未能解析候选 POI 坐标"

    async def _geocode_location(
        self,
        session: ClientSession,
        tool_names: list[str],
        address: str,
        city: str,
        label: str
    ) -> tuple[GeoLocation | None, str]:
        """地理编码地址，maps_geo 失败时尝试 maps_text_search"""
        logger.info("高德MCP", f"  编码{label}: {address}")

        geo_args = {"address": address, "city": city} if city else {"address": address}
        geo_raw = await session.call_tool("maps_geo", arguments=geo_args)
        geo_preview = self._tool_result_preview(geo_raw)

        self._log_step(
            "call_tool",
            True,
            tool="maps_geo",
            arguments_preview={"address": address, "city": city},
            raw_preview=geo_preview
        )

        geo_data, geo_error = self._load_tool_json(geo_raw, f"{label} maps_geo")
        if not geo_error:
            loc = self._parse_geo_result(geo_data)
            if loc:
                logger.success("高德MCP", f"  {label}: {loc.formatted_address} ({loc.lng}, {loc.lat})")
                return loc, ""
            geo_error = f"{label} maps_geo 结果无法归一化，顶层字段: {list(geo_data.keys())}"

        logger.warning("高德MCP", f"  {label} maps_geo 解析失败: {geo_error}")
        self._log_step(
            "parse_tool_result",
            False,
            error=geo_error,
            tool="maps_geo",
            arguments_preview={"address": address, "city": city},
            raw_preview=geo_preview
        )

        if "maps_text_search" not in tool_names:
            return None, geo_error

        logger.info("高德MCP", f"  使用文本搜索回退{label}: {address}")
        search_args = {"keywords": address, "city": city} if city else {"keywords": address}
        search_raw = await session.call_tool("maps_text_search", arguments=search_args)
        search_preview = self._tool_result_preview(search_raw)

        self._log_step(
            "call_tool",
            True,
            tool="maps_text_search",
            arguments_preview={"keywords": address, "city": city},
            raw_preview=search_preview
        )

        search_data, search_error = self._load_tool_json(search_raw, f"{label} maps_text_search")
        if search_error:
            self._log_step(
                "parse_tool_result",
                False,
                error=search_error,
                tool="maps_text_search",
                arguments_preview={"keywords": address, "city": city},
                raw_preview=search_preview
            )
            return None, f"{geo_error}; {search_error}"

        loc = self._parse_text_search_result(search_data)
        if not loc:
            pois = self._extract_pois(search_data)
            if "maps_search_detail" in tool_names and pois:
                logger.info("高德MCP", f"  文本搜索候选缺少坐标，查询 POI 详情")
                loc, detail_error = await self._search_detail_location(session, pois, label)
                if not loc:
                    search_error = f"{label} maps_text_search/maps_search_detail 结果无法归一化: {detail_error}"
                    self._log_step(
                        "parse_tool_result",
                        False,
                        error=search_error,
                        tool="maps_text_search",
                        arguments_preview={"keywords": address, "city": city},
                        raw_preview=search_preview
                    )
                    return None, f"{geo_error}; {search_error}"
            else:
                search_error = f"{label} maps_text_search 结果无法归一化，顶层字段: {list(search_data.keys())}"
                self._log_step(
                    "parse_tool_result",
                    False,
                    error=search_error,
                    tool="maps_text_search",
                    arguments_preview={"keywords": address, "city": city},
                    raw_preview=search_preview
                )
                return None, f"{geo_error}; {search_error}"

        self.mcp_log["fallback_used"] = True
        self.mcp_log["fallback_reason"] = f"{label} maps_geo 解析失败，改用 maps_text_search/maps_search_detail"
        logger.success("高德MCP", f"  {label}: {loc.formatted_address} ({loc.lng}, {loc.lat})")
        return loc, ""
    
    async def find_meeting_point(
        self,
        location1: str,
        location2: str,
        city: str = "",
        request_id: str = ""
    ) -> MeetingPointResult:
        """
        查找两个地点之间的会面地点
        
        Args:
            location1: 第一个地点
            location2: 第二个地点
            city: 城市（可选）
            request_id: 请求ID
            
        Returns:
            MeetingPointResult 会面地点推荐结果
        """
        self.mcp_log["request_id"] = request_id
        self.mcp_log["started_at"] = datetime.now().isoformat()
        
        logger.section("高德 MCP 服务调用")
        logger.info("高德MCP", f"查找会面地点: {location1} <-> {location2}")
        if city:
            logger.info("高德MCP", f"指定城市: {city}")
        
        try:
            logger.step(1, 5, "连接 MCP 服务器")
            
            # 配置 httpx 不使用代理
            import httpx
            
            # 创建不使用代理的 httpx 客户端
            http_client = httpx.AsyncClient(
                trust_env=False,  # 不信任环境变量（包括代理设置）
                timeout=60.0,
                follow_redirects=True
            )
            
            try:
                async with streamable_http_client(
                    self.mcp_url,
                    http_client=http_client
                ) as streams:
                    logger.success("高德MCP", "✓ 连接建立")
                    
                    # 注意：使用 *_ 接收可能的额外返回值
                    read_stream, write_stream, *_ = streams
                    
                    logger.step(2, 5, "创建 MCP Session")
                    async with ClientSession(read_stream, write_stream) as session:
                        logger.success("高德MCP", "✓ Session 创建成功")
                        
                        # 步骤 1: 初始化
                        logger.step(3, 5, "初始化 MCP 连接")
                        await session.initialize()
                        self._log_step("initialize", True)
                        
                        # 步骤 2: 获取工具列表
                        logger.step(4, 5, "获取可用工具列表")
                        tools_response = await session.list_tools()
                        tools = tools_response.tools
                        tool_names = [tool.name for tool in tools]
                        
                        logger.info("高德MCP", f"可用工具数量: {len(tools)}")
                        logger.debug("高德MCP", f"工具列表: {', '.join(tool_names[:5])}...")
                        
                        self._log_step(
                            "list_tools",
                            True,
                            tools=tool_names,
                            raw_preview={"count": len(tools)}
                        )
                        
                        # 步骤 3: 调用地理编码工具
                        logger.step(5, 5, "地理编码与距离计算")
                        
                        # 检查 maps_geo 工具是否存在
                        if "maps_geo" not in tool_names:
                            error_msg = "maps_geo 工具不存在"
                            logger.error("高德MCP", error_msg)
                            self._log_step("call_tool", False, error=error_msg)
                            return MeetingPointResult(
                                success=False,
                                error=error_msg,
                                via_mcp=True
                            )
                        
                        loc1, loc1_error = await self._geocode_location(
                            session=session,
                            tool_names=tool_names,
                            address=location1,
                            city=city,
                            label="位置1"
                        )
                        if not loc1:
                            error_msg = f"位置1地理编码解析失败: {loc1_error}"
                            logger.error("高德MCP", error_msg)
                            return MeetingPointResult(success=False, error=error_msg, via_mcp=True)

                        loc2, loc2_error = await self._geocode_location(
                            session=session,
                            tool_names=tool_names,
                            address=location2,
                            city=city,
                            label="位置2"
                        )
                        if not loc2:
                            error_msg = f"位置2地理编码解析失败: {loc2_error}"
                            logger.error("高德MCP", error_msg)
                            return MeetingPointResult(success=False, error=error_msg, via_mcp=True)
                        
                        # 步骤 4: 计算距离和中点
                        mid_lng = (loc1.lng + loc2.lng) / 2
                        mid_lat = (loc1.lat + loc2.lat) / 2
                        
                        distance = 0.0
                        if "maps_distance" in tool_names:
                            distance_raw = await session.call_tool(
                                "maps_distance",
                                arguments={
                                    "origins": f"{loc1.lng},{loc1.lat}",
                                    "destination": f"{loc2.lng},{loc2.lat}",
                                    "type": 0  # 直线距离
                                }
                            )
                            
                            self._log_step(
                                "call_tool",
                                True,
                                tool="maps_distance",
                                arguments_preview={"type": 0},
                                raw_preview=self._tool_result_preview(distance_raw)
                            )
                            
                            distance_data, distance_error = self._load_tool_json(distance_raw, "maps_distance")
                            if distance_error:
                                logger.warning("高德MCP", f"  距离计算结果解析失败: {distance_error}")
                                self._log_step(
                                    "parse_tool_result",
                                    False,
                                    error=distance_error,
                                    tool="maps_distance"
                                )
                            
                            if "results" in distance_data and distance_data["results"]:
                                distance = float(distance_data["results"][0].get("distance", 0))
                            
                            logger.info("高德MCP", f"  两地距离: {distance:.0f} 米")
                        
                        # 步骤 5: 搜索中点附近的推荐地点
                        logger.info("高德MCP", f"  搜索中点附近的会面地点...")
                        
                        meeting_places = []
                        if "maps_around_search" in tool_names:
                            # 搜索咖啡馆、餐厅等适合会面的地点
                            search_keywords = ["咖啡馆", "餐厅", "茶楼"]
                            
                            for keyword in search_keywords:
                                try:
                                    search_raw = await session.call_tool(
                                        "maps_around_search",
                                        arguments={
                                            "location": f"{mid_lng},{mid_lat}",
                                            "keywords": keyword,
                                            "radius": 1000,  # 1公里范围
                                            "sortrule": "distance"  # 按距离排序
                                        }
                                    )
                                    
                                    self._log_step(
                                        "call_tool",
                                        True,
                                        tool="maps_around_search",
                                        arguments_preview={"keywords": keyword, "radius": 1000},
                                        raw_preview=self._tool_result_preview(search_raw)
                                    )
                                    
                                    search_data, search_error = self._load_tool_json(search_raw, f"maps_around_search {keyword}")
                                    if search_error:
                                        logger.warning("高德MCP", f"    搜索{keyword}结果解析失败: {search_error}")
                                        self._log_step(
                                            "parse_tool_result",
                                            False,
                                            error=search_error,
                                            tool="maps_around_search",
                                            arguments_preview={"keywords": keyword, "radius": 1000}
                                        )
                                        continue

                                    # 解析 POI 结果
                                    pois = search_data.get("pois", []) or search_data.get("results", [])
                                    if pois:
                                        for poi in pois[:2]:  # 取前2个
                                            meeting_places.append({
                                                "name": poi.get("name", ""),
                                                "address": poi.get("address", ""),
                                                "type": keyword,
                                                "distance": poi.get("distance", "")
                                            })
                                        logger.info("高德MCP", f"    找到 {len(pois)} 个{keyword}")
                                        break  # 找到一个类型就足够了
                                except Exception as e:
                                    logger.warning("高德MCP", f"    搜索{keyword}失败: {str(e)}")
                                    continue
                        
                        # 构建推荐文本
                        if meeting_places:
                            meeting_point = f"推荐会面地点：\n\n"
                            for i, place in enumerate(meeting_places[:3], 1):
                                meeting_point += f"{i}. {place['name']}\n"
                                meeting_point += f"   地址: {place['address']}\n"
                                if place['distance']:
                                    meeting_point += f"   距中点: {place['distance']}米\n"
                                meeting_point += "\n"
                            meeting_point += f"两地中点坐标: ({mid_lng:.6f}, {mid_lat:.6f})\n"
                            meeting_point += f"两地直线距离: {distance:.0f}米"
                        else:
                            logger.warning("高德MCP", "未找到推荐地点，返回中点坐标")
                            meeting_point = f"建议在两地中点附近会面\n坐标: ({mid_lng:.6f}, {mid_lat:.6f})\n直线距离: {distance:.0f}米"
                        
                        # 构建结果
                        result = MeetingPointResult(
                            success=True,
                            meeting_point=meeting_point,
                            distance=distance,
                            location1_info=loc1,
                            location2_info=loc2,
                            via_mcp=True
                        )
                        
                        self.mcp_log["normalized_result"] = {
                            "meeting_point": meeting_point,
                            "distance": distance,
                            "recommended_places": meeting_places,
                            "midpoint": {
                                "lng": mid_lng,
                                "lat": mid_lat
                            },
                            "location1": asdict(loc1),
                            "location2": asdict(loc2)
                        }
                        
                        logger.success("高德MCP", "会面地点推荐完成")
                        
                        return result
            finally:
                # 确保关闭 http_client
                await http_client.aclose()
                    
        except Exception as e:
            error_msg = f"MCP 调用异常: {str(e)}"
            error_type = type(e).__name__
            
            logger.error("高德MCP", f"{error_type}: {error_msg}")
            
            # 记录更详细的错误信息
            import traceback
            logger.debug("高德MCP", f"错误堆栈:\n{traceback.format_exc()}")
            
            self._log_step("call_tool", False, error=f"{error_type}: {error_msg}")
            
            return MeetingPointResult(
                success=False,
                error=error_msg,
                via_mcp=True
            )
        finally:
            self.mcp_log["finished_at"] = datetime.now().isoformat()
    
    def save_mcp_log(self, storage_dir: Path) -> Path:
        """
        保存 MCP 调用日志
        
        Args:
            storage_dir: 存储目录
            
        Returns:
            保存的文件路径
        """
        filename = f"{self.mcp_log['request_id']}_mcp.json"
        logger.info("高德MCP", f"保存 MCP 调用日志: {filename}")
        return save_json_log(self.mcp_log, filename, storage_dir)
