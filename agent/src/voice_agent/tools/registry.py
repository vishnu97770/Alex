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


@register("end_call")
def _end_call(ctx: ToolContext) -> Any:
    @function_tool(
        name="end_call",
        description=(
            "End the call. Use only after you have said goodbye and the conversation's ending conditions "
            "are met, or the caller asked to hang up."
        ),
    )
    async def end_call(context: RunContext, reason: str) -> str:
        ctx.state.end_reason = reason[:60]
        context.session.shutdown(drain=True)
        return "The call is ending. Say nothing further."

    return end_call


def build_tools(allowed: list[str], ctx: ToolContext) -> list[Any]:
    tools = []
    for name in dict.fromkeys(["end_call", *allowed]):  # end_call is always available
        if name not in _REGISTRY:
            raise UnknownToolError(f"profile requests unknown tool '{name}'")
        tools.append(_REGISTRY[name](ctx))
    return tools
