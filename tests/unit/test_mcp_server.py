import pytest
from mcp_server.server import MCPServer, MCPToolRequest


@pytest.fixture
def mcp_server():
    return MCPServer()


class TestMCPServer:
    def test_tool_discovery(self, mcp_server):
        tools = mcp_server.list_tools()
        
        assert len(tools) >= 10
        tool_names = [t["name"] for t in tools]
        assert "fhir_search" in tool_names
        assert "clinical_score_news2" in tool_names
        assert "drug_interaction_check" in tool_names
        assert "protocol_get" in tool_names
        assert "alert_dispatch" in tool_names

    @pytest.mark.asyncio
    async def test_news2_calculation(self, mcp_server):
        request = MCPToolRequest(
            tool="clinical_score_news2",
            arguments={
                "vitals": {
                    "heart_rate": 130,
                    "systolic_bp": 85,
                    "respiratory_rate": 28,
                    "temperature": 39.2,
                    "spo2": 87,
                }
            }
        )
        
        response = await mcp_server.execute_tool(request)
        
        assert response.success == True
        assert response.result["score"] >= 10
        assert response.result["risk_level"] in ["CRITICAL", "HIGH"]

    @pytest.mark.asyncio
    async def test_qsofa_calculation(self, mcp_server):
        request = MCPToolRequest(
            tool="clinical_score_qsofa",
            arguments={
                "vitals": {
                    "respiratory_rate": 26,
                    "systolic_bp": 90,
                    "gcs": 15,
                }
            }
        )
        
        response = await mcp_server.execute_tool(request)
        
        assert response.success == True
        assert response.result["score"] >= 2

    @pytest.mark.asyncio
    async def test_unknown_tool(self, mcp_server):
        request = MCPToolRequest(
            tool="nonexistent_tool",
            arguments={}
        )
        
        response = await mcp_server.execute_tool(request)
        
        assert response.success == False
        assert response.error is not None
        assert "Unknown" in response.error

    @pytest.mark.asyncio
    async def test_execution_timing(self, mcp_server):
        request = MCPToolRequest(
            tool="discover",
            arguments={}
        )
        
        response = await mcp_server.execute_tool(request)
        
        assert response.success == True
        assert response.execution_time_ms is not None
        assert response.execution_time_ms >= 0
