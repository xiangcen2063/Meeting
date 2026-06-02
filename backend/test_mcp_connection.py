"""
测试高德 MCP 连接

运行此脚本来诊断 MCP 连接问题
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from dotenv import load_dotenv

load_dotenv()

async def test_mcp_connection():
    """测试 MCP 连接"""
    amap_key = os.getenv("AMAP_API_KEY")
    
    if not amap_key:
        print("❌ 错误: AMAP_API_KEY 未配置")
        return
    
    mcp_url = f"https://mcp.amap.com/mcp?key={amap_key}"
    
    print(f"📡 测试 MCP 连接...")
    print(f"   URL: https://mcp.amap.com/mcp")
    print()
    
    try:
        print("1️⃣  创建 streamable HTTP 客户端...")
        async with streamable_http_client(mcp_url) as streams:
            print("   ✅ 客户端创建成功")
            
            read_stream, write_stream, *_ = streams
            print(f"   ✅ 获取到 streams: read={type(read_stream).__name__}, write={type(write_stream).__name__}")
            
            print()
            print("2️⃣  创建 MCP Session...")
            async with ClientSession(read_stream, write_stream) as session:
                print("   ✅ Session 创建成功")
                
                print()
                print("3️⃣  初始化连接...")
                await session.initialize()
                print("   ✅ 初始化成功")
                
                print()
                print("4️⃣  获取工具列表...")
                tools_response = await session.list_tools()
                tools = tools_response.tools
                print(f"   ✅ 获取到 {len(tools)} 个工具")
                
                print()
                print("📋 可用工具列表:")
                for i, tool in enumerate(tools[:10], 1):
                    print(f"   {i}. {tool.name}")
                if len(tools) > 10:
                    print(f"   ... 还有 {len(tools) - 10} 个工具")
                
                print()
                print("5️⃣  测试地理编码...")
                result = await session.call_tool(
                    "maps_geo",
                    arguments={"address": "西湖", "city": "杭州"}
                )
                print(f"   ✅ 地理编码成功")
                print(f"   返回内容: {result.content[0].text[:100]}...")
                
        print()
        print("🎉 所有测试通过！MCP 连接正常")
        
    except Exception as e:
        print()
        print(f"❌ 测试失败: {type(e).__name__}")
        print(f"   错误信息: {str(e)}")
        print()
        print("📝 错误堆栈:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("高德地图 MCP 连接诊断")
    print("=" * 60)
    print()
    
    asyncio.run(test_mcp_connection())
