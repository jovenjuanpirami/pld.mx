#!/usr/bin/env python3
"""
Local development server for PLD.mx
Builds Jekyll-like site and serves on localhost:4000
"""

import os
import re
import http.server
import socketserver
import shutil
import datetime
import math
from pathlib import Path

ROOT = Path(__file__).parent.parent
SITE_DIR = ROOT / "_site"
POSTS_DIR = ROOT / "_posts"
PAGES_DIR = ROOT / "pages"
LAYOUTS_DIR = ROOT / "_layouts"
INCLUDES_DIR = ROOT / "_includes"
ASSETS_DIR = ROOT / "assets"

PORT = 4000


def read_file(path):
    return path.read_text(encoding="utf-8")


def parse_frontmatter(content):
    """Parse YAML-like frontmatter from markdown files."""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    fm_text = parts[1].strip()
    body = parts[2].strip()
    meta = {}
    current_key = None
    current_list = None
    for line in fm_text.split("\n"):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if line.startswith("  - "):
            val = line_stripped.lstrip("- ").strip().strip('"').strip("'")
            if current_list is not None:
                meta[current_key].append(val)
            continue
        if ":" in line_stripped:
            key, _, val = line_stripped.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val:
                meta[key] = val
                current_key = key
                current_list = None
            else:
                meta[key] = []
                current_key = key
                current_list = key
    return meta, body


def markdown_to_html(md):
    """Very basic markdown to HTML conversion."""
    lines = md.split("\n")
    html_lines = []
    in_list = None  # 'ul' or 'ol'
    in_table = False
    in_blockquote = False
    table_header_done = False

    for line in lines:
        stripped = line.strip()

        # Empty line
        if not stripped:
            if in_list:
                html_lines.append(f"</{in_list}>")
                in_list = None
            if in_blockquote:
                html_lines.append("</blockquote>")
                in_blockquote = False
            if in_table:
                html_lines.append("</table>")
                in_table = False
                table_header_done = False
            html_lines.append("")
            continue

        # Raw HTML passthrough
        if stripped.startswith("<"):
            if in_list:
                html_lines.append(f"</{in_list}>")
                in_list = None
            html_lines.append(stripped)
            continue

        # Blockquote
        if stripped.startswith("> "):
            if not in_blockquote:
                html_lines.append("<blockquote>")
                in_blockquote = True
            text = inline_format(stripped[2:])
            html_lines.append(f"<p>{text}</p>")
            continue

        # Table
        if "|" in stripped and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if all(set(c) <= set("-: ") for c in cells):
                table_header_done = True
                continue
            if not in_table:
                html_lines.append("<table>")
                in_table = True
            tag = "th" if not table_header_done else "td"
            row = "".join(f"<{tag}>{inline_format(c)}</{tag}>" for c in cells)
            html_lines.append(f"<tr>{row}</tr>")
            continue

        # Headers
        m = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if m:
            if in_list:
                html_lines.append(f"</{in_list}>")
                in_list = None
            level = len(m.group(1))
            text = inline_format(m.group(2))
            slug = re.sub(r"[^\w\s-]", "", m.group(2).lower())
            slug = re.sub(r"\s+", "-", slug).strip("-")
            html_lines.append(f'<h{level} id="{slug}">{text}</h{level}>')
            continue

        # Unordered list
        if re.match(r"^[-*]\s+", stripped):
            text = inline_format(re.sub(r"^[-*]\s+", "", stripped))
            if in_list != "ul":
                if in_list:
                    html_lines.append(f"</{in_list}>")
                html_lines.append("<ul>")
                in_list = "ul"
            html_lines.append(f"<li>{text}</li>")
            continue

        # Ordered list
        m2 = re.match(r"^\d+\.\s+(.*)", stripped)
        if m2:
            text = inline_format(m2.group(1))
            if in_list != "ol":
                if in_list:
                    html_lines.append(f"</{in_list}>")
                html_lines.append("<ol>")
                in_list = "ol"
            html_lines.append(f"<li>{text}</li>")
            continue

        # Paragraph
        if in_list:
            html_lines.append(f"</{in_list}>")
            in_list = None
        html_lines.append(f"<p>{inline_format(stripped)}</p>")

    if in_list:
        html_lines.append(f"</{in_list}>")
    if in_table:
        html_lines.append("</table>")
    if in_blockquote:
        html_lines.append("</blockquote>")

    return "\n".join(html_lines)


def inline_format(text):
    """Apply inline markdown formatting."""
    # Bold + italic
    text = re.sub(r"\*\*\*(.*?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    # Bold
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)
    # Links
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Inline code
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def format_date(date_str):
    """Format date in Spanish."""
    months = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
    }
    try:
        if isinstance(date_str, str):
            d = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
        else:
            d = date_str
        return f"{d.day} de {months[d.month]}, {d.year}"
    except Exception:
        return str(date_str)


