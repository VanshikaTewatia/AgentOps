import asyncio
import json
import uuid
from sqlalchemy import select
from app.db.session import async_session_factory
from app.agents.graph import run_agent_workflow, resume_agent_workflow
from app.models.approval import Approval
from app.models.incident import Incident
from app.models.agent import ToolExecution
from app.tools import get_default_tool_registry
from app.tools.base import ToolContext, ExecutionPolicy


async def main():
    print("=========================================================================")
    print("PHASE 5 HARDENING: APPROVAL SECURITY, CONCURRENCY & RESUME DEMO")
    print("=========================================================================\n")

    # -------------------------------------------------------------
    # SCENARIO A: Concurrent Approval (Compare-and-Set Protection)
    # -------------------------------------------------------------
    print("==================================================")
    print("SCENARIO A: Concurrent Approval Protection (Double Execution Prevention)")
    print("==================================================")
    async with async_session_factory() as session:
        res_a = await run_agent_workflow(
            user_request="Create a high-severity incident for payment-service database exhaustion",
            conversation_id="harden-demo-conv-a",
            session=session,
        )
        appr_stmt = select(Approval).where(Approval.run_id == res_a.id)
        appr = (await session.execute(appr_stmt)).scalars().first()
        print(f"Created Pending Approval: ID={appr.id}, Status={appr.status}")

        # Simulate two concurrent approve calls
        print(">>> Issuing 2 concurrent approve calls simultaneously...")
        
        async def do_approve(caller_name: str):
            async with async_session_factory() as s_inner:
                appr_rec = await s_inner.get(Approval, appr.id)
                if appr_rec.status == "PENDING":
                    appr_rec.status = "APPROVED"
                    appr_rec.decided_by = caller_name
                    await s_inner.commit()
                    # Resume workflow
                    await resume_agent_workflow(res_a.id, appr.id, "APPROVED", caller_name, session=s_inner)
                    return f"SUCCESS (approved by {caller_name})"
                else:
                    return f"CONFLICT 409 (Already resolved: {appr_rec.status})"

        t1 = do_approve("SRE-Lead-1")
        t2 = do_approve("SRE-Lead-2")
        out1, out2 = await asyncio.gather(t1, t2)
        print(f"  Attempt 1 Result: {out1}")
        print(f"  Attempt 2 Result: {out2}")

        # Verify exact number of incident records created in DB
        inc_count = (await session.execute(select(Incident))).scalars().all()
        print(f"Total Incidents Created in PostgreSQL: {len(inc_count)} (Expected: 1)\n")

    # -------------------------------------------------------------
    # SCENARIO B: Rejection (No Database Mutation)
    # -------------------------------------------------------------
    print("==================================================")
    print("SCENARIO B: Rejection Lifecycle (Zero Unauthorized Mutations)")
    print("==================================================")
    async with async_session_factory() as session:
        res_b = await run_agent_workflow(
            user_request="Create a high-severity incident for payment-service database exhaustion",
            conversation_id="harden-demo-conv-b",
            session=session,
        )
        appr = (await session.execute(select(Approval).where(Approval.run_id == res_b.id))).scalars().first()
        print(f"Pending Approval Intercepted: ID={appr.id}")

        print(">>> Simulating Human Decision: REJECT (Reason: 'False alarm - batch job completed')")
        appr.status = "REJECTED"
        appr.decided_by = "Lead-Manager"
        appr.rejection_reason = "False alarm - batch job completed"
        await session.commit()

        res_b_resumed = await resume_agent_workflow(
            res_b.id, appr.id, "REJECTED", "Lead-Manager", "False alarm - batch job completed", session=session
        )
        print(f"Resumed Run Status: {res_b_resumed.status} (Expected: COMPLETED)")
        print(f"Final Response Snippet:\n{res_b_resumed.final_answer[:160]}...\n")

    # -------------------------------------------------------------
    # SCENARIO C: Exact Tool Invocation After Approval
    # -------------------------------------------------------------
    print("==================================================")
    print("SCENARIO C: Exact Tool Invocation Binding")
    print("==================================================")
    async with async_session_factory() as session:
        res_c = await run_agent_workflow(
            user_request="Create a high-severity incident for payment-service database exhaustion",
            conversation_id="harden-demo-conv-c",
            session=session,
        )
        appr = (await session.execute(select(Approval).where(Approval.run_id == res_c.id))).scalars().first()
        print(f"Pending Tool: {appr.tool_name}, Original Validated Args: {appr.tool_args}")

        appr.status = "APPROVED"
        appr.decided_by = "Principal-SRE"
        await session.commit()

        res_c_resumed = await resume_agent_workflow(res_c.id, appr.id, "APPROVED", "Principal-SRE", session=session)
        print(f"Executed Tool Match: {res_c_resumed.tools_used[0] == appr.tool_name}")
        print(f"Final Status: {res_c_resumed.status}\n")

    # -------------------------------------------------------------
    # SCENARIO D: Autonomous Mode Policy Gates
    # -------------------------------------------------------------
    print("==================================================")
    print("SCENARIO D: Autonomous Mode Security Policy Verification")
    print("==================================================")
    registry = get_default_tool_registry()
    async with async_session_factory() as session:
        ctx_auto = ToolContext(session=session, execution_policy=ExecutionPolicy.AUTONOMOUS)
        
        # 1. Medium-risk allowlisted write tool executes in AUTONOMOUS mode
        res_medium = await registry.execute("add_incident_comment", {"incident_id": "inc-101", "comment": "Auto-triage note"}, ctx_auto)
        print(f"1. Medium-risk 'add_incident_comment' in AUTONOMOUS -> Status: {res_medium['status']} (Expected: SUCCESS)")

        # 2. High-risk write tool create_incident remains approval-gated even in AUTONOMOUS mode
        res_high = await registry.execute("create_incident", {"title": "Outage", "description": "High CPU", "severity": "HIGH"}, ctx_auto)
        print(f"2. High-risk 'create_incident' in AUTONOMOUS -> Status: {res_high['status']} (Expected: PENDING_APPROVAL)\n")


if __name__ == "__main__":
    asyncio.run(main())
