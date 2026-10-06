"""The Campus Customs shop agent, built with PydanticAI.

The agent is loaded from two things:
  1. its system prompt — read from `prompts/prompt.md` (the shop's voice + safety rules), and
  2. its model — an Anthropic Claude model, chosen by the CAMPUS_CUSTOMS_MODEL env var.

It needs an Anthropic API key (ANTHROPIC_API_KEY), which you can put in the top-level `.env` file.
If no key is configured — or the model call fails — we fall back to a plain keyword
search so the chat widget keeps working.
"""

import os

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pathlib import Path

from dotenv import load_dotenv

from audit import AuditRun, short
from models import AgentReply, ChatRequest, ChatResponse, ChatTurn, CustomerContext
from tools import (
    ChatDeps,
    describe_context,
    get_customer_profile,
    get_page_context,
    get_product_description,
    get_product_price,
    get_product_stock,
    keyword_fallback,
    list_categories,
    search_products,
)

# Load .env (top-level folder; a backend/.env also works) so ANTHROPIC_API_KEY and
# CAMPUS_CUSTOMS_MODEL can live in a file. Real environment variables take precedence.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "prompt.md"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")
# Default to Claude Opus 5; override with CAMPUS_CUSTOMS_MODEL (e.g. anthropic:claude-sonnet-5).
MODEL = os.getenv("CAMPUS_CUSTOMS_MODEL", "anthropic:claude-opus-5")

# Agent-loop limits. One chat message may take at most MAX_MODEL_REQUESTS model calls and
# MAX_TOOL_CALLS tool calls; past that the run stops and the keyword fallback answers instead.
MAX_MODEL_REQUESTS = 8
MAX_TOOL_CALLS = 12
MAX_OUTPUT_TOKENS = 2000  # per model response (replies are short; this leaves room for 30 product ids)
OUTPUT_RETRIES = 2  # times the model may fix a reply the output check rejected
HISTORY_TURNS = 12  # earlier chat turns sent to the model


