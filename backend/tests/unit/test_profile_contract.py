import json
from pathlib import Path

import jsonschema

from app.db.models import AgentProfileVersion
from app.services.profile_builder import build_generic_profile
from tests.conftest import FAKE_FIELDS

SCHEMA = json.loads((Path(__file__).resolve().parents[3] / "contracts" / "agent-profile.schema.json").read_text())


def test_generic_profile_matches_shared_contract():
    v = AgentProfileVersion(structured_fields=FAKE_FIELDS, context_prompt="p" * 30)
    jsonschema.validate(build_generic_profile(v), SCHEMA)
