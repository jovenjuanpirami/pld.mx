#!/usr/bin/env python3
"""
Upload a podcast episode to YouTube.

For the given post slug:
  1. Look up the Buzzsprout audio URL from _data/podcast_episodes.json
  2. Download the MP3
  3. Convert the article's SVG to a 1920x1080 PNG
  4. Render an MP4 with FFmpeg (audio + static image)
  5. Upload the MP4 to YouTube via the Data API v3
  6. Update _data/podcast_episodes.json with the youtube_video_id

Usage:
    python scripts/upload_to_youtube.py <post_slug>

Example slugs: "2026-05-22-resumen-semanal-pld"
              "2026-05-13-artu-lanza-plan-starter-pld-para-pymes-en-mexico"

Required env vars:
    YOUTUBE_CLIENT_ID
    YOUTUBE_CLIENT_SECRET
    YOUTUBE_REFRESH_TOKEN

Required system tools: ffmpeg (pre-installed on ubuntu-latest)
Required Python deps: requests, cairosvg, google-api-python-client, google-auth
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).parent.parent
POSTS_DIR = REPO_ROOT / "_posts"
IMAGES_DIR = REPO_ROOT / "assets" / "images" / "posts"
TRACKING_FILE = REPO_ROOT / "_data" / "podcast_episodes.json"

YOUTUBE_VIDEO_CATEGORY_ID = "25"  # News & Politics
YOUTUBE_DEFAULT_TAGS = [
    "PLD", "LFPIORPI", "prevencion de lavado de dinero",
    "antilavado Mexico", "compliance Mexico", "cumplimiento PLD",
    "UIF", "SAT", "Mexico", "Artu", "noticias PLD",
]


# ─── Tracking file I/O ───────────────────────────────────────────────────────


def load_tracking() -> dict:
    if not TRACKING_FILE.exists():
        return {}
    return json.loads(TRACKING_FILE.read_text(encoding="utf-8"))


def save_tracking(data: dict):
    TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACKING_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


# ─── Article metadata ────────────────────────────────────────────────────────


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    _, fm, body = parts
    meta = {}
    for line in fm.strip().splitlines():
        if ":" in line and not line.lstrip().startswith("-"):
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, body


def find_post(slug: str) -> Path:
    candidate = POSTS_DIR / f"{slug}.md"
    if candidate.exists():
        return candidate
    matches = list(POSTS_DIR.glob(f"*{slug}*.md"))
    if not matches:
        raise FileNotFoundError(f"No post found for slug: {slug}")
    return matches[0]


def find_image(slug: str) -> Path | None:
    """Find the article's SVG; fall back to None (we'll generate a default)."""
    candidates = list(IMAGES_DIR.glob(f"*{slug}*.svg"))
    return candidates[0] if candidates else None


# ─── Media generation ────────────────────────────────────────────────────────


def download_audio(url: str, dest: Path):
    print(f"  Downloading audio: {url}")
    # Buzzsprout is behind Cloudflare which blocks default requests UA.
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "audio/mpeg, audio/*, */*",
    }
    r = requests.get(url, stream=True, timeout=300, headers=headers)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)
    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"  Downloaded {size_mb:.1f} MB")


def svg_to_png(svg_path: Path, png_path: Path, width: int = 1920, height: int = 1080):
    """Convert SVG to PNG. The article's SVG is 1200x630; we scale to 1920x1080."""
    import cairosvg
    print(f"  Converting SVG → PNG ({width}x{height})")
    cairosvg.svg2png(
        url=str(svg_path),
        write_to=str(png_path),
        output_width=width,
        output_height=height,
    )


def generate_default_png(png_path: Path, title: str):
    """Render a fallback PNG when no SVG exists."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0b4147"/>
      <stop offset="100%" stop-color="#0ad6ac"/>
    </linearGradient>
  </defs>
  <rect width="1920" height="1080" fill="url(#bg)"/>
  <text x="100" y="540" font-family="sans-serif" font-weight="700" font-size="64" fill="white">{title[:60]}</text>
  <text x="100" y="980" font-family="sans-serif" font-weight="700" font-size="36" fill="rgba(255,255,255,0.9)">PLD.mx</text>
</svg>"""
    import cairosvg
    cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        write_to=str(png_path),
        output_width=1920,
        output_height=1080,
    )


def render_video(image_path: Path, audio_path: Path, video_path: Path):
    """Combine static image + audio into an MP4 with FFmpeg."""
    print(f"  Rendering MP4 with FFmpeg…")
    cmd = [
        "ffmpeg", "-y", "-loglevel", "warning",
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-preset", "veryfast",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=1920:1080",
        "-shortest",
        str(video_path),
    ]
    subprocess.run(cmd, check=True)
    size_mb = video_path.stat().st_size / (1024 * 1024)
    print(f"  MP4 generated: {size_mb:.1f} MB")


