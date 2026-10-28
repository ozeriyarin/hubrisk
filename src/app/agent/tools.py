"""Tools the model may call. Every tool is deterministic code; the model only chooses and explains.

The v3 agent spec replaces `about` with the domain tools. Keep them pure functions over `ToolContext` so tests
can run them without a model.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from app import __version__
from app.agent.prompts import SCOPE_DESCRIPTION


@dataclass
class ToolContext:
    """Everything tools need (DB handles, config). Built once at startup, injected per run as `deps`."""

    product_name: str


class About(BaseModel):
    product: str
    version: str
    scope: str


def about(ctx: RunContext[ToolContext]) -> About:
    """What this assistant is and what it covers. Call when the user asks what you can do."""
    return About(product=ctx.deps.product_name, version=__version__, scope=SCOPE_DESCRIPTION)


def build_toolset() -> FunctionToolset[ToolContext]:
    toolset: FunctionToolset[ToolContext] = FunctionToolset()
    toolset.add_function(about)
    return toolset
