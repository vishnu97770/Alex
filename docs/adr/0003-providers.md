# ADR-0003: Deepgram for STT and TTS

Status: accepted

## Context
User chose Deepgram for both. Single DEEPGRAM_API_KEY.

## Decision
Provider factories in agent/providers are config-driven so STT/TTS stay swappable.
