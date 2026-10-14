"""Export JSON Schemas to contracts/. Run: uv run python scripts_export_contracts.py"""
import json
from pathlib import Path

from voice_agent.profile.schema import AgentProfileSpec

out = Path(__file__).resolve().parents[1] / "contracts" / "agent-profile.schema.json"
out.write_text(json.dumps(AgentProfileSpec.model_json_schema(), indent=2, sort_keys=True) + "\n")
print("wrote", out)
