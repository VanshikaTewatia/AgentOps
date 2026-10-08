import abc
import json
import re
import uuid
from typing import Any, Dict, List, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.agent import Plan, PlanStep, ToolCallData, DelegationPlan, SpecialistTask

logger = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMClient(abc.ABC):
    """Abstract interface for LLM calls with optional structured JSON schema generation and tool calling."""

    @abc.abstractmethod
    async def generate_text(
        self,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate freeform completion."""
        pass

    @abc.abstractmethod
    async def generate_structured(
        self,
        messages: List[Dict[str, Any]],
        response_model: Type[T],
        temperature: Optional[float] = None,
    ) -> T:
        """Generate structured output validated against a Pydantic model."""
        pass

    @abc.abstractmethod
    async def decide_tool_calls(
        self,
        messages: List[Dict[str, Any]],
        tools_definitions: List[Dict[str, Any]],
        temperature: Optional[float] = None,
    ) -> List[ToolCallData]:
        """Generate structured tool calls based on context and tool schemas."""
        pass


class MockLLMClient(LLMClient):
    """Deterministic offline LLM simulator generating compliant technical plans, tool calls, and analyses."""

    async def generate_text(
        self,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        user_message = ""
        for m in reversed(messages):
            if m.get("role") in ("user", "human"):
                user_message = str(m.get("content", ""))
                break
        return (
            f"[AGENTOPS Synthesis] Multi-Agent Investigation concluded for: '{user_message[:100]}'\n"
            f"The investigation confirmed root causes and synthesized specialist findings."
        )

    async def generate_structured(
        self,
        messages: List[Dict[str, Any]],
        response_model: Type[T],
        temperature: Optional[float] = None,
    ) -> T:
        user_content = ""
        for m in reversed(messages):
            if m.get("role") in ("user", "human"):
                user_content = str(m.get("content", ""))
                break
        lower_content = user_content.lower()

        if response_model == DelegationPlan:
            # Multi-agent dynamic supervisor delegation routing
            if "create" in lower_content and "incident" in lower_content:
                tasks = [
                    SpecialistTask(
                        task_id=f"task-{uuid.uuid4().hex[:6]}",
                        target_agent="IncidentAgent",
                        task_description="Create a formal high-severity incident ticket for infrastructure outage",
                        required_tools=["create_incident"],
                    )
                ]
                return DelegationPlan(
                    plan_summary="Delegate incident ticket creation to IncidentAgent",
                    tasks=tasks,
                    estimated_impact="HIGH",
                )  # type: ignore

            if "add" in lower_content and "comment" in lower_content:
                tasks = [
                    SpecialistTask(
                        task_id=f"task-{uuid.uuid4().hex[:6]}",
                        target_agent="DiagnosticAgent",
                        task_description="Inspect health status and active metrics for payment-service",
                        required_tools=["get_service_status"],
                    ),
                    SpecialistTask(
                        task_id=f"task-{uuid.uuid4().hex[:6]}",
                        target_agent="IncidentAgent",
                        task_description="Add triage and root-cause mitigation comment to incident record",
                        required_tools=["add_incident_comment"],
                    ),
                ]
                return DelegationPlan(
                    plan_summary="Delegate service inspection to DiagnosticAgent and triage commenting to IncidentAgent",
                    tasks=tasks,
                    estimated_impact="MEDIUM",
                )  # type: ignore

            if "kafka" in lower_content and ("runbook" in lower_content or "recommend" in lower_content):
                tasks = [
                    SpecialistTask(
                        task_id=f"task-{uuid.uuid4().hex[:6]}",
                        target_agent="KnowledgeAgent",
                        task_description="Search Kafka runbooks for consumer lag mitigation procedures",
                        required_tools=["search_knowledge_base"],
                    ),
                ]
                return DelegationPlan(
                    plan_summary="Delegate runbook inquiry to KnowledgeAgent",
                    tasks=tasks,
                    estimated_impact="LOW",
                )  # type: ignore

            if "kafka" in lower_content or "lag" in lower_content:
                tasks = [
                    SpecialistTask(
                        task_id=f"task-{uuid.uuid4().hex[:6]}",
                        target_agent="DiagnosticAgent",
                        task_description="Fetch consumer lag metrics and partition errors for kafka",
                        required_tools=["get_service_metrics"],
                    ),
                    SpecialistTask(
                        task_id=f"task-{uuid.uuid4().hex[:6]}",
                        target_agent="KnowledgeAgent",
                        task_description="Retrieve kafka consumer lag remediation runbook",
                        required_tools=["search_knowledge_base"],
                    ),
                ]
                return DelegationPlan(
                    plan_summary="Delegate metrics inspection to DiagnosticAgent and runbook retrieval to KnowledgeAgent",
                    tasks=tasks,
                    estimated_impact="MEDIUM",
                )  # type: ignore

            if "payment" in lower_content or "connection" in lower_content or "exhaustion" in lower_content:
                tasks = [
                    SpecialistTask(
                        task_id=f"task-{uuid.uuid4().hex[:6]}",
                        target_agent="DiagnosticAgent",
                        task_description="Investigate payment-service health, connection metrics, and latency",
                        required_tools=["get_service_status", "get_service_metrics"],
                    ),
                    SpecialistTask(
                        task_id=f"task-{uuid.uuid4().hex[:6]}",
                        target_agent="KnowledgeAgent",
                        task_description="Retrieve database connection pool exhaustion troubleshooting runbook",
                        required_tools=["search_knowledge_base"],
                    ),
                ]
                return DelegationPlan(
                    plan_summary="Delegate telemetry analysis to DiagnosticAgent and runbook retrieval to KnowledgeAgent",
                    tasks=tasks,
                    estimated_impact="MEDIUM",
                )  # type: ignore

            # Fallback delegation: KnowledgeAgent
            tasks = [
                SpecialistTask(
                    task_id=f"task-{uuid.uuid4().hex[:6]}",
                    target_agent="KnowledgeAgent",
                    task_description=f"Retrieve operational documentation for inquiry: {user_content[:60]}",
                    required_tools=["search_knowledge_base"],
                )
            ]
            return DelegationPlan(
                plan_summary=f"Delegate inquiry to KnowledgeAgent: {user_content[:60]}",
                tasks=tasks,
                estimated_impact="LOW",
            )  # type: ignore

        if response_model == Plan:
            # Deterministically identify service & problem domain
            if "create" in lower_content and "incident" in lower_content:
                plan_steps = [
                    PlanStep(
                        step_number=1,
                        description="Request creation of high-severity incident ticket",
                        tool_required="create_incident",
                        requires_rag=False,
                        requires_human_approval=True,
                    ),
                ]
                return Plan(
                    task_summary="Create high-severity incident ticket for infrastructure alert",
                    steps=plan_steps,
                    estimated_impact="HIGH",
                )  # type: ignore

            if "add" in lower_content and "comment" in lower_content:
                plan_steps = [
                    PlanStep(
                        step_number=1,
                        description="Check current health and runtime status of payment-service",
                        tool_required="get_service_status",
                        requires_rag=False,
                        requires_human_approval=False,
                    ),
                    PlanStep(
                        step_number=2,
                        description="Append mitigation and triage comment to incident record",
                        tool_required="add_incident_comment",
                        requires_rag=False,
                        requires_human_approval=True,
                    ),
                ]
                return Plan(
                    task_summary="Investigate and append incident investigation comment",
                    steps=plan_steps,
                    estimated_impact="MEDIUM",
                )  # type: ignore

            if "payment" in lower_content or "connection" in lower_content:
                plan_steps = [
                    PlanStep(
                        step_number=1,
                        description="Check current health and runtime status of payment-service",
                        tool_required="get_service_status",
                        requires_rag=False,
                        requires_human_approval=False,
                    ),
                    PlanStep(
                        step_number=2,
                        description="Fetch database connection pool metrics and p99 latency stats",
                        tool_required="get_service_metrics",
                        requires_rag=False,
                        requires_human_approval=False,
                    ),
                    PlanStep(
                        step_number=3,
                        description="Query recent active incidents and alerts for payment-service",
                        tool_required="query_incidents",
                        requires_rag=False,
                        requires_human_approval=False,
                    ),
                    PlanStep(
                        step_number=4,
                        description="Retrieve database troubleshooting runbooks and connection pool guides",
                        tool_required="search_knowledge_base",
                        requires_rag=True,
                        requires_human_approval=False,
                    ),
                ]
                return Plan(
                    task_summary="Investigate payment-service incidents and database connection pool exhaustion",
                    steps=plan_steps,
                    estimated_impact="MEDIUM",
                )  # type: ignore

            if "kafka" in lower_content or "lag" in lower_content:
                plan_steps = [
                    PlanStep(
                        step_number=1,
                        description="Fetch consumer lag metrics for kafka service",
                        tool_required="get_service_metrics",
                        requires_rag=False,
                        requires_human_approval=False,
                    ),
                    PlanStep(
                        step_number=2,
                        description="Query active incident alerts for kafka partitions",
                        tool_required="query_incidents",
                        requires_rag=False,
                        requires_human_approval=False,
                    ),
                    PlanStep(
                        step_number=3,
                        description="Retrieve kafka consumer lag remediation runbook",
                        tool_required="search_knowledge_base",
                        requires_rag=True,
                        requires_human_approval=False,
                    ),
                ]
                return Plan(
                    task_summary="Investigate Kafka consumer lag spike and partition rebalances",
                    steps=plan_steps,
                    estimated_impact="MEDIUM",
                )  # type: ignore

            # Generic fallback plan
            plan_steps = [
                PlanStep(
                    step_number=1,
                    description=f"Retrieve operational documentation for request: {user_content[:60]}",
                    tool_required="search_knowledge_base",
                    requires_rag=True,
                    requires_human_approval=False,
                ),
                PlanStep(
                    step_number=2,
                    description="Analyze findings and produce structured resolution report",
                    tool_required=None,
                    requires_rag=False,
                    requires_human_approval=False,
                ),
            ]
            return Plan(
                task_summary=f"Investigate: {user_content[:80]}",
                steps=plan_steps,
                estimated_impact="LOW",
            )  # type: ignore

        # Fallback empty construction
        return response_model.model_validate({})

    async def decide_tool_calls(
        self,
        messages: List[Dict[str, Any]],
        tools_definitions: List[Dict[str, Any]],
        temperature: Optional[float] = None,
    ) -> List[ToolCallData]:
        """Deterministically determine which tool to invoke based on prompt/step context."""
        user_content = ""
        for m in reversed(messages):
            if m.get("role") in ("user", "human", "system"):
                user_content += " " + str(m.get("content", ""))

        lower = user_content.lower()
        tool_calls: List[ToolCallData] = []

        # Check for creation request
        if "create_incident" in lower or ("create" in lower and "incident" in lower):
            return [
                ToolCallData(
                    tool_call_id=f"call-{uuid.uuid4().hex[:6]}",
                    tool_name="create_incident",
                    tool_args={
                        "title": "Payment service DB connection pool exhaustion",
                        "description": "Database pool utilization exceeded 95% threshold causing transaction timeouts",
                        "severity": "HIGH",
                        "service": "payment-service",
                    },
                )
            ]

        # Check for add incident comment request
        if "add_incident_comment" in lower or ("add" in lower and "comment" in lower):
            return [
                ToolCallData(
                    tool_call_id=f"call-{uuid.uuid4().hex[:6]}",
                    tool_name="add_incident_comment",
                    tool_args={
                        "incident_id": "inc-8921-pay",
                        "comment": "Identified connection pool leak. Restarting pool workers.",
                    },
                )
            ]

        # Check for service status request
        if "get_service_status" in lower:
            svc_name = "payment-service" if "payment" in lower else "kafka" if "kafka" in lower else "redis" if "redis" in lower else "infrastructure"
            return [
                ToolCallData(
                    tool_call_id=f"call-{uuid.uuid4().hex[:6]}",
                    tool_name="get_service_status",
                    tool_args={"service": svc_name},
                )
            ]

        # Check for service metrics
        if "get_service_metrics" in lower or "metric" in lower:
            svc_name = "payment-service" if "payment" in lower else "kafka" if "kafka" in lower else "redis" if "redis" in lower else "infrastructure"
            return [
                ToolCallData(
                    tool_call_id=f"call-{uuid.uuid4().hex[:6]}",
                    tool_name="get_service_metrics",
                    tool_args={"service": svc_name, "timeframe": "last_30_minutes"},
                )
            ]

        # Check for incidents query
        if "query_incidents" in lower or "incident" in lower:
            svc_name = "payment-service" if "payment" in lower else "kafka" if "kafka" in lower else "redis" if "redis" in lower else None
            return [
                ToolCallData(
                    tool_call_id=f"call-{uuid.uuid4().hex[:6]}",
                    tool_name="query_incidents",
                    tool_args={"service": svc_name, "timeframe": "last_24_hours"},
                )
            ]

        # Check for knowledge search
        if "search_knowledge_base" in lower or "runbook" in lower or "troubleshoot" in lower:
            return [
                ToolCallData(
                    tool_call_id=f"call-{uuid.uuid4().hex[:6]}",
                    tool_name="search_knowledge_base",
                    tool_args={"query": user_content[:80], "top_k": 3},
                )
            ]

        return tool_calls


class OpenAILLMClient(LLMClient):
    """OpenAI or OpenAI-compatible LLM client with JSON schema enforcement and Tool Calling."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
    ):
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY must be provided when LLM_PROVIDER is 'openai'. "
                "Set OPENAI_API_KEY in your .env or environment variables."
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.default_temperature = temperature

    async def generate_text(
        self,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "temperature": temperature if temperature is not None else self.default_temperature,
            "messages": messages,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                logger.error(f"LLM API returned error: {e.response.text}")
                raise RuntimeError(f"LLM API error: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                logger.error(f"LLM request failed: {e}")
                raise RuntimeError(f"LLM connection error: {e}")

    async def generate_structured(
        self,
        messages: List[Dict[str, Any]],
        response_model: Type[T],
        temperature: Optional[float] = None,
    ) -> T:
        schema = response_model.model_json_schema()
        system_instruction = (
            f"You must output ONLY valid JSON adhering strictly to this JSON schema:\n"
            f"{json.dumps(schema, indent=2)}\n"
            f"Do not include markdown code fences (no ```json ... ```) or conversational filler."
        )

        formatted_messages = [{"role": "system", "content": system_instruction}] + messages
        raw_text = await self.generate_text(
            messages=formatted_messages,
            temperature=temperature if temperature is not None else 0.0,
        )

        clean_text = raw_text.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\n|\n```$", "", clean_text, flags=re.MULTILINE).strip()

        try:
            parsed_json = json.loads(clean_text)
            return response_model.model_validate(parsed_json)
        except Exception as e:
            logger.error(f"Failed to parse structured LLM response: {clean_text}. Error: {e}")
            raise ValueError(f"LLM response failed Pydantic validation: {e}")

    async def decide_tool_calls(
        self,
        messages: List[Dict[str, Any]],
        tools_definitions: List[Dict[str, Any]],
        temperature: Optional[float] = None,
    ) -> List[ToolCallData]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "temperature": temperature if temperature is not None else self.default_temperature,
            "messages": messages,
            "tools": tools_definitions,
            "tool_choice": "auto",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                message = data["choices"][0]["message"]
                
                raw_tool_calls = message.get("tool_calls", [])
                result: List[ToolCallData] = []
                for tc in raw_tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    fn_args_raw = fn.get("arguments", "{}")
                    try:
                        fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                    except Exception:
                        fn_args = {}
                    
                    result.append(
                        ToolCallData(
                            tool_call_id=tc.get("id", str(uuid.uuid4())),
                            tool_name=fn_name,
                            tool_args=fn_args,
                        )
                    )
                return result
            except Exception as e:
                logger.error(f"Failed to obtain tool calls from LLM: {e}")
                return []


def get_llm_client() -> LLMClient:
    """Factory to instantiate the configured LLM client."""
    provider = settings.LLM_PROVIDER.lower()
    if provider == "openai":
        return OpenAILLMClient(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
        )
    elif provider == "mock":
        return MockLLMClient()
    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{provider}'. Supported providers: 'mock', 'openai'."
        )
