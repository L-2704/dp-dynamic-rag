"""
Flow engine: guided conversational PCC/CVR/MV Theft/Lost Report slot-filling.

Handles question generation, free-text slot parsing, back-navigation
(including inline corrections like "go back, I meant Organization"), and
grounded final-answer generation via retrieval + Ollama.
"""

import re
from app.retrieval.conversation_state import Session
from app.retrieval.flow_config import (
    PCC_PURPOSES_INDIVIDUAL,
    PCC_PURPOSES_ORGANIZATION,
    VERIFICATION_MODES,
    MANDATORY_ADDR_ANTECEDENT_PURPOSES,
    MV_THEFT_ROLES,
    LOST_REPORT_TYPES,
)
from app.retrieval.retriever import retrieve
from app.retrieval.llm import generate_answer


PCC_STEPS = ["applicant_type", "pcc_type", "verification_mode"]
CVR_STEPS = ["is_govt_employee"]
MV_THEFT_STEPS = ["delhi_jurisdiction", "role", "has_reg_no"]
LOST_REPORT_STEPS = ["report_type", "criminal_suspicion"]


# ─── Text normalisation ───────────────────────────────────────────────────────

def _norm(text: str) -> str:
    return text.lower().strip().rstrip(".!?,")


# ─── Intent detection helpers ─────────────────────────────────────────────────

def _is_back(msg: str) -> bool:
    """True when user expresses a desire to go back or correct an earlier answer."""
    n = _norm(msg)
    return any(p in n for p in [
        "go back", "i meant", "scratch that", "no wait",
        "change my", "wait,", "wrong,", "actually",
    ])


def _detect_applicant_type(msg: str) -> str | None:
    n = _norm(msg)
    if "organization" in n or "organisation" in n:
        return "Organization"
    if "individual" in n or "personal" in n or "myself" in n:
        return "Individual"
    return None


def _detect_pcc_type(msg: str, purposes: list[str]) -> str | None:
    n = _norm(msg)
    stripped = n.strip()

    if stripped.isdigit():
        idx = int(stripped) - 1
        if 0 <= idx < len(purposes):
            return purposes[idx]

    for p in purposes:
        if stripped == p.lower():
            return p

    best, best_score = None, 0
    for p in purposes:
        tokens = [t.lower() for t in re.split(r"[/\s,]+", p) if len(t) > 3]
        score = sum(1 for t in tokens if t in n)
        if score > best_score:
            best_score, best = score, p

    return best if best_score > 0 else None


def _detect_verification_mode(msg: str) -> str | None:
    n = _norm(msg)
    stripped = n.strip()
    if stripped == "1" or "address" in n or "both" in n:
        return VERIFICATION_MODES[0]
    if stripped == "2" or "only" in n or "criminal" in n or (
        "antecedent" in n and "address" not in n
    ):
        return VERIFICATION_MODES[1]
    return None


def _detect_yes_no(msg: str) -> str | None:
    n = _norm(msg).strip()
    yes_words = {"yes", "y", "yeah", "yep", "yup", "correct", "sure", "true"}
    no_words = {"no", "n", "nope", "nah", "false"}
    if n in yes_words:
        return "yes"
    if n in no_words:
        return "no"
    words = set(n.split())
    if words & yes_words:
        return "yes"
    if words & no_words:
        return "no"
    return None


def _detect_role(msg: str) -> str | None:
    n = _norm(msg)
    if "duty" in n or "police" in n or "officer" in n or "official" in n:
        return MV_THEFT_ROLES[1]
    if "citizen" in n or "complainant" in n or "myself" in n or n == "me":
        return MV_THEFT_ROLES[0]
    return None


def _detect_report_type(msg: str) -> str | None:
    n = _norm(msg)
    if "found" in n:
        return "Found"
    if "lost" in n:
        return "Lost"
    return None


# ─── Question text generators ─────────────────────────────────────────────────

def _fmt_list(items: list[str]) -> str:
    return "\n".join(f"  {i + 1}. {item}" for i, item in enumerate(items))


def _ask_pcc(step: str, slots: dict) -> str:
    if step == "applicant_type":
        return "Are you applying as an **Individual** or as an **Organization**?"

    if step == "pcc_type":
        at = slots.get("applicant_type", "Individual")
        purposes = PCC_PURPOSES_INDIVIDUAL if at == "Individual" else PCC_PURPOSES_ORGANIZATION
        return (
            f"What is the purpose of your PCC application?\n"
            f"Here are the options available for **{at}**:\n\n"
            + _fmt_list(purposes)
            + "\n\nPlease type the number or name of your purpose."
        )

    if step == "verification_mode":
        return (
            "Which mode of verification do you need?\n\n"
            "  1. Address and Antecedent Verification\n"
            "  2. Antecedent Verification Only\n\n"
            "Type 1 or 2, or say the mode name."
        )

    return ""


