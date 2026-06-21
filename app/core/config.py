import yaml
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

def _load_yaml(filename: str) -> dict:
    path = CONFIG_DIR / filename
    with open(path, "r") as f:
        return yaml.safe_load(f)

ingestion_config = _load_yaml("ingestion_config.yaml")
retrieval_config = _load_yaml("retrieval_config.yaml")
app_config = _load_yaml("config.yaml")
