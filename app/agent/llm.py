"""LiteLLM wrapper. Model comes from LLM_MODEL (any LiteLLM provider string).

* "ollama/<model>" is sent to Ollama's /api/chat ("ollama_chat/") which supports native tool calling.
* Tool calls that small models print as JSON text are recovered.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

import litellm

from app.config import env

litellm.drop_params = True
litellm.suppress_debug_info = True
litellm.telemetry = False

TOOL_NAMES = ("resolve_entities", "get_pnl", "get_trend", "get_ratio", "variance_drivers",
              "rank_entities", "compare_versions", "get_kpi_cockpit", "get_workforce", "describe_catalog",
              "get_landing", "get_ytd_with_landing", "explain_landing", "rank_landing", "run_readonly_sql")


@dataclass
class LLMResult:
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    latency: float = 0.0
    model: str = ""
    usage: dict = field(default_factory=dict)
    native_tool_call: bool = False


def resolve_model(model: str | None = None) -> str:
    m = (model or env("LLM_MODEL", "ollama/qwen2.5-coder:14b")).strip()
    if m.startswith("ollama/"):
        m = "ollama_chat/" + m.split("/", 1)[1]
    return m


def _kwargs(model: str) -> dict:
    kw: dict = {"temperature": float(env("LLM_TEMPERATURE", "0") or 0),
                "timeout": float(env("LLM_TIMEOUT_SECONDS", "300") or 300)}
    if model.startswith("ollama"):
        kw["api_base"] = env("OLLAMA_API_BASE", "http://localhost:11434")
        kw["num_ctx"] = int(env("OLLAMA_NUM_CTX", "8192") or 8192)
        if "gpt-oss" in model:                     # reasoning model: keep thinking short on CPU
            kw["reasoning_effort"] = env("GPT_OSS_REASONING_EFFORT", "low")
    elif model.startswith("vertex_ai/"):
        if env("VERTEXAI_PROJECT"):
            kw["vertex_project"] = env("VERTEXAI_PROJECT")
        kw["vertex_location"] = env("VERTEXAI_LOCATION", "us-central1")
    return kw


def _vertex_openai(model: str) -> tuple[str, dict] | None:
    """Vertex AI through its OpenAI-compatible endpoint with a short-lived OAuth access token
    (env VERTEX_ACCESS_TOKEN). Used for the evaluation when the runtime has no Application Default
    Credentials with Vertex AI access; the token is passed per run and never stored."""
    token = env("VERTEX_ACCESS_TOKEN")
    if not (model.startswith("vertex_ai/") and token):
        return None
    proj, loc = env("VERTEXAI_PROJECT"), env("VERTEXAI_LOCATION", "us-central1")
    base = f"https://{loc}-aiplatform.googleapis.com/v1/projects/{proj}/locations/{loc}/endpoints/openapi"
    return f"openai/google/{model.split('/', 1)[1]}", {"api_base": base, "api_key": token}


def chat(messages: list[dict], tools: list[dict] | None = None, model: str | None = None,
         tool_choice: str | None = None, max_tokens: int | None = None) -> LLMResult:
    m = resolve_model(model)
    kw = _kwargs(m)
    alt = _vertex_openai(m)
    if alt:
        m, extra = alt
        kw = {k: v for k, v in kw.items() if not k.startswith("vertex_")}
        kw.update(extra)
        kw["extra_body"] = {"reasoning_effort": env("VERTEX_REASONING_EFFORT", "none")}
    if tools:
        kw["tools"] = tools
        if tool_choice:
            kw["tool_choice"] = tool_choice
    if max_tokens:
        if "gpt-oss" in m:                         # thinking tokens count against the budget
            max_tokens = max(max_tokens, 2000)
        kw["max_tokens"] = max_tokens
    t0 = time.time()
    resp = litellm.completion(model=m, messages=messages, **kw)
    msg = resp.choices[0].message
    calls, native = parse_tool_calls(msg)
    usage = {}
    if getattr(resp, "usage", None):
        try:
            usage = {"prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens}
        except Exception:  # noqa: BLE001
            usage = {}
    return LLMResult(content=(msg.content or "").strip(), tool_calls=calls, latency=time.time() - t0,
                     model=m, usage=usage, native_tool_call=native)


def _loads(s) -> dict:
    if isinstance(s, dict):
        return s
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else {}
    except (TypeError, ValueError):
        return {}


def parse_tool_calls(msg) -> tuple[list[dict], bool]:
    calls = []
    for tc in (getattr(msg, "tool_calls", None) or []):
        fn = getattr(tc, "function", None)
        if fn is None or not getattr(fn, "name", None):
            continue
        calls.append({"name": fn.name, "arguments": _loads(fn.arguments)})
    if calls:
        return calls, True
    return calls_from_text(getattr(msg, "content", "") or ""), False


def _balanced_objects(text: str) -> list[str]:
    out, depth, start = [], 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                out.append(text[start:i + 1])
    return out


def calls_from_text(text: str) -> list[dict]:
    """Recover tool calls printed as text, e.g. '{"name": "get_pnl", "arguments": {...}}'
    or 'get_pnl {"org": "Mexico"}'."""
    if not text:
        return []
    calls = []
    for obj in _balanced_objects(text):
        d = _loads(obj)
        name = d.get("name") or d.get("tool") or d.get("function") or d.get("tool_name")
        if isinstance(name, dict):
            name = name.get("name")
        args = d.get("arguments") or d.get("args") or d.get("parameters") or d.get("input")
        if name in TOOL_NAMES:
            calls.append({"name": name, "arguments": _loads(args) if args is not None else {}})
    if calls:
        return calls
    for m in re.finditer(r"\b(" + "|".join(TOOL_NAMES) + r")\b\s*\(?\s*(\{)", text):
        objs = _balanced_objects(text[m.start(2):])
        if objs:
            calls.append({"name": m.group(1), "arguments": _loads(objs[0])})
    return calls