def _ask_cvr(step: str, slots: dict) -> str:
    if step == "is_govt_employee":
        return (
            "CVR (Character Verification Report) is available **only for government employees** "
            "applying through a Ministry or State Government.\n\n"
            "Are you a government employee applying via a Ministry or State Government? "
            "(Yes / No)"
        )
    return ""


def _ask_mv_theft(step: str, slots: dict) -> str:
    if step == "delhi_jurisdiction":
        return "Was your motor vehicle stolen within the territorial jurisdiction of Delhi? (Yes / No)"

    if step == "role":
        return (
            "Are you registering this complaint as the **Citizen/Complainant**, or are you a "
            "**Police official** logging an offline station report? "
            "(Citizen/Complainant or Duty Officer/Police Official)"
        )

    if step == "has_reg_no":
        return "Do you have the vehicle's permanent Registration Number available? (Yes / No)"

    return ""


def _ask_lost_report(step: str, slots: dict) -> str:
    if step == "report_type":
        return (
            "Are you reporting an item you have **lost**, or recording an unclaimed article "
            "you have **found**? (Lost / Found)"
        )

    if step == "criminal_suspicion":
        return (
            "Does your lost item involve any suspicion of physical crime, theft, break-in, or "
            "snatched property? (No, simple loss / Yes, suspect theft)"
        )

    return ""


# ─── Slot parsers ─────────────────────────────────────────────────────────────

def _parse_pcc(step: str, msg: str, slots: dict) -> tuple[str | None, str | None]:
    if step == "applicant_type":
        v = _detect_applicant_type(msg)
        return (v, None) if v else (
            None, "Please reply with **Individual** or **Organization**."
        )

    if step == "pcc_type":
        at = slots.get("applicant_type", "Individual")
        purposes = PCC_PURPOSES_INDIVIDUAL if at == "Individual" else PCC_PURPOSES_ORGANIZATION
        v = _detect_pcc_type(msg, purposes)
        if v:
            return v, None
        return None, (
            "I didn't recognise that purpose. Please choose from the list:\n\n"
            + _fmt_list(purposes)
        )

    if step == "verification_mode":
        v = _detect_verification_mode(msg)
        return (v, None) if v else (
            None, "Please type **1** (Address & Antecedent Verification) or **2** (Antecedent Verification Only)."
        )

    return None, "Unknown step."


def _parse_cvr(step: str, msg: str, slots: dict) -> tuple[str | None, str | None]:
    if step == "is_govt_employee":
        v = _detect_yes_no(msg)
        return (v, None) if v else (None, "Please answer **Yes** or **No**.")
    return None, "Unknown step."


def _parse_mv_theft(step: str, msg: str, slots: dict) -> tuple[str | None, str | None]:
    if step == "delhi_jurisdiction":
        v = _detect_yes_no(msg)
        return (v, None) if v else (None, "Please answer **Yes** or **No**.")

    if step == "role":
        v = _detect_role(msg)
        return (v, None) if v else (
            None, "Please reply with **Citizen/Complainant** or **Duty Officer/Police Official**."
        )

    if step == "has_reg_no":
        v = _detect_yes_no(msg)
        return (v, None) if v else (None, "Please answer **Yes** or **No**.")

    return None, "Unknown step."


def _parse_lost_report(step: str, msg: str, slots: dict) -> tuple[str | None, str | None]:
    if step == "report_type":
        v = _detect_report_type(msg)
        return (v, None) if v else (None, "Please answer **Lost** or **Found**.")

    if step == "criminal_suspicion":
        v = _detect_yes_no(msg)
        return (v, None) if v else (None, "Please answer **Yes** or **No**.")

    return None, "Unknown step."


# ─── Final answer builders ────────────────────────────────────────────────────

def _pcc_breadcrumb(slots: dict) -> str:
    parts = [
        slots.get("applicant_type", ""),
        slots.get("pcc_type", ""),
        slots.get("verification_mode", ""),
    ]
    return " > ".join(p for p in parts if p)


def _pcc_final(session: Session) -> str:
    session.complete = True
    crumb = _pcc_breadcrumb(session.slots)
    query = "PCC applicant photo upload documents checklist step by step procedure apply new"
    chunks = retrieve(query, top_k=5)
    answer = generate_answer(query, chunks)
    return (
        f"**Your selections:** {crumb}\n\n"
        f"---\n\n"
        f"{answer}\n\n"
        f"---\n\n"
        f"**Reminder:** If your application is later rejected, you have a "
        f"**one-time option to raise a query** about the rejection."
    )


