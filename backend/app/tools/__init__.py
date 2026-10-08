from app.tools.base import BaseTool, ToolContext, ToolRisk
from app.tools.registry import ToolRegistry
from app.tools.service_tools import GetServiceStatusTool, GetServiceMetricsTool
from app.tools.incident_tools import (
    QueryIncidentsTool,
    GetIncidentTool,
    AddIncidentCommentTool,
    CreateIncidentTool,
)
from app.tools.rag_tools import SearchKnowledgeBaseTool
from app.tools.database_tools import GetDatabaseStatsTool


def get_default_tool_registry() -> ToolRegistry:
    """Factory helper providing a pre-populated central ToolRegistry."""
    registry = ToolRegistry()
    registry.register(GetServiceStatusTool())
    registry.register(GetServiceMetricsTool())
    registry.register(QueryIncidentsTool())
    registry.register(GetIncidentTool())
    registry.register(AddIncidentCommentTool())
    registry.register(CreateIncidentTool())
    registry.register(SearchKnowledgeBaseTool())
    registry.register(GetDatabaseStatsTool())
    return registry


__all__ = [
    "BaseTool",
    "ToolContext",
    "ToolRisk",
    "ToolRegistry",
    "get_default_tool_registry",
    "GetServiceStatusTool",
    "GetServiceMetricsTool",
    "QueryIncidentsTool",
    "GetIncidentTool",
    "AddIncidentCommentTool",
    "CreateIncidentTool",
    "SearchKnowledgeBaseTool",
    "GetDatabaseStatsTool",
]
