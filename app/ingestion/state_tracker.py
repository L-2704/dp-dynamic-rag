import json
import hashlib
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "scrape_state.json"

def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    with open(STATE_PATH, "r") as f:
        return json.load(f)

def update_state(category: str, content_hash: str, status: str):
    state = load_state()
    state[category] = {"content_hash": content_hash, "status": status}
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
