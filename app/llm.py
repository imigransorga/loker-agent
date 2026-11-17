"""Helper pemanggilan Claude API (dipakai semua agent)."""
import json

import anthropic

from .config import ANTHROPIC_API_KEY, CLAUDE_MODEL

# Fallback server-side: kalau model menolak (refusal), API otomatis mengulang di model cadangan.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5",
                   "claude-fable-5-2", "claude-fable-5-1"}

WEB_SEARCH_TOOL = {
    "type": "web_search_20260209",
    "name": "web_search",
    "user_location": {"type": "approximate", "country": "ID", "timezone": "Asia/Jakarta"},
}

_client: anthropic.Anthropic | None = None


class ClaudeError(RuntimeError):
    pass


def client() -> anthropic.Anthropic:
    global _client
    if not ANTHROPIC_API_KEY:
        raise ClaudeError("ANTHROPIC_API_KEY belum diisi di file .env")
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=3)
    return _client


def _create(**kw):
    if CLAUDE_MODEL in FALLBACK_MODELS:
        kw["betas"] = [FALLBACK_BETA]
        kw["fallbacks"] = "default"
    try:
        resp = client().beta.messages.create(model=CLAUDE_MODEL, **kw)
    except anthropic.AuthenticationError as e:
        raise ClaudeError("API key Claude tidak valid") from e
    except anthropic.RateLimitError as e:
        raise ClaudeError("Kena rate limit Claude API, coba lagi sebentar") from e
    except anthropic.APIStatusError as e:
        raise ClaudeError(f"Claude API error {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise ClaudeError("Gagal konek ke Claude API (cek internet)") from e
    if resp.stop_reason == "refusal":
        raise ClaudeError("Claude menolak permintaan ini")
    return resp


def _text(resp) -> str:
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def ask_text(system: str, prompt: str, effort: str = "medium", max_tokens: int = 16000) -> str:
    resp = _create(
        system=system,
        max_tokens=max_tokens,
        output_config={"effort": effort},
        messages=[{"role": "user", "content": prompt}],
    )
    return _text(resp)


def ask_json(system: str, prompt: str, schema: dict, effort: str = "low",
             max_tokens: int = 16000) -> dict:
    """Jawaban dijamin JSON sesuai schema (structured outputs)."""
    resp = _create(
        system=system,
        max_tokens=max_tokens,
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason == "max_tokens":
        raise ClaudeError("Jawaban Claude terpotong (max_tokens)")
    return json.loads(_text(resp))


def research(system: str, prompt: str, max_searches: int = 5, effort: str = "medium",
             allowed_domains: list[str] | None = None) -> tuple[str, list[dict]]:
    """Riset pakai web search Claude. Return (teks jawaban, daftar sumber {title,url})."""
    tool = dict(WEB_SEARCH_TOOL, max_uses=max_searches)
    if allowed_domains:
        tool["allowed_domains"] = allowed_domains
    messages: list = [{"role": "user", "content": prompt}]
    resp = None
    for _ in range(4):  # lanjutkan bila server menjeda giliran (pause_turn)
        resp = _create(
            system=system,
            max_tokens=16000,
            output_config={"effort": effort},
            tools=[tool],
            messages=messages,
        )
        if resp.stop_reason != "pause_turn":
            break
        messages = [messages[0], {"role": "assistant", "content": [b.to_dict() for b in resp.content]}]

    sources: dict[str, str] = {}
    for b in resp.content:
        if b.type == "web_search_tool_result" and isinstance(b.content, list):
            for r in b.content:
                url = getattr(r, "url", None)
                if url:
                    sources.setdefault(url, getattr(r, "title", "") or url)
    return _text(resp), [{"url": u, "title": t} for u, t in sources.items()]
