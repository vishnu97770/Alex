import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from voice_agent.profile.schema import AgentProfileSpec

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "agent-profile.schema.json"


def _profile(**kw):
    return {"identity": {"agent_name": "Ava"}, "context_prompt": "Be helpful.", **kw}


def test_minimal_profile_valid_with_defaults():
    p = AgentProfileSpec.model_validate(_profile())
    assert p.voice_behavior.latency_profile == "balanced"
    assert p.allowed_tools == []


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        AgentProfileSpec.model_validate(_profile(surprise=1))


def test_contract_file_matches_model_and_validates_instances():
    schema = json.loads(CONTRACT.read_text())
    assert schema == AgentProfileSpec.model_json_schema(), "run scripts_export_contracts.py"
    jsonschema.validate(AgentProfileSpec.model_validate(_profile()).model_dump(), schema)
