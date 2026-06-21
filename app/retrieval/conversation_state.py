"""
In-memory session store for guided conversational flows.
"""
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Session:
    session_id: str
    flow: str           # "pcc" or "cvr"
    slots: dict = field(default_factory=dict)
    current_step: int = 0
    complete: bool = False


_sessions: dict[str, Session] = {}


def create_session(flow: str) -> Session:
    sid = str(uuid.uuid4())
    s = Session(session_id=sid, flow=flow)
    _sessions[sid] = s
    return s


def get_session(session_id: str) -> Optional[Session]:
    return _sessions.get(session_id)
