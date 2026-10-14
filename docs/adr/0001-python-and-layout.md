# ADR-0001: Python 3.12 and repo layout

Status: accepted

## Context
livekit-agents 1.8.7 declares requires-python >=3.12.

## Decision
All Python services pin 3.12 and use uv with lockfiles. Layout follows the master prompt; one pyproject per service.
