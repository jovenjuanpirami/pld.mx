#!/usr/bin/env python3
"""
PLD.mx — Podcast generator

Converts a Jekyll markdown post into a podcast episode using ElevenLabs (TTS),
then uploads to Buzzsprout. Buzzsprout's RSS feeds out to Spotify, Apple Podcasts,
Amazon Music, etc.

Usage:
    python generate_podcast.py _posts/2026-05-13-foo.md [more_posts.md ...]

Required env vars:
    ELEVENLABS_API_KEY     — ElevenLabs API key
    ELEVENLABS_VOICE_ID    — Voice ID (Spanish MX voice)
    BUZZSPROUT_API_TOKEN   — Buzzsprout API token
    BUZZSPROUT_PODCAST_ID  — Buzzsprout numeric podcast ID

Idempotent: tracks published episodes in _data/podcast_episodes.json and skips
posts that are already published.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests

# ─── Configuration ───────────────────────────────────────────────────────────

ELEVENLABS_MODEL = "eleven_multilingual_v2"   # best multilingual model, supports Spanish
MAX_CHARS_PER_CHUNK = 4500                    # ElevenLabs hard cap is 5000
REPO_ROOT = Path(__file__).parent.parent
POSTS_DIR = REPO_ROOT / "_posts"
TRACKING_FILE = REPO_ROOT / "_data" / "podcast_episodes.json"

ACRONYMS = {
    "LFPIORPI": "Ley Federal para la Prevención e Identificación de Operaciones con Recursos de Procedencia Ilícita",
    "UMA": "Unidad de Medida y Actualización (U M A)",
    "KYC": "Know Your Customer (KYC)",
    "KYB": "Know Your Business (KYB)",
    "EBR": "Evaluación Basada en Riesgo (E B R)",
    "SHCP": "Secretaría de Hacienda y Crédito Público",
    "UIF": "Unidad de Inteligencia Financiera",
    "SAT": "Servicio de Administración Tributaria",
    "PLD": "Prevención de Lavado de Dinero",
    "FT": "Financiamiento al Terrorismo",
    "PEP": "Persona Políticamente Expuesta",
    "GAFI": "Grupo de Acción Financiera Internacional",
    "GAFILAT": "Grupo de Acción Financiera de Latinoamérica",
    "CNBV": "Comisión Nacional Bancaria y de Valores",
    "DOF": "Diario Oficial de la Federación",
    "FGR": "Fiscalía General de la República",
    "AML": "Anti-Money Laundering",
    "VASP": "Proveedor de Servicios de Activos Virtuales",
}

# ─── Markdown parsing ────────────────────────────────────────────────────────


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from markdown body. Returns (metadata, body)."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    _, fm_text, body = parts
    metadata = {}
    for line in fm_text.strip().splitlines():
        if ":" in line and not line.lstrip().startswith("-"):
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata, body


def clean_markdown_for_speech(body: str) -> str:
    """Strip markdown/HTML and make text speakable."""
    text = body

    # Remove HTML blocks (CTA boxes, video embeds, etc.)
    text = re.sub(r"<div[^>]*>.*?</div>", "", text, flags=re.DOTALL)
    text = re.sub(r"<iframe[^>]*>.*?</iframe>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)

    # Remove code fences
    text = re.sub(r"```[^`]*```", "", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Remove markdown tables (lines starting with |)
    text = re.sub(r"^\s*\|.*$", "", text, flags=re.MULTILINE)

    # Convert headers to sentence-ending pauses
    text = re.sub(r"^#{1,6}\s+(.*)$", r"\1.\n", text, flags=re.MULTILINE)

    # [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Bold/italic markers
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)

    # Bullet points and horizontal rules
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^---+\s*$", "", text, flags=re.MULTILINE)

    # Cut the FAQ section (verbose for audio)
    text = re.split(r"(?im)^Preguntas\s+Frecuentes\s*\.?\s*$", text, maxsplit=1)[0]

    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def expand_acronyms_first_use(text: str) -> str:
    """Expand each acronym on its first occurrence only."""
    for acronym, expansion in ACRONYMS.items():
        pattern = rf"\b{re.escape(acronym)}\b"
        match = re.search(pattern, text)
        if match:
            text = text[: match.start()] + expansion + text[match.end():]
    return text


def build_episode_script(metadata: dict, body: str) -> str:
    """Combine intro + cleaned content + outro into final script."""
    title = metadata.get("title", "Análisis PLD")
    cleaned = clean_markdown_for_speech(body)
    cleaned = expand_acronyms_first_use(cleaned)

    intro = (
        f"Bienvenidos a PLD punto MX, su fuente diaria de análisis sobre "
        f"prevención de lavado de dinero en México. "
        f"En el episodio de hoy: {title}."
    )
    outro = (
        "Para leer el análisis completo, visita pld punto MX. "
        "Si te gustó este episodio, suscríbete a nuestro podcast para recibir "
        "más contenido sobre cumplimiento regulatorio, la LFPIORPI y prevención "
        "de lavado de dinero en México."
    )

    return f"{intro}\n\n{cleaned}\n\n{outro}"


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Split text into chunks <= max_chars at paragraph or sentence boundaries."""
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = (current + "\n\n" + para).strip() if current else para
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        # If a single paragraph is too long, split it at sentence boundaries
        if len(para) > max_chars:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            buf = ""
            for sent in sentences:
                cand = (buf + " " + sent).strip() if buf else sent
                if len(cand) <= max_chars:
                    buf = cand
                else:
                    if buf:
                        chunks.append(buf)
                    buf = sent
            current = buf
        else:
            current = para
    if current:
        chunks.append(current)
    return chunks


