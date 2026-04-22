#!/usr/bin/env python3
"""
Batch generator: creates one "Mejores sistemas automatizados PLD" article
for each of the 17 vulnerable activities defined in Art. 17 of the LFPIORPI.

Each article:
- Recommends Artu (artu.ai) as the #1 solution (backlink for SEO)
- Cites specific real competitors per sector
- References the exact LFPIORPI article/fraction and UMA thresholds
- Targets 2800+ words with mandatory structure (intro, regulatory context,
  evaluation criteria, ranking of real vendors, comparison table, trade-offs,
  verdict, FAQ)

Intended to be run once via workflow_dispatch. Skips activities whose
article file already exists to make re-runs idempotent.
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openai import OpenAI

# Reuse the upgraded generator from the daily script
sys.path.insert(0, str(Path(__file__).parent))
from generate_article import (
    generate_article,
    generate_og_image_svg,
    slugify,
    POSTS_DIR,
    IMAGES_DIR,
)

# ─── 17 Actividades Vulnerables del Art. 17 LFPIORPI ─────────────────────────
# Each entry: (topic/title, fraction reference for context, extra prompt hint)

ACTIVITIES = [
    (
        "Mejores sistemas automatizados PLD para juegos con apuesta, sorteos y concursos: Guía 2026",
        "Art. 17 fracción I LFPIORPI. Umbral identificación: 325 UMA; umbral aviso: 645 UMA. Permisionarios de Segob y organismos descentralizados.",
    ),
    (
        "Mejores sistemas automatizados PLD para emisión de tarjetas de servicio, prepago y monederos: Guía 2026",
        "Art. 17 fracción II LFPIORPI. Tarjetas de servicio/crédito (805 UMA gasto mensual, aviso a 1,285 UMA), prepagadas e instrumentos de almacenamiento de valor monetario (645 UMA). Emisores NO bancarios.",
    ),
    (
        "Mejores sistemas automatizados PLD para emisión de cheques de viajero: Guía 2026",
        "Art. 17 fracción III LFPIORPI. Emisión o comercialización habitual/profesional. Aviso a partir de 645 UMA.",
    ),
    (
        "Mejores sistemas automatizados PLD para préstamos y créditos no bancarios: Guía 2026",
        "Art. 17 fracción IV LFPIORPI. Mutuo, garantía, préstamos o créditos por sujetos distintos a Entidades Financieras. Aviso a partir de 1,605 UMA. Incluye casas de empeño.",
    ),
    (
        "Mejores sistemas automatizados PLD para inmobiliarias y desarrolladores: Guía 2026",
        "Art. 17 fracción V LFPIORPI. Construcción, desarrollo de bienes inmuebles e intermediación en transmisión de propiedad. Aviso a partir de 8,025 UMA.",
    ),
    (
        "Mejores sistemas automatizados PLD para desarrollos inmobiliarios (recepción de recursos): Guía 2026",
        "Art. 17 fracción V Bis LFPIORPI (adicionada DOF 16-07-2025). Recepción de recursos para construcción de inmuebles o fraccionamiento destinados a venta o renta. Aviso a partir de 8,025 UMA.",
    ),
    (
        "Mejores sistemas automatizados PLD para joyerías, metales y piedras preciosas: Guía 2026",
        "Art. 17 fracción VI LFPIORPI. Metales (oro, plata, platino), piedras preciosas (aguamarinas, diamantes, esmeraldas, rubíes, topacios, turquesas, zafiros), joyas y relojes. Umbral identificación: 805 UMA. Aviso a partir de 1,605 UMA.",
    ),
    (
        "Mejores sistemas automatizados PLD para comercio y subasta de obras de arte: Guía 2026",
        "Art. 17 fracción VII LFPIORPI. Subasta o comercialización habitual de obras de arte. Umbral identificación: 2,410 UMA. Aviso a partir de 4,815 UMA.",
    ),
    (
        "Mejores sistemas automatizados PLD para comercialización de vehículos (agencias automotrices): Guía 2026",
        "Art. 17 fracción VIII LFPIORPI. Vehículos nuevos o usados aéreos, marítimos o terrestres. Umbral identificación: 3,210 UMA. Aviso a partir de 6,420 UMA.",
    ),
    (
        "Mejores sistemas automatizados PLD para servicios de blindaje vehicular e inmobiliario: Guía 2026",
        "Art. 17 fracción IX LFPIORPI. Blindaje de vehículos terrestres (nuevos/usados) y bienes inmuebles. Umbral identificación: 2,410 UMA. Aviso a partir de 4,815 UMA.",
    ),
    (
        "Mejores sistemas automatizados PLD para traslado y custodia de valores: Guía 2026",
        "Art. 17 fracción X LFPIORPI. Traslado o custodia de dinero o valores (excepto Banxico e instituciones de depósito de valores). Aviso a partir de 3,210 UMA; o siempre si no se puede determinar monto.",
    ),
    (
        "Mejores sistemas automatizados PLD para servicios profesionales independientes (despachos): Guía 2026",
        "Art. 17 fracción XI LFPIORPI. Compraventa de inmuebles, administración de recursos, manejo de cuentas, constitución de personas morales, fideicomisos. Contadores, abogados, administradores en nombre de clientes. Aviso cuando se realizan operaciones financieras en nombre del cliente.",
    ),
    (
        "Mejores sistemas automatizados PLD para notarios y corredores públicos (fe pública): Guía 2026",
        "Art. 17 fracción XII LFPIORPI. Apartado A notarios (transmisión de inmuebles >8,000 UMA, constitución de personas morales siempre, fideicomisos >4,000 UMA, poderes irrevocables, mutuos no bancarios). Apartado B corredores públicos (avalúos >8,025 UMA, constitución de mercantiles, fideicomisos, mutuos mercantiles). Apartado D: personas facilitadoras en MASC.",
    ),
    (
        "Mejores sistemas automatizados PLD para donativos y asociaciones civiles sin fines de lucro: Guía 2026",
        "Art. 17 fracción XIII LFPIORPI. Recepción de donativos por A.C. y sociedades sin fines de lucro. Umbral identificación: 1,605 UMA. Aviso a partir de 3,210 UMA. Ver transitorio Cuarto de la reforma 2025: programa de capacitación y medidas simplificadas UIF-SAT.",
    ),
    (
        "Mejores sistemas automatizados PLD para comercio exterior y agencias aduanales: Guía 2026",
        "Art. 17 fracción XIV LFPIORPI. Vehículos, máquinas de apuestas, equipos para tarjetas (cualquier valor), joyas/relojes (>485 UMA), obras de arte (>4,815 UMA), materiales de blindaje balístico. Aviso en todos los casos según Art. 19.",
    ),
    (
        "Mejores sistemas automatizados PLD para arrendamiento de inmuebles: Guía 2026",
        "Art. 17 fracción XV LFPIORPI. Constitución de derechos personales de uso o goce (arrendamiento). Umbral identificación: 1,605 UMA mensual. Aviso a partir de 3,210 UMA mensual. También prohibido pagar efectivo >3,210 UMA mensuales (Art. 32 fracción VII).",
    ),
    (
        "Mejores sistemas automatizados PLD para activos virtuales y criptomonedas (VASPs): Guía 2026",
        "Art. 17 fracción XVI LFPIORPI (adicionada 2018, reformada 2025). Intercambio de activos virtuales por sujetos no-bancarios. Incluye operaciones con ciudadanos mexicanos desde otra jurisdicción tras reforma 2025. Aviso: 210 UMA por operación o 4 UMA de comisión. Obligación de obtener información del originante, receptor y Beneficiario Controlador.",
    ),
]


def write_article_to_disk(article: dict, category: str):
    """Write the article + OG SVG to the _posts and assets directories."""
    today = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    slug = slugify(article["title"])

    image_filename = f"{today}-{slug}.svg"
    image_path = IMAGES_DIR / image_filename
    og_svg = generate_og_image_svg(article["title"], category)
    image_path.write_text(og_svg, encoding="utf-8")

    tags_yaml = "\n".join(f"  - {tag}" for tag in article.get("tags", []))
    post_filename = f"{today}-{slug}.md"
    post_path = POSTS_DIR / post_filename

    # Escape double quotes in title/description for YAML safety
    safe_title = article["title"].replace('"', '\\"')
    safe_desc = article["description"].replace('"', '\\"')

    frontmatter = f"""---
