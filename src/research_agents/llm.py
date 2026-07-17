"""LLM client plus the generic tool-calling loop every agent reuses.

The loop is the core of tool calling: the model replies with structured
tool requests, we execute them locally, append the results as `tool`
messages, and let the model continue until it answers in plain text.

Backed by Groq via the OpenAI protocol. Swapping providers means changing
`base_url` and `model` in config; nothing here needs to know the difference.
"""

import json
import random
import re
import time
from functools import lru_cache
from typing import Any, Callable, TypeVar

from openai import BadRequestError, OpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

from research_agents.config import get_settings

T = TypeVar("T", bound=BaseModel)


@lru_cache
def get_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.groq_api_key, base_url=settings.base_url)


def _is_malformed_tool_call(exc: BadRequestError) -> bool:
    """Groq's 400 for "the model emitted a tool call I can't parse".

    Distinguished from every other 400 (a genuinely bad request, which retrying
    would only repeat) by Groq's `tool_use_failed` code.
    """
    return "tool_use_failed" in str(exc)


def _complete(**kwargs: Any) -> Any:
    """One chat completion, retrying through the two failures the free tier throws.

    - **rate limits.** Groq's free tier is capped per minute and parallel
      researchers will hit it.
    - **malformed tool calls.** The model sometimes emits a tool call Groq
      can't parse. Generation is stochastic, so the same request usually
      succeeds on a retry — worth doing because one bad call would otherwise
      kill a multi-minute run near the end of it.

    Exponential backoff with jitter so parallel retries don't re-collide.
    """
    settings = get_settings()
    for attempt in range(settings.max_rate_limit_retries):
        try:
            return get_client().chat.completions.create(**kwargs)
        except (RateLimitError, BadRequestError) as exc:
            if isinstance(exc, BadRequestError) and not _is_malformed_tool_call(exc):
                raise  # a real bad request; retrying just repeats it
            if attempt == settings.max_rate_limit_retries - 1:
                raise
            time.sleep(2**attempt + random.random())
    raise RuntimeError("unreachable")


def complete(messages: list[dict[str, Any]], model: str | None = None) -> str:
    """One completion, plain text out. For agents that reason but call no tools."""
    response = _complete(model=model or get_settings().model, messages=messages)
    return response.choices[0].message.content or ""


def run_tool_loop(
    messages: list[dict[str, Any]],
    tool_schemas: list[dict[str, Any]],
    tool_impls: dict[str, Callable[..., str]],
    model: str | None = None,
) -> str:
    """Drive the model until it answers without requesting a tool.

    Returns the final assistant text. Mutates `messages` in place so the
    caller can inspect the full transcript afterwards.
    """
    settings = get_settings()
    model = model or settings.model

    for _ in range(settings.max_tool_turns):
        response = _complete(model=model, messages=messages, tools=tool_schemas)
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            return message.content or ""

        for call in message.tool_calls:
            name = call.function.name
            impl = tool_impls.get(name)
            if impl is None:
                result = f"Error: no tool named {name!r}."
            else:
                try:
                    args = json.loads(call.function.arguments or "{}")
                    result = impl(**args)
                except Exception as exc:  # surface failures to the model, don't crash
                    result = f"Error running {name}: {exc}"
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result}
            )

    return "Stopped: hit the tool-call limit without producing an answer."


def _extract_json(text: str) -> str:
    """Pull a JSON object out of a reply, tolerating ```json fences and prose."""
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


def complete_json(
    messages: list[dict[str, Any]],
    schema: type[T],
    model: str | None = None,
) -> T:
    """Ask for JSON matching `schema` and validate it.

    Prompts for JSON and validates locally rather than trusting the provider's
    structured-output mode, feeding a failure back once for a repair attempt
    before giving up.
    """
    settings = get_settings()
    model = model or settings.model
    messages = [
        *messages,
        {
            "role": "system",
            "content": (
                "Reply with a single JSON object matching this schema. "
                "No prose, no code fences.\n"
                f"{json.dumps(schema.model_json_schema())}"
            ),
        },
    ]

    last_error = ""
    for _ in range(2):
        response = _complete(model=model, messages=messages)
        raw = response.choices[0].message.content or ""
        try:
            return schema.model_validate_json(_extract_json(raw))
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            messages.extend(
                [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": f"That did not validate: {last_error}\nReturn corrected JSON only.",
                    },
                ]
            )

    raise ValueError(f"{schema.__name__} did not validate after a retry: {last_error}")
