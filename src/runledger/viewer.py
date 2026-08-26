"""Generate a dependency-free offline HTML timeline for a recorded run."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .ledger import Ledger
from .report import build_summary


_CSS = """
:root { color-scheme: dark; font-family: ui-sans-serif, system-ui, sans-serif; background: #0b1020; color: #e7ecf7; }
body { max-width: 1100px; margin: 0 auto; padding: 32px; }
header { border-bottom: 1px solid #26304a; padding-bottom: 20px; margin-bottom: 22px; }
h1 { margin: 0 0 8px; font-size: 30px; }
.badge { display: inline-block; border-radius: 999px; padding: 4px 10px; background: #173b31; color: #8cf0c2; font-weight: 700; }
.badge.failed { background: #49232b; color: #ffadb5; }
.controls { display: flex; gap: 12px; margin: 18px 0; }
input { background: #111a30; border: 1px solid #34405e; color: #e7ecf7; border-radius: 8px; padding: 9px 12px; min-width: 280px; }
.timeline { border-left: 2px solid #34405e; margin-left: 10px; padding-left: 20px; }
.event { position: relative; margin: 0 0 14px; padding: 14px 16px; border: 1px solid #26304a; border-radius: 10px; background: #10182b; }
.event::before { content: ''; position: absolute; left: -28px; top: 18px; width: 12px; height: 12px; border: 3px solid #0b1020; border-radius: 50%; background: #64b5ff; }
.event.completed::before { background: #8cf0c2; }
.event.verification::before { background: #f3c969; }
.meta { color: #9aa8c4; font-size: 12px; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #0a0f1c; padding: 10px; border-radius: 7px; }
code { color: #b8d7ff; }
.hidden { display: none; }
table { width: 100%; border-collapse: collapse; margin-top: 12px; }
th, td { text-align: left; border-bottom: 1px solid #26304a; padding: 9px; vertical-align: top; }
"""


def _event_detail(event: dict) -> str:
    detail = {key: value for key, value in event.items() if key not in {"schema", "run_id", "seq", "timestamp", "type"}}
    return html.escape(json.dumps(detail, indent=2, sort_keys=True)) if detail else ""


def render_html(run_dir: Path) -> str:
    summary = build_summary(run_dir)
    events = list(Ledger(run_dir).events())
    status_class = "failed" if summary["status"] == "failed" else ""
    event_cards = []
    for event in events:
        event_type = event.get("type", "event")
        event_cards.append(
            f'<article class="event {html.escape(event_type)}" data-type="{html.escape(event_type)}">'
            f'<strong>#{event.get("seq")}: {html.escape(event_type)}</strong>'
            f'<div class="meta">{html.escape(str(event.get("timestamp", "")))}</div>'
            f'<details><summary>Inspect event data</summary><pre>{_event_detail(event)}</pre></details>'
            "</article>"
        )
    artifact_links = []
    for path in sorted((run_dir / "artifacts").glob("*") if (run_dir / "artifacts").exists() else []):
        artifact_links.append(f"<li><a href='artifacts/{html.escape(path.name)}'>{html.escape(path.name)}</a></li>")
    payload = html.escape(json.dumps(summary, sort_keys=True))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RunLedger — {html.escape(summary['run_id'])}</title><style>{_CSS}</style></head>
<body>
<header><h1>RunLedger replay: <code>{html.escape(summary['run_id'])}</code></h1>
<span class="badge {status_class}">{html.escape(summary['status'])}</span>
<p>Offline timeline of observable events. This report does not prove code correctness, security, or command safety.</p></header>
<section><h2>Run summary</h2><table><tr><th>Events</th><td>{summary['event_count']}</td></tr><tr><th>Commands</th><td>{len(summary['commands'])}</td></tr><tr><th>Artifacts</th><td><ul>{''.join(artifact_links) or '<li>None</li>'}</ul></td></tr></table></section>
<section><h2>Timeline</h2><div class="controls"><label>Filter event type <input id="filter" placeholder="e.g. command.completed"></label></div><div class="timeline" id="timeline">{''.join(event_cards) or '<p>No events recorded.</p>'}</div></section>
<script type="application/json" id="summary">{payload}</script>
<script>const input=document.getElementById('filter');const cards=[...document.querySelectorAll('.event')];input.addEventListener('input',()=>{{const q=input.value.toLowerCase();cards.forEach(c=>c.classList.toggle('hidden',q&&!c.dataset.type.toLowerCase().includes(q)));}});</script>
</body></html>"""
