"""
Interactive terminal test for the PCC/CVR guided conversational flow.

Run:  python3 tests/test_flow.py
Commands:
  restart  — clear session and start over
  exit     — quit
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.retrieval.conversation_state import create_session
from app.retrieval.flow_engine import start_flow, process_message


# ─── Flow detection ───────────────────────────────────────────────────────────

def detect_flow(msg: str) -> str | None:
    n = msg.lower()
    if "pcc" in n or "police clearance" in n or "clearance certificate" in n:
        return "pcc"
    if "cvr" in n or "character verification" in n:
        return "cvr"
    if "stolen" in n or "mv theft" in n or "vehicle theft" in n or "file fir" in n or "e-fir" in n:
        return "mv_theft"
    if "lost" in n or "found" in n or "lost report" in n:
        return "lost_report"
    return None


# ─── REPL ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 64)
    print("  PCC / CVR Guided Conversational Flow — Test Interface")
    print("=" * 64)
    print("Say 'I need a PCC' or 'I need a CVR' to begin.")
    print("Say 'restart' to reset, 'exit' to quit.\n")

    session = None

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            break

        if user_input.lower() == "restart":
            session = None
            print("\nBot: Session cleared. What do you need — PCC or CVR?\n")
            continue

        # No active session (or previous one finished) — detect new flow
        if session is None or session.complete:
            flow = detect_flow(user_input)
            if flow is None:
                print(
                    "\nBot: I can help with:\n"
                    "  • PCC (Police Clearance Certificate) — say 'I need a PCC'\n"
                    "  • CVR (Character Verification Report) — say 'I need a CVR'\n"
                )
                continue
            session = create_session(flow)
            response = start_flow(session)
            print(f"\nBot: {response}\n")
            continue

        response = process_message(session, user_input)
        print(f"\nBot: {response}\n")


if __name__ == "__main__":
    main()
