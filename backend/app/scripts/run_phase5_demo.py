import asyncio
import json
import uuid
from sqlalchemy import select
from app.db.session import async_session_factory
from app.agents.graph import run_agent_workflow, resume_agent_workflow
from app.models.approval import Approval
from app.models.incident import Incident
from app.models.agent import ToolExecution


async def main():
    print("=========================================================================")
    print("PHASE 5: HUMAN APPROVAL WORKFLOW & RESUMPTION DEMO")
    print("=========================================================================\n")

    # -------------------------------------------------------------
    # SCENARIO 1: Pure READ operations (No approval needed)
    # -------------------------------------------------------------
    print("==================================================")
    print("SCENARIO 1: \"Investigate payment-service database exhaustion and summarize root cause.\"")
    print("==================================================")
    async with async_session_factory() as session:
        res1 = await run_agent_workflow(
            user_request="Investigate payment-service database exhaustion and summarize root cause.",
            conversation_id="phase5-demo-1",
            session=session,
        )
        print(f"Run ID: {res1.id}")
        print(f"Execution Status: {res1.status} (Expected: COMPLETED)")
        print(f"Tools Used ({len(res1.tools_used)}): {', '.join(res1.tools_used)}")
        print(f"Total Tool Calls: {res1.number_of_tool_calls}")
        print(f"Events Emitted: {len(res1.events)}")
        print(f"Final Response Snippet:\n{res1.final_answer[:160]}...\n")

    # -------------------------------------------------------------
    # SCENARIO 2: Add Incident Comment (WRITE -> WAITING_APPROVAL -> APPROVE)
    # -------------------------------------------------------------
    print("==================================================")
    print("SCENARIO 2: \"Investigate payment-service issue and add an investigation comment.\"")
    print("==================================================")
    async with async_session_factory() as session:
        res2 = await run_agent_workflow(
            user_request="Investigate payment-service issue and add an investigation comment.",
            conversation_id="phase5-demo-2",
            session=session,
        )
        print(f"Initial Run ID: {res2.id}")
        print(f"Initial Status: {res2.status} (Expected: WAITING_APPROVAL)")
        print(f"Tools Used: {', '.join(res2.tools_used)}")
        
        # Look up pending approval in PostgreSQL
        appr_stmt = select(Approval).where(Approval.run_id == res2.id)
        apprs = (await session.execute(appr_stmt)).scalars().all()
        if apprs:
            appr = apprs[0]
            print(f"Approval Intercepted: ID={appr.id}, Tool={appr.tool_name}, Status={appr.status}")
            
            # Simulate Human Approval
            print("\n>>> Simulating Human Decision: APPROVE (decided_by='Lead-SRE-Alice')")
            appr.status = "APPROVED"
            appr.decided_by = "Lead-SRE-Alice"
            await session.commit()

            res2_resumed = await resume_agent_workflow(
                run_id=res2.id,
                approval_id=appr.id,
                decision="APPROVED",
                decided_by="Lead-SRE-Alice",
                session=session,
            )
            print(f"Resumed Run Status: {res2_resumed.status} (Expected: COMPLETED)")
            print(f"Total Tool Executions: {res2_resumed.number_of_tool_calls}")
            print(f"Events Emitted: {len(res2_resumed.events)}")
            print(f"Final Response Snippet:\n{res2_resumed.final_answer[:160]}...\n")

    # -------------------------------------------------------------
    # SCENARIO 3: Create Incident (WRITE -> WAITING_APPROVAL -> REJECT)
    # -------------------------------------------------------------
    print("==================================================")
    print("SCENARIO 3: \"Create a high-severity incident for the payment-service outage.\" (REJECTED)")
    print("==================================================")
    async with async_session_factory() as session:
        res3 = await run_agent_workflow(
            user_request="Create a high-severity incident for the payment-service outage.",
            conversation_id="phase5-demo-3",
            session=session,
        )
        print(f"Initial Run ID: {res3.id}")
        print(f"Initial Status: {res3.status} (Expected: WAITING_APPROVAL)")

        apprs = (await session.execute(select(Approval).where(Approval.run_id == res3.id))).scalars().all()
        if apprs:
            appr = apprs[0]
            print(f"Approval Intercepted: ID={appr.id}, Tool={appr.tool_name}, Status={appr.status}")
            
            # Simulate Human Rejection
            print("\n>>> Simulating Human Decision: REJECT (reason='Duplicate ticket already open: INC-404')")
            appr.status = "REJECTED"
            appr.decided_by = "Ops-Manager-Bob"
            appr.rejection_reason = "Duplicate ticket already open: INC-404"
            await session.commit()

            res3_resumed = await resume_agent_workflow(
                run_id=res3.id,
                approval_id=appr.id,
                decision="REJECTED",
                decided_by="Ops-Manager-Bob",
                rejection_reason="Duplicate ticket already open: INC-404",
                session=session,
            )
            print(f"Resumed Run Status: {res3_resumed.status} (Expected: COMPLETED)")
            print(f"Final Response Snippet:\n{res3_resumed.final_answer[:160]}...\n")

    # -------------------------------------------------------------
    # SCENARIO 4: Create Incident (WRITE -> WAITING_APPROVAL -> APPROVE -> DB Verify)
    # -------------------------------------------------------------
    print("==================================================")
    print("SCENARIO 4: \"Create a high-severity incident for the payment-service outage.\" (APPROVED & COMMITTED)")
    print("==================================================")
    async with async_session_factory() as session:
        res4 = await run_agent_workflow(
            user_request="Create a high-severity incident for the payment-service outage.",
            conversation_id="phase5-demo-4",
            session=session,
        )
        print(f"Initial Run ID: {res4.id}")
        print(f"Initial Status: {res4.status} (Expected: WAITING_APPROVAL)")

        apprs = (await session.execute(select(Approval).where(Approval.run_id == res4.id))).scalars().all()
        if apprs:
            appr = apprs[0]
            print(f"Approval Intercepted: ID={appr.id}, Tool={appr.tool_name}, Status={appr.status}")
            
            # Simulate Human Approval
            print("\n>>> Simulating Human Decision: APPROVE (decided_by='VP-Engineering')")
            appr.status = "APPROVED"
            appr.decided_by = "VP-Engineering"
            await session.commit()

            res4_resumed = await resume_agent_workflow(
                run_id=res4.id,
                approval_id=appr.id,
                decision="APPROVED",
                decided_by="VP-Engineering",
                session=session,
            )
            print(f"Resumed Run Status: {res4_resumed.status} (Expected: COMPLETED)")
            
            # Verify Incident in PostgreSQL table
            inc_stmt = select(Incident).order_by(Incident.created_at.desc())
            latest_inc = (await session.execute(inc_stmt)).scalars().first()
            if latest_inc:
                print(f"PostgreSQL Incident Created: ID={latest_inc.id}, Title='{latest_inc.title}', Severity={latest_inc.severity}")

            print(f"\nFinal Response Snippet:\n{res4_resumed.final_answer[:200]}...\n")


if __name__ == "__main__":
    asyncio.run(main())
