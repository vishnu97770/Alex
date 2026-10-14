# ADR-0005: Dev infra host ports 5443/6390

Status: accepted

## Context
5433 and 6380 were already bound on the dev machine.

## Decision
docker-compose.dev.yml maps Postgres to 5443 and Redis to 6390.
