import time
from typing import Any, Dict, List, Optional
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.tools.base import BaseTool, ToolContext, ToolRisk, RiskLevel, ExecutionPolicy

logger = get_logger(__name__)


class ToolRegistry:
    """Central registry enforcing validation, permissions, and safe tool execution."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a new operational tool."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting already registered tool: {tool.name}")
        self._tools[tool.name] = tool
        logger.info(
            f"Registered tool '{tool.name}' (Type: {tool.risk_type.value}, "
            f"Level: {tool.risk_level.value}, Requires Approval: {tool.requires_approval}, "
            f"Auto-Allowed: {tool.allowed_in_autonomous})"
        )

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieve tool by exact name."""
        return self._tools.get(name)

    def list_available(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_definitions(self) -> List[Dict[str, Any]]:
        """Get OpenAI-compatible function definitions for all registered tools."""
        return [tool.get_definition() for tool in self._tools.values()]

    def validate_args(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Validates arguments against the tool's Pydantic input schema."""
        tool = self.get(tool_name)
        if not tool:
            raise ValueError(f"Unknown tool '{tool_name}'. Available tools: {self.list_available()}")
        return tool.input_schema.model_validate(args)

    async def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        context: Optional[ToolContext] = None,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """
        Executes a registered tool securely with validation, error handling, risk policy gates, and transient retries.
        """
        tool = self.get(name)
        if not tool:
            return {
                "status": "FAILED",
                "output": None,
                "error": f"Tool '{name}' is not registered in the system.",
                "latency_ms": 0.0,
                "requires_approval": False,
            }

        ctx = context or ToolContext()
        policy = ctx.execution_policy or ExecutionPolicy(settings.EXECUTION_POLICY)

        # 1. Authorization & Human Approval Policy Gate:
        # If the execution is explicitly pre-approved by a human decision, bypass the gate
        is_authorized = False
        if ctx.is_pre_approved:
            is_authorized = True
            logger.info(f"Tool '{name}' executing with pre-authorized human approval by '{ctx.approved_by}'.")
        elif policy == ExecutionPolicy.AUTONOMOUS and tool.allowed_in_autonomous:
            is_authorized = True
            logger.info(f"Tool '{name}' authorized automatically under AUTONOMOUS execution policy.")
        elif not tool.requires_approval:
            is_authorized = True

        if not is_authorized:
            logger.warning(
                f"Execution of sensitive tool '{name}' intercepted: requires human approval "
                f"(Risk: {tool.risk_level.value}, Policy: {policy.value})."
            )
            return {
                "status": "PENDING_APPROVAL",
                "output": None,
                "error": f"Tool '{name}' is a sensitive operation and requires human approval before execution.",
                "latency_ms": 0.0,
                "requires_approval": True,
            }

        # 2. Validate arguments against Pydantic schema
        try:
            validated_params = tool.input_schema.model_validate(arguments)
        except ValidationError as e:
            logger.error(f"Validation error for tool '{name}': {e}")
            return {
                "status": "FAILED",
                "output": None,
                "error": f"Invalid arguments for tool '{name}': {str(e)}",
                "latency_ms": 0.0,
                "requires_approval": False,
            }

        start_t = time.perf_counter()
        last_error: Optional[Exception] = None

        # 3. Execution with transient retries
        for attempt in range(max_retries + 1):
            try:
                output_model = await tool.execute(validated_params, ctx)
                duration_ms = (time.perf_counter() - start_t) * 1000
                return {
                    "status": "SUCCESS",
                    "output": output_model.model_dump(),
                    "error": None,
                    "latency_ms": round(duration_ms, 2),
                    "requires_approval": False,
                }
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1}/{max_retries + 1} failed for tool '{name}': {e}")
                if attempt < max_retries:
                    continue

        duration_ms = (time.perf_counter() - start_t) * 1000
        return {
            "status": "FAILED",
            "output": None,
            "error": f"Execution error in tool '{name}': {str(last_error)}",
            "latency_ms": round(duration_ms, 2),
            "requires_approval": False,
        }
