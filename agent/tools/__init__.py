from .calculator import TOOL as CALCULATOR_TOOL
from .registry import Tool, ToolContext, ToolRegistry, ToolResult
from .search import TOOL as SEARCH_TOOL
from .todo import TOOL as TODO_TOOL
from .weather import TOOL as WEATHER_TOOL


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool in (CALCULATOR_TOOL, SEARCH_TOOL, TODO_TOOL, WEATHER_TOOL):
        registry.register(tool)
    return registry
