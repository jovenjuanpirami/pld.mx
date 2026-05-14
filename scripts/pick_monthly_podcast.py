#!/usr/bin/env python3
"""
Pick the single highest-SEO-value article from the last ~30 days to convert
into a monthly highlight podcast episode.

Scoring heuristic (proxies for "most likely to be searched / found"):
    +5 : software ranking / comparison articles ("Mejor software", "Top 10",
         "Mejores sistemas", "Comparativa", "Ranking", "Las mejores")
    +3 : sector-specific guide ("PLD para [actividad]", "Guía")
    +2 : LFPIORPI explainer (cites a specific article number, "Artículo X")
    +1 : any other tecnologia / cumplimiento article
    +0 : default

Excludes:
- Friday briefs (already published as their own weekly episodes)
- Articles already published as podcast episodes (tracked in _data/podcast_episodes.json)

Prints the chosen post path to stdout. Workflow consumes it.
Exits with code 0 even if no candidate found — workflow handles the empty case.
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).parent.parent
POSTS_DIR = REPO_ROOT / "_posts"
TRACKING_FILE = REPO_ROOT / "_data" / "podcast_episodes.json"

LOOKBACK_DAYS = 35  # a bit more than a month to catch edge cases

HIGH_VALUE_PREFIXES = (
    "Mejor software",
    "Mejores sistemas",
    "Mejores software",
    "Mejor plataforma",
    "Top ",
    "Comparativa",
    "Ranking",
    "Las mejores",
)

GUIDE_KEYWORDS = ("Guía", "PLD para", "Cómo")


def load_tracking() -> dict:
    if not TRACKING_FILE.exists():
        return {}
    try:
        return json.loads(TRACKING_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_post_date(filename: str):
    """Extract YYYY-MM-DD date prefix from Jekyll post filename."""
    match = re.match(r"^(\d{4}-\d{2}-\d{2})-", filename)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def read_title(path: Path) -> str:
    """Pull the title from the YAML frontmatter."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    match = re.search(r'^title:\s*"([^"]+)"', text, re.MULTILINE)
    if match:
        return match.group(1)
    match = re.search(r"^title:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def score_article(title: str) -> int:
    if title.startswith(HIGH_VALUE_PREFIXES):
        return 5
    if any(kw in title for kw in GUIDE_KEYWORDS):
        return 3
    if re.search(r"Art(í|i)culo\s+\d+", title):
        return 2
    return 1


def main():
    today = datetime.now(ZoneInfo("America/Mexico_City")).replace(tzinfo=timezone.utc)
    cutoff = today - timedelta(days=LOOKBACK_DAYS)

    tracking = load_tracking()
    already_published = set(tracking.keys())

    candidates = []
    for post in POSTS_DIR.glob("*.md"):
        slug = post.stem
        if slug in already_published:
            continue
        if "resumen-semanal" in slug:
            continue  # Friday briefs handled separately
        post_date = parse_post_date(post.name)
        if post_date is None or post_date < cutoff:
            continue
        title = read_title(post)
        score = score_article(title)
        candidates.append((score, post_date, post, title))

    if not candidates:
        print("", end="")  # empty stdout - workflow skips
        print(f"No eligible candidate in last {LOOKBACK_DAYS} days", file=sys.stderr)
        return

    # Sort by score DESC then date DESC (most recent at top score wins)
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
    score, date, path, title = candidates[0]

    print(f"Picked: {path.name} (score={score}, date={date.date()})", file=sys.stderr)
    print(f"  Title: {title}", file=sys.stderr)
    # Stdout = path only, for the workflow to capture
    print(path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