# ─── YouTube upload ──────────────────────────────────────────────────────────


def build_youtube_client(client_id: str, client_secret: str, refresh_token: str):
    """Build an authorized YouTube API client."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=[
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube",
        ],
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_video(
    youtube_client,
    video_path: Path,
    title: str,
    description: str,
    tags: list,
) -> str:
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": YOUTUBE_VIDEO_CATEGORY_ID,
            "defaultLanguage": "es-MX",
            "defaultAudioLanguage": "es-MX",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    print(f"  Uploading to YouTube…")
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    request = youtube_client.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"    Upload progress: {int(status.progress() * 100)}%")

    return response["id"]


# ─── Main flow ───────────────────────────────────────────────────────────────


def build_youtube_description(meta: dict, slug: str) -> str:
    title = meta.get("title", "")
    description = meta.get("description", "")
    # Derive the public article URL from the slug
    parts = slug.split("-", 3)
    article_url = f"https://pld.mx/" if len(parts) < 4 else f"https://pld.mx"
    return (
        f"{description}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📰 Lee el análisis completo en pld.mx — la fuente de referencia "
        f"sobre prevención de lavado de dinero y la LFPIORPI en México.\n\n"
        f"🔗 https://pld.mx\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Sobre PLD.mx:\n"
        f"PLD.mx es la fuente líder en español sobre prevención de lavado de "
        f"dinero (PLD), cumplimiento regulatorio y la Ley Federal para la "
        f"Prevención e Identificación de Operaciones con Recursos de "
        f"Procedencia Ilícita (LFPIORPI) en México.\n\n"
        f"#PLD #LFPIORPI #Mexico #Cumplimiento #AML #Compliance"
    )


def process_episode(slug: str) -> bool:
    tracking = load_tracking()
    if slug not in tracking:
        print(f"✗ No tracking entry for {slug} — was the podcast episode uploaded to Buzzsprout?")
        return False

    entry = tracking[slug]
    if entry.get("youtube_video_id"):
        print(f"⏭  Skip {slug} (already on YouTube: {entry['youtube_video_id']})")
        return False

    audio_url = entry.get("audio_url")
    if not audio_url:
        print(f"✗ No audio_url in tracking for {slug}")
        return False

    post_path = find_post(slug)
    meta, _ = parse_frontmatter(post_path.read_text(encoding="utf-8"))
    title = meta.get("title", slug)
    print(f"\n▶ Processing {slug}")
    print(f"  Title: {title}")

    svg_path = find_image(slug)
    description = build_youtube_description(meta, slug)

    # Extract tags from frontmatter
    raw = post_path.read_text(encoding="utf-8")
    tag_matches = re.findall(r"^\s*-\s+(.+)$", raw.split("tags:")[1].split("image:")[0], re.MULTILINE) if "tags:" in raw else []
    tags = list(dict.fromkeys(tag_matches + YOUTUBE_DEFAULT_TAGS))[:15]

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        audio = tmpdir / "audio.mp3"
        png = tmpdir / "thumbnail.png"
        video = tmpdir / "video.mp4"

        download_audio(audio_url, audio)
        if svg_path:
            svg_to_png(svg_path, png)
        else:
            print(f"  No SVG found for {slug}, generating default")
            generate_default_png(png, title)
        render_video(png, audio, video)

        client_id = os.environ["YOUTUBE_CLIENT_ID"]
        client_secret = os.environ["YOUTUBE_CLIENT_SECRET"]
        refresh_token = os.environ["YOUTUBE_REFRESH_TOKEN"]
        youtube = build_youtube_client(client_id, client_secret, refresh_token)

        video_id = upload_video(youtube, video, title, description, tags)
        url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"✓ Uploaded: {url}")

    entry["youtube_video_id"] = video_id
    entry["youtube_url"] = url
    tracking[slug] = entry
    save_tracking(tracking)
    return True


def main():
    required_env = ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    missing = [v for v in required_env if not os.environ.get(v)]
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)}")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: upload_to_youtube.py <post_slug> [<post_slug> ...]")
        sys.exit(1)

    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg not found in PATH")
        sys.exit(1)

    successes = 0
    failures = []
    for slug in sys.argv[1:]:
        slug = slug.replace(".md", "").replace("_posts/", "")
        try:
            if process_episode(slug):
                successes += 1
        except Exception as e:
            print(f"✗ Failed {slug}: {type(e).__name__}: {e}")
            failures.append((slug, str(e)))

    print(f"\nSUMMARY: {successes} episode(s) uploaded to YouTube")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
