"""Builds the runtime AgentProfile (contracts/agent-profile.schema.json) for a stored version."""

from typing import Any

from app.db.models import AgentProfileVersion


def build_generic_profile(v: AgentProfileVersion) -> dict[str, Any]:
    f = v.structured_fields
    flow = f.get("conversation_flow", {})
    return {
        "identity": {
            "agent_name": f.get("agent_name", "Assistant"),
            "role_summary": f.get("role_summary", ""),
        },
        "context_prompt": v.context_prompt,
        "voice_behavior": {
            "voice_id": f.get("voice_id", ""),  # empty: the worker's default voice
            "hindi_voice_id": f.get("hindi_voice_id", ""),  # empty: Hindi replies use the voice above
            "greeting": flow.get("opening", ""),
            "latency_profile": "aggressive",
        },
        "allowed_tools": ["end_call"],
        "escalation_rules": {"when": [], "how": f.get("escalation_rules", "")},
        "end_conditions": list(f.get("call_ending_conditions", [])),
        "audit_fields": [],
    }
