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
        "voice_behavior": {"greeting": flow.get("opening", "")},
        "allowed_tools": ["end_call"],
        "escalation_rules": {"when": [], "how": f.get("escalation_rules", "")},
        "end_conditions": list(f.get("call_ending_conditions", [])),
        "audit_fields": [],
    }