def _build_agent():
    """Create the PydanticAI agent, or return None if no API key is available."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    from pydantic_ai import Agent, ModelRetry, NativeOutput, RunContext, Tool

    shop_agent = Agent(
        MODEL,
        deps_type=ChatDeps,
        # Structured reply (see AgentReply in models.py). NativeOutput uses Anthropic's JSON-schema
        # structured outputs rather than a forced tool call, which some Claude models reject.
        output_type=NativeOutput(AgentReply),
        system_prompt=SYSTEM_PROMPT,
        retries=OUTPUT_RETRIES,
        tools=[
            Tool(search_products, takes_ctx=True),
            Tool(get_product_description, takes_ctx=True),
            Tool(get_product_price, takes_ctx=True),
            Tool(get_product_stock, takes_ctx=True),
            Tool(list_categories, takes_ctx=True),
            Tool(get_customer_profile, takes_ctx=True),
            Tool(get_page_context, takes_ctx=True),
        ],
    )

    @shop_agent.instructions
    def who_and_where(ctx: RunContext[ChatDeps]) -> str:
        # Added to every request: who is signed in and which page they're on (from the database).
        return describe_context(ctx.deps)

    @shop_agent.output_validator
    def only_looked_up_products(ctx: RunContext[ChatDeps], output: AgentReply) -> AgentReply:
        # Every card must be a product a tool returned in this run, so no card can be made up.
        unknown = [pid for pid in output.product_ids if pid not in ctx.deps.seen]
        if unknown:
            raise ModelRetry(
                f"These product_ids were not returned by a tool in this conversation: {unknown}. "
                "Look the products up with a tool first, or only list product_ids from your tool results."
            )
        return output

    return shop_agent


agent = _build_agent()


def _to_message_history(turns: list[ChatTurn]):
    """Convert prior chat turns into PydanticAI message history."""
    if not turns:
        return None
    from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

    history = []
    for turn in turns[-HISTORY_TURNS:]:  # keep it short
        if turn.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=turn.content)]))
        else:
            history.append(ModelResponse(parts=[TextPart(content=turn.content)]))
    return history


async def run_chat(
    req: ChatRequest, customer: CustomerContext | None = None, saved_history: list[ChatTurn] | None = None,
    searches: list[tuple[str, int]] | None = None,
) -> ChatResponse:
    """Run the agent on one user message and return the reply plus product cards.

    `customer` is the signed-in shopper (None for guests) and `saved_history` is their saved
    conversation from the database; guests' history comes from the request instead. Both, plus the
    page the shopper is on, go into the agent's dependencies.

    The agent names products by id; the cards themselves are built from the database rows its
    tools returned, so prices, stock, and images always come from the database.

    Any catalogue searches that ran are appended to `searches` (query, total matches) for analytics.
    """
    deps = ChatDeps(customer=customer, page=req.page_context)
    audit = AuditRun("llm" if agent else "keyword-fallback", MODEL if agent else None, customer, req.page_context, req.message)
    if agent is None:
        # No API key configured — use the keyword fallback.
        return _fallback(req, deps, audit, searches, "fallback_complete")
    history = saved_history if customer is not None else req.history
    try:
        output, stop_reason, usage = await _run_agent_loop(req.message, deps, history or [], audit)
    except Exception as e:
        # Any model/network/auth error, or a loop limit: degrade gracefully instead of erroring the widget.
        from pydantic_ai.exceptions import UsageLimitExceeded

        limit_hit = isinstance(e, UsageLimitExceeded)
        audit.log("error", step=audit.step, kind="loop_limit" if limit_hit else type(e).__name__, detail=short(e))
        reason = "loop_limit_then_fallback" if limit_hit else "error_then_fallback"
        return _fallback(req, ChatDeps(customer=customer, page=req.page_context), audit, searches, reason)
    if searches is not None:
        searches.extend(deps.searches)
    products = deps.cards(output.product_ids)
    response = ChatResponse(
        reply=output.reply,
        results_title=output.results_title if products else None,
        products=products,
    )
    audit.log(
        "run_end", stop_reason=stop_reason, reply=short(response.reply), results_title=response.results_title,
        product_ids=[p.product_id for p in products][:10], cards=len(products), model_requests=usage.requests,
        tool_calls=usage.tool_calls, input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
        duration_ms=audit.elapsed_ms(),
    )
    return response


async def _run_agent_loop(message: str, deps: ChatDeps, history: list[ChatTurn], audit: AuditRun):
    """Run the agent step by step, logging every model response, tool call, and tool result.

    Returns (AgentReply, the final stop reason, usage totals).
    """
    from pydantic_ai import UsageLimits
    from pydantic_ai.messages import RetryPromptPart, ToolCallPart, ToolReturnPart

    stop_reason = None
    async with agent.iter(
        message,
        deps=deps,
        message_history=_to_message_history(history),
        usage_limits=UsageLimits(request_limit=MAX_MODEL_REQUESTS, tool_calls_limit=MAX_TOOL_CALLS),
        model_settings={"max_tokens": MAX_OUTPUT_TOKENS},
    ) as run:
        async for node in run:
            if agent.is_model_request_node(node):
                # What goes back to the model: results of the tools it called, or a request to retry.
                for part in node.request.parts:
                    if isinstance(part, ToolReturnPart):
                        audit.log("tool_result", step=audit.step, tool=part.tool_name, result=short(part.content))
                    elif isinstance(part, RetryPromptPart):
                        audit.log("retry", step=audit.step, tool=part.tool_name or "output_check", reason=short(part.content))
            elif agent.is_call_tools_node(node):
                audit.step += 1
                response = node.model_response
                stop_reason = response.finish_reason
                calls = [p for p in response.parts if isinstance(p, ToolCallPart)]
                audit.log(
                    "model_response", step=audit.step, model=response.model_name, stop_reason=stop_reason,
                    tool_calls=[c.tool_name for c in calls], input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )
                for c in calls:
                    audit.log("tool_call", step=audit.step, tool=c.tool_name, args=short(c.args))
        return run.result.output, stop_reason, run.usage


def _fallback(req: ChatRequest, deps: ChatDeps, audit: AuditRun, searches, stop_reason: str) -> ChatResponse:
    """Answer with the keyword fallback, logging its lookups in the same shape as agent tool calls."""
    response = keyword_fallback(req.message, deps)
    if searches is not None:
        searches.extend(deps.searches)
    for t in deps.trace:
        audit.step += 1
        audit.log("tool_call", step=audit.step, tool=t["tool"], args=short(t["args"]))
        audit.log("tool_result", step=audit.step, tool=t["tool"], result=short(t["result"]))
    audit.log(
        "run_end", stop_reason=stop_reason, reply=short(response.reply), results_title=response.results_title,
        product_ids=[p.product_id for p in response.products][:10], cards=len(response.products),
        tool_calls=len(deps.trace), duration_ms=audit.elapsed_ms(),
    )
    return response


def agent_status() -> dict:
    """Small helper so the API can report whether the LLM agent is active."""
    return {"agent": "llm" if agent is not None else "keyword-fallback", "model": MODEL if agent else None}