def _cvr_final(session: Session) -> str:
    session.complete = True
    query = "CVR character verification report government employee upload documents checklist procedure"
    chunks = retrieve(query, top_k=5)
    answer = generate_answer(query, chunks)
    return (
        f"**Character Verification Report (CVR) — Government Employees**\n\n"
        f"{answer}\n\n"
        f"---\n\n"
        f"**Reminder:** If your application is later rejected, you have a "
        f"**one-time option to raise a query** about the rejection."
    )


def _mv_theft_breadcrumb(slots: dict) -> str:
    parts = []
    if slots.get("delhi_jurisdiction"):
        parts.append("Delhi: " + slots["delhi_jurisdiction"])
    if slots.get("role"):
        parts.append("Role: " + slots["role"])
    if slots.get("has_reg_no"):
        parts.append("Reg No: " + slots["has_reg_no"])
    return " > ".join(parts)


def _mv_theft_final(session: Session) -> str:
    session.complete = True
    crumb = _mv_theft_breadcrumb(session.slots)
    role = session.slots.get("role", "")

    if role == MV_THEFT_ROLES[1]:
        query = "Duty Officer register FIR vehicle theft documents procedure complainant details"
    else:
        query = "register FIR vehicle theft complainant documents procedure vehicle details"

    chunks = retrieve(query, top_k=5)
    answer = generate_answer(query, chunks)
    return (
        f"**Your selections:** {crumb}\n\n"
        f"---\n\n"
        f"{answer}\n\n"
        f"---\n\n"
        f"**Note:** Your application enters 'Pending Investigation' status. If untraced, a final "
        f"report is automatically forwarded to the eCourt on the 21st day for insurance claim purposes."
    )


def _lost_report_final_lost(session: Session) -> str:
    session.complete = True
    query = "lost article report register LR number procedure"
    chunks = retrieve(query, top_k=3)
    answer = generate_answer(query, chunks)
    return (
        f"**Lost Article Report**\n\n"
        f"{answer}\n\n"
        f"---\n\n"
        f"**Note:** Lost Reports are purely informational records for administrative purposes "
        f"(e.g. re-issuing documents) and do not trigger a police investigation. You can retrieve "
        f"past reports anytime using your LR Number and registered Email ID."
    )


def _lost_report_final_found(session: Session) -> str:
    session.complete = True
    query = "found article register category serial number search upload photo description central database"
    chunks = retrieve(query, top_k=3)
    answer = generate_answer(query, chunks)
    return f"**Found Article Report**\n\n{answer}"


# ─── Back-navigation ──────────────────────────────────────────────────────────

def _pcc_go_back(session: Session, msg: str) -> str:
    steps = PCC_STEPS

    for i in range(session.current_step):
        v, _ = _parse_pcc(steps[i], msg, session.slots)
        if v is not None:
            session.slots[steps[i]] = v
            for s in steps[i + 1:]:
                session.slots.pop(s, None)
            session.current_step = i + 1

            if steps[i] == "pcc_type" and v.lower() in MANDATORY_ADDR_ANTECEDENT_PURPOSES:
                session.slots["verification_mode"] = VERIFICATION_MODES[0]
                return (
                    f"Since your purpose is **{v}**, the verification mode is "
                    f"automatically set to **Address and Antecedent Verification** "
                    f"— this is mandatory for Emigration (NRI-linked purposes).\n\n"
                    + _pcc_final(session)
                )

            if session.current_step >= len(steps):
                return _pcc_final(session)
            return _ask_pcc(steps[session.current_step], session.slots)

    if session.current_step > 0:
        session.current_step -= 1
        session.slots.pop(steps[session.current_step], None)
    return _ask_pcc(steps[session.current_step], session.slots)


def _mv_theft_go_back(session: Session, msg: str) -> str:
    steps = MV_THEFT_STEPS
    for i in range(session.current_step):
        v, _ = _parse_mv_theft(steps[i], msg, session.slots)
        if v is not None:
            session.slots[steps[i]] = v
            for s in steps[i + 1:]:
                session.slots.pop(s, None)
            session.current_step = i + 1
            if session.current_step >= len(steps):
                return _mv_theft_final(session)
            return _ask_mv_theft(steps[session.current_step], session.slots)

    if session.current_step > 0:
        session.current_step -= 1
        session.slots.pop(steps[session.current_step], None)
    return _ask_mv_theft(steps[session.current_step], session.slots)


# ─── Per-flow processors ──────────────────────────────────────────────────────

def _process_pcc(session: Session, msg: str) -> str:
    steps = PCC_STEPS
    idx = session.current_step

    if idx >= len(steps):
        return _pcc_final(session)

    val, err = _parse_pcc(steps[idx], msg, session.slots)

    if val is not None:
        session.slots[steps[idx]] = val
        session.current_step += 1

        if steps[idx] == "pcc_type" and val.lower() in MANDATORY_ADDR_ANTECEDENT_PURPOSES:
            session.slots["verification_mode"] = VERIFICATION_MODES[0]
            return (
                f"Since your purpose is **{val}**, the verification mode is "
                f"automatically set to **Address and Antecedent Verification** "
                f"— this is mandatory for Emigration (NRI-linked purposes).\n\n"
                + _pcc_final(session)
            )

        if session.current_step >= len(steps):
            return _pcc_final(session)
        return _ask_pcc(steps[session.current_step], session.slots)

    if _is_back(msg):
        return _pcc_go_back(session, msg)

    return err


