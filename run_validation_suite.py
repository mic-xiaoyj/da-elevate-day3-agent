"""Automated Validation Suite for Module 3-3 Cymbal Operations Agent."""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Ensure clean environment
os.environ.pop("GOOGLE_API_CERTIFICATE_CONFIG", None)
os.environ.pop("CLOUDSDK_CONTEXT_AWARE_USE_CLIENT_CERTIFICATE", None)
load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from app.agent import root_agent

PROMPTS = [
    ("UC 1.1a Hardware Error",
     "What is the immediate field recovery protocol when a cashier encounters an ERR-PAY-4001 EMV contactless payment freeze, and how do we ensure the customer is not double-charged?"),
    ("UC 1.1c Out-of-Scope Hardware",
     "How do I replace the engine oil on a Ford F-150 truck?"),
    ("UC 1.2a Stockout Risk (<20h)",
     "What is the estimated cover hours remaining for store inventory positions experiencing stockout risk of less than 20 hours, and what is their total on-hand inventory?"),
    ("UC 1.3 Real-Time Cashier Metrics",
     "Read live 1-hour rolling metrics and audit status flags for Cashier CASH_1190 at Store 48."),
    ("UC 2.1a Warranty Transaction",
     "Check transaction details for TXN-20260312-0015811 and show the warranty coverage policy for the purchased item."),
    ("UC 2.2 Dual Cashier Baseline",
     "What is Cashier CASH_1190's live 1-hour override rate right now, compared to their 7-day historical override baseline?"),
    ("UC 2.3 Cross-Cloud Offender Audit",
     "Show cashiers with active cashier promo abuse alerts in the last 7 days and retrieve checkout logs for the top offender.")
]

async def run_suite():
    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        session_service=session_service,
        app_name="cymbal_operations_agent"
    )

    for title, prompt_text in PROMPTS:
        print("\n" + "=" * 80)
        print(f"▶ RUNNING: {title}")
        print(f"Prompt: {prompt_text}")
        print("-" * 80)

        session_id = f"session-{title.split()[1].replace('.', '_')}"
        session = await session_service.create_session(
            app_name="cymbal_operations_agent",
            session_id=session_id,
            user_id="lead_auditor"
        )

        user_msg = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text=prompt_text)]
        )

        tools_called = []
        final_texts = []

        try:
            events = runner.run_async(
                user_id="lead_auditor",
                session_id=session.id,
                new_message=user_msg,
            )
            async for event in events:
                if event.content and event.content.parts:
                    for p in event.content.parts:
                        if p.text:
                            final_texts.append(p.text)
                        elif p.function_call:
                            call_str = f"{p.function_call.name}({p.function_call.args})"
                            tools_called.append(call_str)
                            print(f"  [TOOL CALL] {call_str}")
                        elif p.function_response:
                            print(f"  [TOOL RESP] {p.function_response.name} done")

            print("\n[AGENT SYNTHESIS]:")
            full_text = "\n".join(final_texts)
            print(full_text[:800] + ("..." if len(full_text) > 800 else ""))
            print(f"\n✔ Summary: Tools invoked: {tools_called}")

        except Exception as e:
            print(f"❌ ERROR in {title}: {e}")

if __name__ == "__main__":
    asyncio.run(run_suite())
