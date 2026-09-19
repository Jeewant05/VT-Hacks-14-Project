"""Safe HTML rendering for the frontend agent's structured demo preview."""

import json
import re
from collections.abc import Iterable
from html import escape
from typing import Any

PREVIEW_PATH = "frontend/preview.json"
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


def _text(value: Any, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{PREVIEW_PATH} requires a non-empty {field}")
    return value.strip()[:limit]


def render_agent_preview(objective: str, artifacts: Iterable[Any]) -> str:
    """Validate the agent-owned preview spec and render it through our fixed shell."""
    preview = next((item for item in artifacts if item.path == PREVIEW_PATH), None)
    if preview is None:
        raise ValueError(f"frontend agent must generate {PREVIEW_PATH}")
    try:
        spec = json.loads(preview.content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{PREVIEW_PATH} must contain valid JSON") from exc
    if not isinstance(spec, dict):
        raise TypeError(f"{PREVIEW_PATH} must contain a JSON object")

    title = _text(spec.get("title"), "title", 80)
    subtitle = _text(spec.get("subtitle"), "subtitle", 240)
    action = _text(spec.get("primary_action", "Get started"), "primary_action", 40)
    accent = spec.get("accent", "#6d5dfc")
    if not isinstance(accent, str) or not _HEX_COLOR.fullmatch(accent):
        raise ValueError(f"{PREVIEW_PATH} accent must be a six-digit hex color")

    raw_metrics = spec.get("metrics", [])
    raw_cards = spec.get("cards")
    if not isinstance(raw_metrics, list) or len(raw_metrics) > 4:
        raise ValueError(f"{PREVIEW_PATH} metrics must be a list of at most 4 items")
    if not isinstance(raw_cards, list) or not 1 <= len(raw_cards) <= 8:
        raise ValueError(f"{PREVIEW_PATH} cards must contain 1-8 items")

    metrics: list[tuple[str, str]] = []
    for index, item in enumerate(raw_metrics):
        if not isinstance(item, dict):
            raise TypeError(f"{PREVIEW_PATH} metric {index + 1} must be an object")
        metrics.append(
            (_text(item.get("value"), "metric value", 24), _text(item.get("label"), "metric label", 50))
        )

    cards: list[tuple[str, str, str]] = []
    for index, item in enumerate(raw_cards):
        if not isinstance(item, dict):
            raise TypeError(f"{PREVIEW_PATH} card {index + 1} must be an object")
        cards.append(
            (
                _text(item.get("title"), "card title", 80),
                _text(item.get("description"), "card description", 240),
                _text(item.get("badge", "Ready"), "card badge", 30),
            )
        )

    metric_html = "".join(
        f'<div class="metric"><strong>{escape(value)}</strong><span>{escape(label)}</span></div>'
        for value, label in metrics
    )
    card_html = "".join(
        f'<article><span class="badge">{escape(badge)}</span><h2>{escape(card_title)}</h2>'
        f'<p>{escape(description)}</p></article>'
        for card_title, description, badge in cards
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} · Agent preview</title>
<style>
:root{{--accent:{accent};--ink:#17211b;--muted:#66746b;--panel:#fff;--line:#dfe8e1}}
*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(145deg,#f5f8f5,#edf3ee);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,sans-serif;min-height:100vh}}
header,main,footer{{width:min(1060px,calc(100% - 40px));margin:auto}}header{{padding:72px 0 34px}}.kicker{{color:var(--accent);font-size:12px;font-weight:800;letter-spacing:.14em;text-transform:uppercase}}
h1{{font-size:clamp(40px,7vw,72px);letter-spacing:-.055em;line-height:.98;margin:14px 0;max-width:850px}}header p{{color:var(--muted);font-size:18px;line-height:1.6;max-width:720px}}
.action{{display:inline-block;background:var(--accent);color:#fff;border-radius:10px;padding:13px 18px;margin-top:10px;font-weight:750}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:4px 0 26px}}.metric,article{{background:var(--panel);border:1px solid var(--line);box-shadow:0 10px 35px #213d280b}}
.metric{{padding:18px;border-radius:14px}}.metric strong,.metric span{{display:block}}.metric strong{{font-size:24px}}.metric span{{color:var(--muted);font-size:13px;margin-top:4px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}}article{{padding:22px;border-radius:16px}}article h2{{font-size:18px;margin:18px 0 8px}}article p{{color:var(--muted);font-size:14px;line-height:1.55;margin:0}}.badge{{background:color-mix(in srgb,var(--accent) 12%,white);color:var(--accent);border-radius:999px;padding:6px 9px;font-size:11px;font-weight:800}}
footer{{padding:34px 0 50px;color:var(--muted);font-size:12px}}code{{color:var(--accent)}}
</style></head><body><header><div class="kicker">Built live by three coordinated agents</div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p><span class="action">{escape(action)}</span></header>
<main><section class="metrics">{metric_html}</section><section class="cards">{card_html}</section></main>
<footer>Generated for <code>{escape(objective[:180])}</code> · Rendered inside Synapse's constrained preview shell</footer></body></html>"""
