"""Token minting and room control. Tokens are short-lived with minimal grants."""

import uuid
from datetime import timedelta

from livekit import api

from app.core.config import Settings


def new_room_name() -> str:
    return f"call-{uuid.uuid4().hex[:16]}"


def mint_participant_token(
    settings: Settings, *, room: str, identity: str, call_id: uuid.UUID, correlation_id: str
) -> str:
    """Browser token. Joining this room triggers explicit dispatch of our named agent."""
    metadata = f'{{"call_id":"{call_id}","correlation_id":"{correlation_id}"}}'
    return (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_ttl(timedelta(seconds=settings.token_ttl_seconds))
        .with_grants(
            api.VideoGrants(room_join=True, room=room, can_publish=True, can_subscribe=True, can_publish_data=True)
        )
        .with_room_config(
            api.RoomConfiguration(
                agents=[api.RoomAgentDispatch(agent_name=settings.agent_name, metadata=metadata)],
                empty_timeout=60,
                departure_timeout=20,
            )
        )
        .to_jwt()
    )


async def close_room(settings: Settings, room: str) -> None:
    lk = api.LiveKitAPI(settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret)
    try:
        await lk.room.delete_room(api.DeleteRoomRequest(room=room))
    finally:
        await lk.aclose()
