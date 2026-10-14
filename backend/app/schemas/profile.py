from typing import Any

from pydantic import BaseModel, Field


class ConversationFlow(BaseModel):
    opening: str
    main_steps: list[str]
    closing: str


class ContextPromptFields(BaseModel):
    """Structured output of the context-prompt generator (Gemini response schema)."""

    agent_name: str
    role_summary: str
    objective: str
    persona_and_tone: str
    language_and_voice_style: str
    conversation_flow: ConversationFlow
    in_scope_topics: list[str]
    out_of_scope_topics_and_deflection_style: str
    escalation_rules: str
    information_to_collect: list[str]
    hard_rules: list[str]
    factual_grounding_policy: str
    call_ending_conditions: list[str]
    assumptions_made: list[str]


class GenerateProfileRequest(BaseModel):
    description: str = Field(min_length=10, max_length=6000)


class UpdateProfileRequest(BaseModel):
    context_prompt: str = Field(min_length=20, max_length=20000)


class ProfileOut(BaseModel):
    profile_id: str
    version: int
    context_prompt: str
    structured_fields: dict[str, Any]
    placeholders: list[str]
    assumptions_made: list[str] = []
