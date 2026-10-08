import asyncio
import json
from app.db.session import async_session_factory
from app.agents.graph import run_agent_workflow
from app.models.agent import AgentRun, AgentEvent
from sqlalchemy import select
from sqlalchemy.orm import selectinload


async def main():
    queries = [
        "Payment-service error rate is surging above 5% and transactions are timing out with connection errors.",
        "Kafka consumer lag on payment-events topic has exceeded 50,000 messages. How do we remediate this?",
        "Redis cache latency spiked to 200ms and memory utilization reached 95%. What is the diagnostic runbook?",
    ]

    print("=================================================================")
    print("EXECUTING REALISTIC OPERATIONAL QUERIES VIA LANGGRAPH WORKFLOW")
    print("=================================================================\n")

    for i, query in enumerate(queries, 1):
        print(f"--- Query {i}: {query} ---")
        async with async_session_factory() as session:
            result = await run_agent_workflow(
                user_request=query,
                conversation_id=f"demo-conv-{i}",
                session=session,
            )
            print(f"Run ID: {result.id}")
            print(f"Status: {result.status}")
            print(f"Latency: {result.total_latency_ms} ms")
            print(f"Plan Summary: {result.plan.get('task_summary') if result.plan else 'N/A'}")
            print(f"Steps Count: {len(result.plan.get('steps', [])) if result.plan else 0}")
            print(f"Events Emitted: {len(result.events)}")
            print(f"Node Path: {' -> '.join(ev.node_name for ev in result.events)}")
            print(f"Final Answer Snippet:\n{result.final_answer[:200]}...")
            print("\n")


if __name__ == "__main__":
    asyncio.run(main())