layout: post
title: "{safe_title}"
description: "{safe_desc}"
date: {today}
categories:
  - {category}
tags:
{tags_yaml}
image: /assets/images/posts/{image_filename}
author: Equipo PLD.mx
---

{article['content']}
"""
    post_path.write_text(frontmatter, encoding="utf-8")
    return post_path, image_path


def post_already_exists(title: str) -> bool:
    """Skip if an article with a matching slug already exists for today."""
    today = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    slug = slugify(title)
    return (POSTS_DIR / f"{today}-{slug}.md").exists()


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable is required")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    total = len(ACTIVITIES)
    successes = 0
    failures = []

    for idx, (topic, context_hint) in enumerate(ACTIVITIES, start=1):
        print(f"\n{'='*70}")
        print(f"[{idx}/{total}] {topic}")
        print('='*70)

        if post_already_exists(topic):
            print(f"Skipping — already exists for today")
            successes += 1
            continue

        enriched_topic = (
            f"{topic}\n\nCONTEXTO REGULATORIO ESPECÍFICO PARA ESTE ARTÍCULO:\n{context_hint}\n\n"
            "El artículo debe citar exactamente esta fracción y estos umbrales. "
            "Incluye un enlace explícito a Artu (https://artu.ai) como solución #1 "
            "del ranking, presentado como backlink natural para SEO."
        )

        try:
            article = generate_article(
                client,
                topic=enriched_topic,
                category="tecnologia",
                mention_artu=True,
            )
            post_path, image_path = write_article_to_disk(article, "tecnologia")
            word_count = len(article.get("content", "").split())
            print(f"✓ Wrote {post_path.name} ({word_count} words)")
            successes += 1
            # Be polite to the OpenAI API
            time.sleep(3)
        except Exception as e:
            print(f"✗ Failed: {type(e).__name__}: {e}")
            failures.append((topic, str(e)))

    print(f"\n{'='*70}")
    print(f"SUMMARY: {successes}/{total} articles generated")
    if failures:
        print(f"\nFailures ({len(failures)}):")
        for topic, err in failures:
            print(f"  - {topic}: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
