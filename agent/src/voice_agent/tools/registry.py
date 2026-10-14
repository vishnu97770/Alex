"""Tool registry. A profile's allowed_tools names are resolved here; unknown names fail closed."""

from collections.abc import Callable
from typing import Any

from livekit.agents import RunContext, function_tool

from voice_agent.tools.base import ToolContext

ToolFactory = Callable[[ToolContext], Any]
_REGISTRY: dict[str, ToolFactory] = {}


class UnknownToolError(KeyError):
    pass


def register(name: str) -> Callable[[ToolFactory], ToolFactory]:
    def deco(f: ToolFactory) -> ToolFactory:
        _REGISTRY[name] = f
        return f

    return deco


@register("propose_end_call")
def _propose_end_call(ctx: ToolContext) -> Any:
    @function_tool(
        name="propose_end_call",
        description=(
            "Call this at the moment you tell the caller you are about to end the call (after asking whether they "
            "need anything else and they said no). Then say it out loud and ask them to confirm."
        ),
    )
    async def propose_end_call(context: RunContext) -> str:
        ctx.state.end_proposed_at = ctx.state.user_turns
        return "Recorded. Now tell the caller you are about to end the call and ask them to confirm. Do not end it yet."

    return propose_end_call


@register("end_call")
def _end_call(ctx: ToolContext) -> Any:
    @function_tool(
        name="end_call",
        description=(
            "End the call. Allowed ONLY after propose_end_call was used AND the caller then clearly agreed in a "
            "later message. Set caller_confirmed=true only in that case."
        ),
    )
    async def end_call(context: RunContext, reason: str, caller_confirmed: bool) -> str:
        st = ctx.state
        if st.end_proposed_at is None:
            return (
                "Not allowed: you have not announced the end of the call. "
                "Ask if they need anything else, then use propose_end_call."
            )
        if not caller_confirmed or st.user_turns <= st.end_proposed_at:
            return (
                "Not allowed: wait for the caller to answer and clearly agree to end the call, "
                "then call end_call again."
            )
        st.end_reason = reason[:60]
        context.session.shutdown(drain=True)
        return "The call is ending. Say nothing further."

    return end_call


def build_tools(allowed: list[str], ctx: ToolContext) -> list[Any]:
    tools = []
    for name in dict.fromkeys(["propose_end_call", "end_call", *allowed]):  # call-ending tools are always available
        if name not in _REGISTRY:
            raise UnknownToolError(f"profile requests unknown tool '{name}'")
        tools.append(_REGISTRY[name](ctx))
    return tools
