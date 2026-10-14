"""AgentProfile: the only thing the runtime needs to run a domain agent.

Adding a new domain = a new profile + tool modules; session_factory, providers,
lifecycle and telephony code stay untouched.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Identity(_Model):
    agent_name: str
    role_summary: str = ""
    organization: str = ""


class InterruptionSettings(_Model):
    enabled: bool = True
    min_duration_s: float = Field(0.5, ge=0, le=5)
    min_words: int = Field(1, ge=0, le=10)


class VoiceBehavior(_Model):
    voice_id: str = ""
    speaking_rate: float = Field(1.0, ge=0.5, le=1.5)
    greeting: str = ""
    fallback_lines: dict[str, str] = Field(
        default_factory=lambda: {
            "tool_failure": "I'm sorry, I can't retrieve that right now.",
            "technical_difficulty": "I'm having technical difficulties, so I'll end this call for now.",
            "not_understood": "Sorry, I didn't catch that. Could you say it again?",
        }
    )
    latency_profile: Literal["aggressive", "balanced", "conservative"] = "balanced"
    interruption: InterruptionSettings = Field(default_factory=InterruptionSettings)


class IdentityVerificationPolicy(_Model):
    required: bool = False
    method: Literal["none", "verbal_secret"] = "none"
    max_attempts: int = Field(3, ge=1, le=5)
    pre_verification_disclosure: str = "state only who is calling and why"


class Policies(_Model):
    confirmation_required_for_actions: bool = True
    disclosure_rules: list[str] = Field(default_factory=list)
    identity_verification: IdentityVerificationPolicy = Field(default_factory=IdentityVerificationPolicy)


class EscalationRules(_Model):
    when: list[str] = Field(default_factory=list)
    how: str = ""


class AgentProfileSpec(_Model):
    identity: Identity
    context_prompt: str
    voice_behavior: VoiceBehavior = Field(default_factory=VoiceBehavior)
    allowed_tools: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    policies: Policies = Field(default_factory=Policies)
    triggers: list[dict[str, str]] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    escalation_rules: EscalationRules = Field(default_factory=EscalationRules)
    audit_fields: list[str] = Field(default_factory=list)
    summary_schema_extensions: dict[str, str] = Field(
        default_factory=dict, description="extra summary fields: name -> description"
    )
    end_conditions: list[str] = Field(default_factory=list)
