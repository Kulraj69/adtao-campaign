#!/usr/bin/env python3
"""
MCP Server for AdTao Campaign API with Supabase Integration
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional, Union
import asyncpg
import httpx
from datetime import datetime

# MCP Protocol imports (you may need to install these)
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.types import (
        CallToolRequestParams,
        GetResourceRequestParams,
        ListResourcesRequestParams,
        ListToolsRequestParams,
        Resource,
        TextContent,
        Tool,
    )
except ImportError:
    print("MCP library not found. Please install: pip install mcp")
    sys.exit(1)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

class AdTaoMCPServer:
    def __init__(self):
        self.server = Server("adtao-campaign-mcp")
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.database_url = os.getenv("DATABASE_URL")
        self.api_base_url = "http://127.0.0.1:8000"
        
        # Register handlers
        self.setup_handlers()
    
    def setup_handlers(self):
        """Set up MCP protocol handlers"""
        
        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """List available resources"""
            return [
                Resource(
                    uri="adtao://database/tables",
                    name="Database Tables",
                    description="List all database tables and their schemas",
                    mimeType="application/json"
                ),
                Resource(
                    uri="adtao://api/endpoints",
                    name="API Endpoints",
                    description="Available FastAPI endpoints",
                    mimeType="application/json"
                ),
                Resource(
                    uri="adtao://campaigns/recent",
                    name="Recent Campaigns",
                    description="Recently created ad campaigns",
                    mimeType="application/json"
                )
            ]
        
        @self.server.get_resource()
        async def handle_get_resource(uri: str) -> str:
            """Get resource content"""
            if uri == "adtao://database/tables":
                return await self.get_database_schema()
            elif uri == "adtao://api/endpoints":
                return await self.get_api_endpoints()
            elif uri == "adtao://campaigns/recent":
                return await self.get_recent_campaigns()
            else:
                raise ValueError(f"Unknown resource: {uri}")
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="execute_sql",
                    description="Execute SQL query on Supabase database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "SQL query to execute"
                            },
                            "params": {
                                "type": "array",
                                "description": "Query parameters",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="call_api_endpoint",
                    description="Call FastAPI endpoint",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "endpoint": {
                                "type": "string",
                                "description": "API endpoint path (e.g., /generate-ad-copy)"
                            },
                            "method": {
                                "type": "string",
                                "description": "HTTP method (GET, POST, PUT, DELETE)",
                                "enum": ["GET", "POST", "PUT", "DELETE"]
                            },
                            "data": {
                                "type": "object",
                                "description": "Request payload"
                            }
                        },
                        "required": ["endpoint", "method"]
                    }
                ),
                Tool(
                    name="create_campaign",
                    description="Create a complete ad campaign with copy and images",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "product_name": {"type": "string"},
                            "target_audience": {"type": "string"},
                            "key_benefits": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "tone": {"type": "string", "default": "professional"},
                            "generate_image": {"type": "boolean", "default": True}
                        },
                        "required": ["product_name", "target_audience", "key_benefits"]
                    }
                ),
                Tool(
                    name="analyze_campaign_performance",
                    description="Analyze campaign performance from database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "campaign_id": {"type": "string"},
                            "date_range": {"type": "string", "description": "Date range (e.g., '7d', '30d')"}
                        }
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            try:
                if name == "execute_sql":
                    result = await self.execute_sql(arguments["query"], arguments.get("params", []))
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "call_api_endpoint":
                    result = await self.call_api_endpoint(
                        arguments["endpoint"],
                        arguments["method"],
                        arguments.get("data")
                    )
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "create_campaign":
                    result = await self.create_campaign(arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "analyze_campaign_performance":
                    result = await self.analyze_campaign_performance(
                        arguments.get("campaign_id"),
                        arguments.get("date_range", "7d")
                    )
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
                else:
                    raise ValueError(f"Unknown tool: {name}")
            
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def execute_sql(self, query: str, params: List[Any] = None) -> Dict[str, Any]:
        """Execute SQL query on Supabase database"""
        try:
            conn = await asyncpg.connect(self.database_url)
            try:
                if params:
                    result = await conn.fetch(query, *params)
                else:
                    result = await conn.fetch(query)
                
                # Convert to dict format
                return {
                    "success": True,
                    "rows": [dict(row) for row in result],
                    "row_count": len(result)
                }
            finally:
                await conn.close()
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def call_api_endpoint(self, endpoint: str, method: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Call FastAPI endpoint"""
        url = f"{self.api_base_url}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                if method == "GET":
                    response = await client.get(url)
                elif method == "POST":
                    response = await client.post(url, json=data)
                elif method == "PUT":
                    response = await client.put(url, json=data)
                elif method == "DELETE":
                    response = await client.delete(url)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": response.json() if response.content else None
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
    
    async def create_campaign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a complete ad campaign"""
        try:
            # Call the integrated ad creation endpoint
            endpoint = "/generate-integrated-ad"
            result = await self.call_api_endpoint(endpoint, "POST", params)
            
            if result["success"]:
                # Store campaign in database
                campaign_data = result["data"]
                query = """
                INSERT INTO campaigns (
                    product_name, target_audience, headline, primary_text, 
                    description, image_path, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """
                db_result = await self.execute_sql(query, [
                    params["product_name"],
                    params["target_audience"],
                    campaign_data.get("headline", ""),
                    campaign_data.get("primary_text", ""),
                    campaign_data.get("description", ""),
                    campaign_data.get("image_path", ""),
                    datetime.now()
                ])
                
                return {
                    "success": True,
                    "campaign": campaign_data,
                    "database_id": db_result["rows"][0]["id"] if db_result["success"] else None
                }
            else:
                return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def analyze_campaign_performance(self, campaign_id: Optional[str], date_range: str) -> Dict[str, Any]:
        """Analyze campaign performance"""
        try:
            if campaign_id:
                query = "SELECT * FROM campaigns WHERE id = $1"
                params = [campaign_id]
            else:
                # Get recent campaigns based on date range
                if date_range == "7d":
                    query = "SELECT * FROM campaigns WHERE created_at >= NOW() - INTERVAL '7 days' ORDER BY created_at DESC"
                elif date_range == "30d":
                    query = "SELECT * FROM campaigns WHERE created_at >= NOW() - INTERVAL '30 days' ORDER BY created_at DESC"
                else:
                    query = "SELECT * FROM campaigns ORDER BY created_at DESC LIMIT 10"
                params = []
            
            result = await self.execute_sql(query, params)
            
            if result["success"]:
                campaigns = result["rows"]
                analysis = {
                    "total_campaigns": len(campaigns),
                    "date_range": date_range,
                    "campaigns": campaigns,
                    "summary": {
                        "most_common_audience": self.get_most_common(campaigns, "target_audience"),
                        "most_common_tone": self.get_most_common(campaigns, "tone") if campaigns else None,
                        "avg_headline_length": sum(len(c.get("headline", "")) for c in campaigns) / len(campaigns) if campaigns else 0
                    }
                }
                return {"success": True, "analysis": analysis}
            else:
                return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_most_common(self, items: List[Dict], field: str) -> Optional[str]:
        """Get most common value for a field"""
        if not items:
            return None
        
        counts = {}
        for item in items:
            value = item.get(field)
            if value:
                counts[value] = counts.get(value, 0) + 1
        
        return max(counts, key=counts.get) if counts else None
    
    async def get_database_schema(self) -> str:
        """Get database schema information"""
        query = """
        SELECT table_name, column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
        """
        result = await self.execute_sql(query)
        return json.dumps(result, indent=2)
    
    async def get_api_endpoints(self) -> str:
        """Get available API endpoints"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.api_base_url}/openapi.json")
                if response.status_code == 200:
                    openapi_spec = response.json()
                    endpoints = list(openapi_spec.get("paths", {}).keys())
                    return json.dumps({"endpoints": endpoints}, indent=2)
                else:
                    return json.dumps({"error": "Could not fetch API spec"}, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)
    
    async def get_recent_campaigns(self) -> str:
        """Get recent campaigns"""
        result = await self.execute_sql(
            "SELECT * FROM campaigns ORDER BY created_at DESC LIMIT 10"
        )
        return json.dumps(result, indent=2, default=str)
    
    async def run(self):
        """Run the MCP server"""
        async with self.server.run(
            stdin=sys.stdin.buffer,
            stdout=sys.stdout.buffer
        ):
            await asyncio.Event().wait()


# Install required dependencies
def install_dependencies():
    """Install required dependencies for MCP server"""
    try:
        import subprocess
        packages = ["asyncpg", "httpx", "python-dotenv"]
        for package in packages:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print("Dependencies installed successfully")
    except Exception as e:
        print(f"Error installing dependencies: {e}")


if __name__ == "__main__":
    # Install dependencies if needed
    try:
        import asyncpg
        import httpx
    except ImportError:
        install_dependencies()
    
    # Run the server
    server = AdTaoMCPServer()
    asyncio.run(server.run()) 