def load_posts():
    """Load all posts from _posts directory."""
    posts = []
    if not POSTS_DIR.exists():
        return posts
    for f in sorted(POSTS_DIR.glob("*.md"), reverse=True):
        content = read_file(f)
        meta, body = parse_frontmatter(content)
        # Extract date and slug from filename
        m = re.match(r"(\d{4}-\d{2}-\d{2})-(.+)\.md", f.name)
        if m:
            meta.setdefault("date", m.group(1))
            meta["slug"] = m.group(2)
        meta["body_md"] = body
        meta["body_html"] = markdown_to_html(body)
        # URL
        cats = meta.get("categories", [])
        cat = cats[0] if isinstance(cats, list) and cats else cats if isinstance(cats, str) else ""
        date_parts = meta.get("date", "2026-01-01")[:10].split("-")
        meta["url"] = f"/{cat}/{date_parts[0]}/{date_parts[1]}/{date_parts[2]}/{meta['slug']}/"
        # Word count / reading time
        word_count = len(body.split())
        meta["reading_time"] = max(1, word_count // 200)
        # Excerpt
        first_para = ""
        for line in body.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-") and not line.startswith("<"):
                first_para = line
                break
        meta["excerpt"] = re.sub(r"\*\*?|`|\[([^\]]+)\]\([^)]+\)", r"\1", first_para)[:200]
        posts.append(meta)
    return posts


def render_include(name, context):
    """Render an include file with simple variable substitution."""
    path = INCLUDES_DIR / name
    if not path.exists():
        return f"<!-- include {name} not found -->"
    return read_file(path)


def render_post_card(post):
    """Render a post card HTML."""
    cats = post.get("categories", [])
    cat = cats[0] if isinstance(cats, list) and cats else ""
    image = post.get("image", "")
    title = post.get("title", "Sin título")
    excerpt = post.get("excerpt", "")
    date = format_date(post.get("date", ""))
    url = post.get("url", "#")

    if image:
        img_html = f'<div class="post-card-image"><img src="{image}" alt="{title}" loading="lazy"></div>'
    else:
        img_html = '''<div class="post-card-image post-card-placeholder">
      <div class="placeholder-icon">
        <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M6 10 L24 2 L42 10 L42 26 C42 38 24 48 24 48 C24 48 6 38 6 26 Z" fill="url(#pg)"/><defs><linearGradient id="pg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#0b4147"/><stop offset="100%" stop-color="#0ad6ac"/></linearGradient></defs></svg>
      </div>
    </div>'''

    return f'''<article class="post-card">
  <a href="{url}" class="post-card-link">
    {img_html}
    <div class="post-card-body">
      {f'<span class="post-card-category">{cat}</span>' if cat else ''}
      <h3 class="post-card-title">{title}</h3>
      <p class="post-card-excerpt">{excerpt[:120]}...</p>
      <time class="post-card-date">{date}</time>
    </div>
  </a>
</article>'''


def build_head(page_meta):
    title = page_meta.get("title", "PLD.mx")
    desc = page_meta.get("description", "Prevención de Lavado de Dinero en México")
    image = page_meta.get("image", "")
    return f'''<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
{f'<meta property="og:image" content="{image}">' if image else ''}
<link rel="icon" type="image/svg+xml" href="/assets/images/favicon.svg">
<link href="https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700,900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/main.css">'''


def build_header():
    return read_file(INCLUDES_DIR / "header.html")


def build_footer():
    return read_file(INCLUDES_DIR / "footer.html").replace(
        "{{ site.time | date: '%Y' }}", str(datetime.datetime.now().year)
    )


def wrap_layout(content, page_meta):
    head = build_head(page_meta)
    header = build_header()
    footer = build_footer()
    return f'''<!DOCTYPE html>
<html lang="es-MX">
<head>
{head}
</head>
<body>
{header}
<main class="site-main">
{content}
</main>
{footer}
<script src="/assets/js/main.js" defer></script>
</body>
</html>'''


def build_index(posts):
    cards = "\n".join(render_post_card(p) for p in posts[:12])
    content = f'''<section class="hero">
  <div class="hero-content container">
    <h1>Prevención de Lavado de Dinero en México</h1>
    <p>Tu fuente diaria de noticias, análisis y recursos sobre PLD, la LFPIORPI y cumplimiento regulatorio para empresas en México.</p>
    <a href="#articulos" class="hero-cta">Ver artículos recientes &darr;</a>
  </div>
</section>
<section id="articulos" class="posts-section">
  <div class="container">
    <h2 class="section-title">Artículos Recientes</h2>
    <div class="posts-grid">
      {cards}
    </div>
  </div>
</section>
<section class="newsletter-section">
  <div class="container">
    <h2>Mantente Informado</h2>
    <p>Publicamos artículos diarios sobre PLD, cumplimiento y regulación en México. Visítanos regularmente para estar al día.</p>
    <a href="/categorias/" class="hero-cta" style="display:inline-flex;">Explorar categorías</a>
  </div>
</section>'''
    meta = {
        "title": "PLD.mx — Noticias y Recursos sobre Prevención de Lavado de Dinero en México",
        "description": "Portal informativo sobre PLD, LFPIORPI y cumplimiento regulatorio. Artículos diarios, guías y recursos para empresas mexicanas.",
    }
    return wrap_layout(content, meta)


def build_post_page(post, posts):
    cats = post.get("categories", [])
    cat = cats[0] if isinstance(cats, list) and cats else ""
    title = post.get("title", "")
    desc = post.get("description", "")
    date = format_date(post.get("date", ""))
    image = post.get("image", "")
    tags = post.get("tags", [])
    body_html = post.get("body_html", "")
    reading_time = post.get("reading_time", 1)

    cat_tag = f'<a href="/categoria/{cat}/" class="post-category-tag">{cat}</a>' if cat else ""
    image_html = f'''<div class="post-hero"><div class="container"><img src="{image}" alt="{title}" loading="eager"></div></div>''' if image else ""

    tags_html = ""
    if tags:
        if isinstance(tags, list):
            tags_html = '<div class="post-tags">' + "".join(f'<span class="tag">#{t}</span>' for t in tags) + "</div>"

    content = f'''<article class="post">
  <header class="post-header">
    <div class="container">
      {cat_tag}
      <h1 class="post-title">{title}</h1>
      {f'<p class="post-subtitle">{desc}</p>' if desc else ''}
      <div class="post-meta">
        <time>{date}</time>
        <span class="post-meta-sep">·</span>
        <span>{reading_time} min de lectura</span>
      </div>
    </div>
  </header>
  {image_html}
  <div class="post-content container">
    {body_html}
  </div>
  <footer class="post-footer container">
    {tags_html}
    <div class="post-share">
      <span>Compartir:</span>
      <a href="#" onclick="return false;">Twitter</a>
      <a href="#" onclick="return false;">LinkedIn</a>
      <a href="#" onclick="return false;">WhatsApp</a>
    </div>
  </footer>
</article>'''
    return wrap_layout(content, post)


def build_page(page_path):
    content = read_file(page_path)
    meta, body = parse_frontmatter(content)

    if page_path.suffix == ".md":
        body_html = markdown_to_html(body)
    else:
        body_html = body

    # For categorias.html, pass through the HTML
    if "categorias" in page_path.name:
        # Extract the raw HTML content
        inner = body_html
    else:
        inner = f'''<div class="page-content container">
  <header class="page-header">
    <h1>{meta.get("title", "")}</h1>
    {f'<p class="page-subtitle">{meta.get("description", "")}</p>' if meta.get("description") else ''}
  </header>
  <div class="page-body">
    {body_html}
  </div>
</div>'''
    return wrap_layout(inner, meta), meta.get("permalink", "")


def build_site():
    """Build the complete site into _site directory."""
    # Clean
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    SITE_DIR.mkdir()

    # Copy assets
    shutil.copytree(ASSETS_DIR, SITE_DIR / "assets")

    # Load posts
    posts = load_posts()

    # Build index
    (SITE_DIR / "index.html").write_text(build_index(posts), encoding="utf-8")

    # Build post pages
    for post in posts:
        url = post["url"].strip("/")
        post_dir = SITE_DIR / url
        post_dir.mkdir(parents=True, exist_ok=True)
        html = build_post_page(post, posts)
        (post_dir / "index.html").write_text(html, encoding="utf-8")

    # Build pages
    for page_path in PAGES_DIR.glob("*"):
        if page_path.suffix in (".md", ".html"):
            html, permalink = build_page(page_path)
            if permalink:
                p = permalink.strip("/")
            else:
                p = page_path.stem
            page_dir = SITE_DIR / p
            page_dir.mkdir(parents=True, exist_ok=True)
            (page_dir / "index.html").write_text(html, encoding="utf-8")

    # Copy CNAME
    cname = ROOT / "CNAME"
    if cname.exists():
        shutil.copy2(cname, SITE_DIR / "CNAME")

    print(f"Built {len(posts)} posts and pages into {SITE_DIR}")


def serve():
    os.chdir(SITE_DIR)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"\n  PLD.mx local server running at:")
        print(f"  http://localhost:{PORT}")
        print(f"\n  Press Ctrl+C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    build_site()
    serve()
