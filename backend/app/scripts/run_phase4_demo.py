import asyncio
import json
from app.db.session import async_session_factory
from app.agents.graph import run_agent_workflow


async def main():
    queries = [
        "Why is payment-service experiencing database connection exhaustion?",
        "Investigate the recent Kafka consumer lag spike on payment-events topic.",
        "Create a high-severity incident for payment-service database exhaustion.",
    ]

    print("=========================================================================")
    print("PHASE 4: REAL TOOL CALLING & AUTONOMOUS AGENT EXECUTION DEMO")
    print("=========================================================================\n")

    for i, query in enumerate(queries, 1):
        print(f"==================================================")
        print(f"SCENARIO {i}: \"{query}\"")
        print(f"==================================================")
        async with async_session_factory() as session:
            result = await run_agent_workflow(
                user_request=query,
                conversation_id=f"phase4-demo-conv-{i}",
                session=session,
            )
            print(f"Run ID: {result.id}")
            print(f"Execution Status: {result.status}")
            print(f"Total Latency: {result.total_latency_ms} ms")
            print(f"Tools Used ({len(result.tools_used)}): {', '.join(result.tools_used) if result.tools_used else 'None'}")
            print(f"Total Tool Calls Executed: {result.number_of_tool_calls}")
            print(f"Events Emitted: {len(result.events)}")
            print(f"Node Path: {' -> '.join(ev.node_name for ev in result.events)}")
            
            if result.tool_executions:
                print("\nTool Executions Log:")
                for te in result.tool_executions:
                    print(f"  - Tool: {te.tool_name:<24} Status: {te.status:<18} Latency: {te.latency_ms}ms")
                    print(f"    Input:  {te.tool_input}")
                    if te.tool_output:
                        out_str = str(te.tool_output)
                        print(f"    Output: {out_str[:120]}..." if len(out_str) > 120 else f"    Output: {out_str}")
                    if te.error:
                        print(f"    Error:  {te.error}")

            print(f"\nFinal Response:\n{result.final_answer}")
            print("\n")


if __name__ == "__main__":
    asyncio.run(main())
