import abc
from enum import Enum
from typing import Any, Dict, Generic, Optional, Type, TypeVar
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession


class ToolRisk(str, Enum):
    READ = "READ"
    WRITE = "WRITE"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExecutionPolicy(str, Enum):
    ASSISTED = "ASSISTED"
    AUTONOMOUS = "AUTONOMOUS"


class ToolContext(BaseModel):
    """Execution context injected into tools when executed."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    session: Optional[AsyncSession] = None
    run_id: Optional[str] = None
    user_request: Optional[str] = None
    execution_policy: ExecutionPolicy = ExecutionPolicy.ASSISTED
    is_pre_approved: bool = False
    approved_by: Optional[str] = None


InT = TypeVar("InT", bound=BaseModel)
OutT = TypeVar("OutT", bound=BaseModel)


class BaseTool(abc.ABC, Generic[InT, OutT]):
    """Abstract base class for all typed AgentOps operational tools."""

    name: str
    description: str
    input_schema: Type[InT]
    output_schema: Type[OutT]
    risk_type: ToolRisk = ToolRisk.READ
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    allowed_in_autonomous: bool = True

    @property
    def risk_classification(self) -> ToolRisk:
        return self.risk_type

    def sanitize_input(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize input before logging or DB persistence.
        Removes credentials, API keys, and sensitive tokens.
        """
        sanitized = dict(tool_input)
        sensitive_keys = {"password", "secret", "token", "api_key", "key", "authorization", "auth"}
        for k in list(sanitized.keys()):
            if any(s in k.lower() for s in sensitive_keys):
                sanitized[k] = "******"
        return sanitized

    def get_definition(self) -> Dict[str, Any]:
        """Returns JSON schema definition formatted for LLM function/tool calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema.model_json_schema(),
            },
        }

    @abc.abstractmethod
    async def execute(self, params: InT, context: ToolContext) -> OutT:
        """Executes the tool with validated Pydantic parameters."""
        pass