# ─── ElevenLabs ──────────────────────────────────────────────────────────────


def synthesize_chunk(text: str, voice_id: str, api_key: str) -> bytes:
    """Call ElevenLabs TTS for a single chunk and return MP3 bytes."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }
    response = requests.post(url, headers=headers, json=payload, timeout=180)
    if response.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs error {response.status_code}: {response.text[:500]}"
        )
    return response.content


def synthesize_full(text: str, voice_id: str, api_key: str) -> bytes:
    """Synthesize full text (chunked if needed) and return concatenated MP3."""
    chunks = chunk_text(text, MAX_CHARS_PER_CHUNK)
    print(f"  Synthesizing {len(chunks)} chunk(s), {len(text)} total chars")
    audio_parts = []
    for i, chunk in enumerate(chunks, 1):
        print(f"    [{i}/{len(chunks)}] {len(chunk)} chars")
        audio_parts.append(synthesize_chunk(chunk, voice_id, api_key))
        time.sleep(0.5)
    # MP3 frames can be concatenated naively
    return b"".join(audio_parts)


# ─── Buzzsprout ──────────────────────────────────────────────────────────────


def upload_to_buzzsprout(
    audio_bytes: bytes,
    title: str,
    description: str,
    podcast_id: str,
    api_token: str,
    filename: str,
) -> dict:
    """Upload an episode to Buzzsprout. Returns the API response dict."""
    url = f"https://www.buzzsprout.com/api/{podcast_id}/episodes.json"
    headers = {"Authorization": f"Token token={api_token}"}
    data = {
        "title": title,
        "description": description,
        "summary": description[:250],
        "explicit": "false",
        "private": "false",
    }
    files = {"audio_file": (filename, audio_bytes, "audio/mpeg")}
    response = requests.post(
        url, headers=headers, data=data, files=files, timeout=300
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Buzzsprout error {response.status_code}: {response.text[:500]}"
        )
    return response.json()


# ─── Tracking ────────────────────────────────────────────────────────────────


def load_tracking() -> dict:
    if not TRACKING_FILE.exists():
        return {}
    try:
        return json.loads(TRACKING_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_tracking(data: dict):
    TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACKING_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


# ─── Main flow ───────────────────────────────────────────────────────────────


def process_post(
    post_path: Path,
    voice_id: str,
    eleven_key: str,
    bz_token: str,
    bz_id: str,
    tracking: dict,
) -> bool:
    """Process a single post. Returns True if a new episode was published."""
    slug = post_path.stem
    if slug in tracking:
        print(f"⏭  Skip {slug} (already published as Buzzsprout #{tracking[slug].get('buzzsprout_id')})")
        return False

    print(f"\n▶ Processing {slug}")
    raw = post_path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(raw)
    title = metadata.get("title", slug)
    description_meta = metadata.get("description", "")

    script = build_episode_script(metadata, body)
    print(f"  Script length: {len(script)} chars")

    print(f"  Calling ElevenLabs (voice {voice_id})…")
    audio = synthesize_full(script, voice_id, eleven_key)
    print(f"  Audio generated: {len(audio):,} bytes ({len(audio)/1024:.1f} KB)")

    # Description for Buzzsprout — short hook + link back to article
    article_url = f"https://pld.mx/{metadata.get('categories', 'noticias')}/{slug.split('-', 3)[-1]}/" if "-" in slug else "https://pld.mx"
    bz_description = (
        f"{description_meta}\n\n"
        f"Lee el análisis completo en pld.mx — Prevención de Lavado de Dinero en México."
    )

    print(f"  Uploading to Buzzsprout podcast #{bz_id}…")
    result = upload_to_buzzsprout(
        audio_bytes=audio,
        title=title,
        description=bz_description,
        podcast_id=bz_id,
        api_token=bz_token,
        filename=f"{slug}.mp3",
    )
    episode_id = result.get("id")
    print(f"✓ Published Buzzsprout episode #{episode_id}: {result.get('audio_url', '')}")

    tracking[slug] = {
        "buzzsprout_id": episode_id,
        "title": title,
        "published_at": result.get("published_at"),
        "audio_url": result.get("audio_url"),
    }
    save_tracking(tracking)
    return True


def main():
    eleven_key = os.environ.get("ELEVENLABS_API_KEY")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
    bz_token = os.environ.get("BUZZSPROUT_API_TOKEN")
    bz_id = os.environ.get("BUZZSPROUT_PODCAST_ID")

    missing = [
        name
        for name, val in [
            ("ELEVENLABS_API_KEY", eleven_key),
            ("ELEVENLABS_VOICE_ID", voice_id),
            ("BUZZSPROUT_API_TOKEN", bz_token),
            ("BUZZSPROUT_PODCAST_ID", bz_id),
        ]
        if not val
    ]
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)}")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: generate_podcast.py <post1.md> [<post2.md> ...]")
        sys.exit(1)

    tracking = load_tracking()
    published_count = 0

    for arg in sys.argv[1:]:
        post_path = Path(arg)
        if not post_path.is_absolute():
            post_path = REPO_ROOT / arg
        if not post_path.exists():
            print(f"⚠  Skip (not found): {arg}")
            continue
        try:
            if process_post(post_path, voice_id, eleven_key, bz_token, bz_id, tracking):
                published_count += 1
        except Exception as e:
            print(f"✗ Failed {post_path.name}: {type(e).__name__}: {e}")

    print(f"\nSUMMARY: {published_count} new episode(s) published")


if __name__ == "__main__":
    main()