def _process_cvr(session: Session, msg: str) -> str:
    steps = CVR_STEPS
    idx = session.current_step

    if idx >= len(steps):
        return _cvr_final(session)

    val, err = _parse_cvr(steps[idx], msg, session.slots)

    if val is not None:
        session.slots[steps[idx]] = val
        session.current_step += 1

        if val == "no":
            session.complete = True
            return (
                "CVR is only available for **government employees** applying via "
                "a Ministry or State Government — it does not apply in your case.\n\n"
                "Would you like to apply for a **PCC (Police Clearance Certificate)** "
                "instead? If so, say **'I need a PCC'** to begin that flow."
            )

        return _cvr_final(session)

    if _is_back(msg):
        session.current_step = 0
        session.slots.pop("is_govt_employee", None)
        return _ask_cvr(steps[0], session.slots)

    return err


def _process_mv_theft(session: Session, msg: str) -> str:
    steps = MV_THEFT_STEPS
    idx = session.current_step

    if idx >= len(steps):
        return _mv_theft_final(session)

    val, err = _parse_mv_theft(steps[idx], msg, session.slots)

    if val is not None:
        session.slots[steps[idx]] = val
        session.current_step += 1

        if steps[idx] == "delhi_jurisdiction" and val == "no":
            session.complete = True
            return (
                "As per Delhi Police regulations, online e-FIR registration is strictly restricted to "
                "thefts occurring **within Delhi**. Please report the incident to your local jurisdiction "
                "instead.\n\n(If this was a mistake, say **'go back'** to change your answer.)"
            )

        if session.current_step >= len(steps):
            return _mv_theft_final(session)
        return _ask_mv_theft(steps[session.current_step], session.slots)

    if _is_back(msg):
        return _mv_theft_go_back(session, msg)

    return err


def _process_lost_report(session: Session, msg: str) -> str:
    steps = LOST_REPORT_STEPS
    idx = session.current_step

    if idx >= len(steps):
        return _lost_report_final_lost(session)

    if steps[idx] == "report_type":
        val, err = _parse_lost_report(steps[idx], msg, session.slots)
        if val is not None:
            session.slots[steps[idx]] = val
            if val == "Found":
                return _lost_report_final_found(session)
            session.current_step += 1
            return _ask_lost_report(steps[session.current_step], session.slots)
        if _is_back(msg):
            return _ask_lost_report(steps[0], session.slots)
        return err

    if steps[idx] == "criminal_suspicion":
        val, err = _parse_lost_report(steps[idx], msg, session.slots)
        if val is not None:
            session.slots[steps[idx]] = val
            if val == "yes":
                session.complete = True
                session.flow = "mv_theft"
                session.current_step = 0
                session.slots = {}
                return (
                    "For stolen property or theft incidents, you'll need to file an **MV Theft e-FIR** "
                    "instead of a Lost Report.\n\n" + _ask_mv_theft(MV_THEFT_STEPS[0], {})
                )
            return _lost_report_final_lost(session)
        if _is_back(msg):
            session.current_step = 0
            session.slots.pop("report_type", None)
            return _ask_lost_report(steps[0], session.slots)
        return err

    return "Unknown step."


# ─── Public API ───────────────────────────────────────────────────────────────

def start_flow(session: Session) -> str:
    """Reset session state and return the opening question for the flow."""
    session.current_step = 0
    session.slots = {}
    session.complete = False
    if session.flow == "pcc":
        return _ask_pcc(PCC_STEPS[0], {})
    if session.flow == "cvr":
        return _ask_cvr(CVR_STEPS[0], {})
    if session.flow == "mv_theft":
        return _ask_mv_theft(MV_THEFT_STEPS[0], {})
    if session.flow == "lost_report":
        return _ask_lost_report(LOST_REPORT_STEPS[0], {})
    return "Unknown flow."


def process_message(session: Session, msg: str) -> str:
    """Process one user turn and return the bot reply."""
    if session.complete:
        return "This session is complete. Type 'restart' to begin a new one."
    if session.flow == "pcc":
        return _process_pcc(session, msg)
    if session.flow == "cvr":
        return _process_cvr(session, msg)
    if session.flow == "mv_theft":
        return _process_mv_theft(session, msg)
    if session.flow == "lost_report":
        return _process_lost_report(session, msg)
    return "Unknown flow type."
