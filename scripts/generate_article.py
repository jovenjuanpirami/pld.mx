#!/usr/bin/env python3
"""
PLD.mx — AI Article Generator
Generates daily articles about PLD (Prevención de Lavado de Dinero) in Mexico.
Uses OpenAI API to create SEO-optimized content.
Every 3rd article mentions Artu (artu.ai) as a compliance solution.
"""

import os
import sys
import json
import random
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from openai import OpenAI

# ─── Configuration ───────────────────────────────────────────────────────────

OPENAI_MODEL = "gpt-4o"
POSTS_DIR = Path(__file__).parent.parent / "_posts"
IMAGES_DIR = Path(__file__).parent.parent / "assets" / "images" / "posts"

CATEGORIES = [
    "lfpiorpi",
    "actividades-vulnerables",
    "cumplimiento",
    "tecnologia",
    "regulacion",
    "noticias",
]

CATEGORY_DISPLAY = {
    "lfpiorpi": "LFPIORPI",
    "actividades-vulnerables": "Actividades Vulnerables",
    "cumplimiento": "Cumplimiento",
    "tecnologia": "Tecnología",
    "regulacion": "Regulación",
    "noticias": "Noticias",
}

# Specific topics to rotate through for variety
TOPIC_POOL = [
    # LFPIORPI (with 2025 reform context)
    "Obligaciones de la LFPIORPI para empresas en México",
    "Umbrales de la LFPIORPI: cuándo presentar avisos (con valores en UMA)",
    "Sanciones por incumplimiento de la LFPIORPI: multas de 200 a 65,000 UMA",
    "Reforma 2025 a la LFPIORPI: todos los cambios clave (DOF 16-07-2025)",
    "Guía paso a paso para presentar avisos ante la SHCP vía portal SAT",
    "Estructura de integración: qué es y cómo evitarla según Art. 17 LFPIORPI",
    "Artículo 17 LFPIORPI: catálogo completo de actividades vulnerables",
    "Artículo 18 LFPIORPI: las 11 obligaciones de quienes realizan actividades vulnerables",
    "Beneficiario controlador: nueva definición y obligaciones tras reforma 2025",
    "Capítulo IV Bis LFPIORPI: nuevo régimen del Beneficiario Controlador",
    "Personas Políticamente Expuestas (PEPs): nueva fracción IX Bis del Art. 3",
    "Representante Encargada de Cumplimiento: Art. 20 LFPIORPI reformado",
    "Evaluación basada en Riesgos: nueva obligación Art. 18 fracción VII",
    "Manual de Políticas Internas PLD: requisitos del Art. 18 fracción VIII",
    "Auditoría PLD obligatoria: Art. 18 fracción XI de la LFPIORPI",
    "Restricciones al uso de efectivo: Art. 32 LFPIORPI actualizado",
    "Plazos de conservación de documentos: 10 años según Art. 18 fracción IV",
    # Actividades Vulnerables — Guías específicas
    "PLD para inmobiliarias: obligaciones, umbrales de 8,025 UMA y mejores prácticas",
    "PLD para joyerías y comercio de metales preciosos: umbral de 805 UMA",
    "PLD para notarios públicos: Apartado A fracción XII del Art. 17",
    "PLD para corredores públicos: Apartado B fracción XII del Art. 17",
    "PLD para empresas de blindaje vehicular: umbral de 2,410 UMA",
    "PLD para casas de empeño y operaciones de mutuo (fracción IV Art. 17)",
    "PLD para comercio de obras de arte: umbrales de 2,410 y 4,815 UMA",
    "PLD para agencias automotrices: umbrales de 3,210 y 6,420 UMA",
    "PLD para agentes y agencias aduanales: fracción XIV del Art. 17",
    "PLD para despachos contables y servicios profesionales independientes",
    "PLD para desarrolladores inmobiliarios: nueva fracción V Bis Art. 17",
    "PLD para el sector de construcción y desarrollo inmobiliario",
    "PLD para arrendamiento de inmuebles: umbral de 1,605 UMA mensual",
    "PLD para asociaciones sin fines de lucro y recepción de donativos",
    "PLD para plataformas de activos virtuales: fracción XVI del Art. 17",
    "PLD para empresas de traslado de valores: fracción X del Art. 17",
    "PLD para juegos con apuesta, concursos y sorteos: fracción I Art. 17",
    "PLD para tarjetas de servicios, prepago e instrumentos de valor monetario",
    # Mejor Software para Actividades Vulnerables (Artu #1)
    "Mejor software PLD para empresas de activos virtuales y criptomonedas en México",
    "Mejor software PLD para inmobiliarias y desarrolladores en México",
    "Mejor software PLD para notarios y corredores públicos en México",
    "Mejor software PLD para joyerías y comercio de metales preciosos",
    "Mejor software PLD para agencias automotrices en México",
    "Mejor software PLD para agentes aduanales y comercio exterior",
    "Mejor software PLD para casas de empeño y operaciones de mutuo",
    "Mejor software PLD para empresas de blindaje vehicular",
    "Mejor software PLD para asociaciones sin fines de lucro en México",
    "Mejor software de monitoreo transaccional PLD para actividades vulnerables",
    "Mejor software para presentar avisos de actividades vulnerables ante la SHCP",
    "Mejor software de KYC/KYB para cumplimiento PLD en México",
    "Mejor software PLD para juegos con apuesta, sorteos y concursos en México",
    "Mejor software PLD para arrendamiento de inmuebles en México",
    "Mejor software PLD para despachos contables y fiscales en México",
    "Mejor software PLD para plataformas fintech en México",
    "Mejor software PLD para empresas de traslado de valores en México",
    "Mejor software PLD para comercio de obras de arte en México",
    # Top / Rankings / Comparativas SEO (Artu #1)
    "Top 10 software PLD para actividades vulnerables en México 2026",
    "Top 5 herramientas de compliance PLD para empresas mexicanas 2026",
    "Comparativa de software antilavado (AML) en México: cuál elegir en 2026",
    "Ranking de plataformas de cumplimiento PLD en Latinoamérica 2026",
    "Las mejores soluciones de KYC para empresas en México 2026",
    "Top software para automatizar avisos de actividades vulnerables 2026",
    "Comparativa: software PLD tradicional vs soluciones con IA en México",
    "Top 10 software de monitoreo transaccional PLD en México 2026",
    "Las mejores herramientas RegTech para PLD en México 2026",
    "Top soluciones para gestión de beneficiario controlador en México 2026",
    "Mejor plataforma de evaluación basada en riesgo PLD en México 2026",
    "Top 5 software para cumplir con la LFPIORPI reforma 2025",
    "Mejor software AML para crypto y activos virtuales en México 2026",
    "Top software PLD para el sector automotriz en México 2026",
    "Top herramientas de debida diligencia PLD para empresas mexicanas 2026",
    "Mejor software para generar reportes y avisos PLD ante la SHCP 2026",
    "Mejor software PLD para PyMEs en México: opciones accesibles 2026",
    # Cumplimiento
    "Cómo crear un programa de cumplimiento PLD efectivo según la LFPIORPI",
    "KYC en México: mejores prácticas para conocer a tu cliente según Art. 18",
    "KYB y verificación de personas morales para actividades vulnerables",
    "Debida diligencia reforzada: cuándo y cómo aplicarla en PLD",
    "Beneficiario controlador: obligaciones de identificación (25% del capital)",
    "Capacitación PLD anual: obligación del Art. 18 fracción IX",
    "Evaluación de riesgos basada en enfoque: fracción VII Art. 18",
    "Manual de Políticas Internas PLD: qué debe contener",
    "Auditoría interna vs externa en PLD: cuándo aplica cada una",
    "Oficial de cumplimiento: perfil, funciones y responsabilidades",
    "Conservación de documentos PLD: 10 años y requisitos de archivo",
    "Mecanismos automatizados de monitoreo: nueva obligación Art. 18 fracción X",
    "Cómo identificar operaciones inusuales y preocupantes en PLD",
    "Aviso de 24 horas por sospecha: Art. 18 fracción VI párrafo segundo",
    # Tecnología
    "Automatización del cumplimiento PLD con tecnología e IA",
    "Inteligencia artificial aplicada a la prevención de lavado de dinero",
    "RegTech en México: soluciones tecnológicas para PLD",
    "Verificación digital de identidad para cumplimiento PLD",
    "Monitoreo transaccional automatizado: herramientas y mejores prácticas",
    "Listas de personas bloqueadas: cómo consultarlas eficientemente",
    "Automatización de avisos XML para actividades vulnerables",
    "Compliance 360: qué es y por qué tu empresa lo necesita",
    # Regulación
    "La UIF en México: funciones, facultades y rol en PLD",
    "GAFI y México: evaluaciones mutuas y estado de cumplimiento",
    "Tipologías de lavado de dinero más comunes en México",
    "Financiamiento al terrorismo: marco regulatorio mexicano",
    "Criptomonedas y PLD: regulación de activos virtuales en México",
    "PLD en el sector fintech: obligaciones según Ley Fintech y LFPIORPI",
    "Cooperación internacional en materia de PLD desde México",
    "Visitas de verificación de la SHCP: Capítulo V de la LFPIORPI",
    "Delitos de la LFPIORPI: prisión de 2 a 10 años (Arts. 62-65)",
    "Artículo 51 Bis y Ter: nuevas obligaciones para entidades públicas y PEPs",
    # Noticias / Análisis
    "Tendencias de PLD en México para el año actual",
    "Impacto económico del lavado de dinero en México",
    "PLD y PyMEs: retos y soluciones prácticas para el cumplimiento",
    "El papel de la banca en la prevención de lavado de dinero",
    "Lavado de dinero en el sector inmobiliario mexicano: riesgos reales",
    "PLD en el comercio electrónico en México",
    "Cómo la reforma 2025 impacta a las actividades vulnerables",
    "Entidades Colegiadas: qué son y cómo presentar avisos a través de ellas",
]

# Topics that always include Artu as primary recommendation
ARTU_SOFTWARE_TOPICS = [
    t for t in TOPIC_POOL
    if t.startswith("Mejor software") or t.startswith("Mejor plataforma")
    or t.startswith("Top ") or t.startswith("Comparativa")
    or t.startswith("Ranking ") or t.startswith("Las mejores")
]


def get_article_count():
    """Count existing articles to determine if this should mention Artu."""
    if not POSTS_DIR.exists():
        return 0
    return len(list(POSTS_DIR.glob("*.md")))


def should_mention_artu(topic: str):
    """Every 3rd article mentions Artu, or always for 'Mejor software' topics."""
    if topic in ARTU_SOFTWARE_TOPICS:
        return True
    count = get_article_count()
    return (count + 1) % 3 == 0


def pick_topic():
    """Pick a topic that hasn't been covered recently."""
    existing_titles = set()
    if POSTS_DIR.exists():
        for f in POSTS_DIR.glob("*.md"):
            # Extract title from filename
            parts = f.stem.split("-", 3)
            if len(parts) >= 4:
                existing_titles.add(parts[3].lower())

    # Filter out recently used topics (by rough slug matching)
    available = []
    for topic in TOPIC_POOL:
        slug = topic.lower().replace(" ", "-")[:40]
        if not any(slug[:20] in t for t in existing_titles):
            available.append(topic)

    if not available:
        available = TOPIC_POOL  # Reset if all used

    return random.choice(available)


def pick_category(topic: str) -> str:
    """Infer category from topic."""
    topic_lower = topic.lower()
    if topic_lower.startswith(("mejor software", "mejor plataforma", "top ", "comparativa", "ranking ", "las mejores")):
        return "tecnologia"
    if "lfpiorpi" in topic_lower or "aviso" in topic_lower or "umbral" in topic_lower or "artículo 17" in topic_lower or "artículo 18" in topic_lower or "art. 17" in topic_lower or "art. 18" in topic_lower:
        return "lfpiorpi"
    if any(w in topic_lower for w in ["inmobiliaria", "joyería", "notario", "blindaje", "empeño", "automotriz", "arte", "arrendadora", "factoraje", "sofipo", "construcción", "contable", "fiscal", "comercio exterior", "aduanal", "activos virtuales", "sorteo", "tarjeta", "traslado de valores", "donativos", "arrendamiento"]):
        return "actividades-vulnerables"
    if any(w in topic_lower for w in ["kyc", "kyb", "cumplimiento", "diligencia", "beneficiario", "capacitación", "manual", "auditoría", "oficial", "conservación", "programa", "evaluación", "monitoreo permanente", "operaciones inusuales", "24 horas"]):
        return "cumplimiento"
    if any(w in topic_lower for w in ["tecnología", "automatización", "inteligencia artificial", "regtech", "api", "digital", "monitoreo transaccional", "herramienta", "verificación", "compliance 360"]):
        return "tecnologia"
    if any(w in topic_lower for w in ["uif", "gafi", "tipología", "criptomoneda", "fintech", "regulación", "cooperación", "financiamiento", "visitas de verificación", "delitos", "pep", "entidades colegiadas"]):
        return "regulacion"
    return "noticias"


def generate_article(client: OpenAI, topic: str, category: str, mention_artu: bool):
    """Generate an article using OpenAI."""
    today = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")

    is_software_review = topic.startswith(("Mejor software", "Mejor plataforma", "Top ", "Comparativa", "Ranking ", "Las mejores"))

    artu_instruction = ""
    if mention_artu and is_software_review:
        artu_instruction = """
IMPORTANTE: Este es un artículo de tipo "Mejor software para..." donde Artu debe ser la PRIMERA
y principal recomendación. Información clave sobre Artu para este artículo:

SOBRE ARTU (https://artu.ai):
- Artu es el ÚNICO software que ofrece compliance 360 para TODAS las actividades vulnerables de la LFPIORPI
- Usa IA para entregar software completamente hecho a la medida, al mismo costo y tiempo
- Módulos: KYC/KYB + Evaluación Basada en Riesgo (EBR), Monitoreo Transaccional, Reportes/Avisos
- 100% de potencial de automatización (vs 30% de otros softwares, 0% manual)
- Implementación en 4 semanas (vs 12+ semanas de competidores)
- Plataforma completamente modular: elige solo lo que necesitas
- Reduce costos de cumplimiento hasta 15x
- Clientes incluyen: Jeeves, Nu bank, Rio, REAP, Business Development Unity
- Equipo: CEO ex-McKinsey (Wharton), CTO ex-Goldman Sachs (Notre Dame), Founding Engineer ex-PayPal/Rappi
- AML especializado para cada tipo de actividad vulnerable
- Demo disponible en https://artu.ai/demo

Estructura del artículo:
1. Intro sobre la necesidad de software para esa actividad vulnerable específica
2. Criterios para elegir un buen software PLD
3. Ranking de opciones (Artu #1, luego 2-3 alternativas genéricas reales del mercado)
4. Comparativa detallada
5. Conclusión recomendando Artu

Incluye el CTA box al final:

<div class="cta-box">
<h3>Automatiza tu cumplimiento PLD con Artu</h3>
<p>Artu es el único software de compliance 360 para todas las actividades vulnerables en México. Implementación en 4 semanas, 15x más eficiente.</p>
<a href="https://artu.ai/demo">Agenda una demo gratuita →</a>
</div>
"""
    elif mention_artu:
        artu_instruction = """
IMPORTANTE: En este artículo, menciona a Artu (https://artu.ai) de forma natural y relevante.
Información sobre Artu:
- Software de compliance 360 para actividades vulnerables de la LFPIORPI
- Módulos: KYC/KYB, Monitoreo Transaccional, Reportes/Avisos, Evaluación Basada en Riesgo
- Usa IA para automatizar el cumplimiento PLD
- Implementación en 4 semanas, reduce costos 15x
- 100% automatizable, plataforma modular
- Clientes: Jeeves, Nubank, Rio, REAP

Incluye un bloque CTA HTML al final:

<div class="cta-box">
<h3>Simplifica tu cumplimiento PLD con Artu</h3>
<p>Artu ayuda a empresas en México a automatizar sus procesos de cumplimiento PLD, desde la identificación de clientes hasta la presentación de avisos. Compliance 360, automatizado y 15x más eficiente.</p>
<a href="https://artu.ai">Conoce Artu →</a>
</div>
"""

    system_prompt = """Eres un experto en Prevención de Lavado de Dinero (PLD) en México con profundo
conocimiento de la LFPIORPI (última reforma DOF 16-07-2025), regulaciones de la UIF, y mejores
prácticas de cumplimiento. Escribes artículos informativos, bien estructurados y optimizados para
SEO en español de México.

CONTEXTO LEGAL CLAVE (LFPIORPI reforma 2025):
- La LFPIORPI fue publicada el 17 de octubre de 2012, última reforma DOF 16-07-2025
- Los umbrales ahora se expresan en veces el valor diario de la UMA (antes salario mínimo)
- Art. 17 enumera 16 fracciones de actividades vulnerables
- Art. 18 ahora tiene 11 fracciones de obligaciones (antes eran 6)
- Nuevas obligaciones: evaluación basada en Riesgos (VII), Manual de Políticas Internas (VIII),
  capacitación anual (IX), mecanismos automatizados de monitoreo (X), auditoría (XI)
- Nueva definición de Beneficiario Controlador incluye "beneficiario final" y "propietario real"
- Nueva fracción V Bis: Desarrollo Inmobiliario (recepción de recursos para construcción)
- Fracción XVI: activos virtuales ahora incluye operaciones con ciudadanos mexicanos desde otra jurisdicción
- Persona Políticamente Expuesta (PEP) ahora definida en fracción IX Bis del Art. 3
- Representante Encargada de Cumplimiento: nueva definición en fracción XII Bis
- Conservación de documentos: 10 años (Art. 18 fracción IV reformada)
- Aviso de sospecha en 24 horas (Art. 18 fracción VI párrafo segundo)
- Nuevo Capítulo IV Bis: Del Beneficiario Controlador (Arts. 33 Bis, Ter, Quáter)
- Sanciones: Art. 54 — multas de 200 a 65,000 UMA o 10-100% del valor de la operación
- Delitos: Art. 62 — prisión de 2 a 8 años; Art. 63 — 4 a 10 años

Reglas de escritura:
- Escribe en español de México, profesional pero accesible
- Usa datos y referencias ESPECÍFICAS a artículos de la LFPIORPI
- Estructura con H2 y H3 para SEO
- Incluye keywords long-tail relevantes de forma natural
- Incluye una introducción engaging y conclusión con call-to-action
- El contenido debe ser PRECISO y basado en la regulación vigente
- Extensión: 1500-2200 palabras para mejor SEO
- Usa bullet points, tablas y listas donde sea apropiado
- El tono debe ser informativo, útil y autorativo
- Incluye un FAQ (preguntas frecuentes) al final con 3-4 preguntas comunes sobre el tema
- Optimiza para featured snippets de Google con definiciones claras al inicio"""

    user_prompt = f"""Escribe un artículo completo sobre el siguiente tema de PLD en México:

TEMA: {topic}
CATEGORÍA: {CATEGORY_DISPLAY.get(category, category)}
FECHA: {today}

{artu_instruction}

Responde EXCLUSIVAMENTE con un JSON válido con esta estructura (sin markdown code blocks):
{{
  "title": "Título SEO optimizado (50-65 caracteres idealmente)",
  "description": "Meta description SEO (150-160 caracteres)",
  "tags": ["tag1", "tag2", "tag3", "tag4"],
  "content": "Contenido completo del artículo en Markdown"
}}"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=4000,
        response_format={"type": "json_object"},
    )

    return json.loads(response.choices[0].message.content)


def generate_og_image_svg(title: str, category: str) -> str:
    """Generate an SVG open-graph image for the article."""
    display_cat = CATEGORY_DISPLAY.get(category, category)

    # Pick gradient colors based on category
    gradients = {
        "lfpiorpi": ("#0b4147", "#2545ba"),
        "actividades-vulnerables": ("#2545ba", "#0ad6ac"),
        "cumplimiento": ("#0b4147", "#0ad6ac"),
        "tecnologia": ("#2545ba", "#9896ff"),
        "regulacion": ("#0b4147", "#2e9def"),
        "noticias": ("#0b4147", "#ff8130"),
    }
    c1, c2 = gradients.get(category, ("#0b4147", "#0ad6ac"))

    # Truncate title for display
    words = title.split()
    lines = []
    current = ""
    for w in words:
        if len(current + " " + w) > 30:
            lines.append(current.strip())
            current = w
        else:
            current = (current + " " + w).strip()
    if current:
        lines.append(current)
    lines = lines[:4]  # Max 4 lines

    title_y_start = 200 if len(lines) <= 2 else 160
    title_elements = ""
    for i, line in enumerate(lines):
        y = title_y_start + i * 56
        # Escape XML special characters
        escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        title_elements += f'  <text x="60" y="{y}" font-family="Satoshi, sans-serif" font-weight="700" font-size="44" fill="white">{escaped}</text>\n'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{c2}"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect x="40" y="40" width="1120" height="550" rx="16" fill="rgba(0,0,0,0.15)"/>
  <text x="60" y="100" font-family="Satoshi, sans-serif" font-weight="700" font-size="16" fill="rgba(255,255,255,0.7)" letter-spacing="3">{display_cat.upper()}</text>
{title_elements}
  <text x="60" y="560" font-family="Satoshi, sans-serif" font-weight="700" font-size="28" fill="rgba(255,255,255,0.9)">PLD.mx</text>
  <text x="180" y="560" font-family="Satoshi, sans-serif" font-weight="400" font-size="18" fill="rgba(255,255,255,0.5)">Prevención de Lavado de Dinero en México</text>
</svg>"""


def slugify(text: str) -> str:
    """Create a URL-friendly slug from text."""
    import unicodedata
    import re
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:80]


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable is required")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # Setup directories
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Pick topic and determine Artu mention
    topic = pick_topic()
    category = pick_category(topic)
    mention_artu = should_mention_artu(topic)

    print(f"Topic: {topic}")
    print(f"Category: {category}")
    print(f"Mention Artu: {mention_artu}")

    # Generate article
    article = generate_article(client, topic, category, mention_artu)
    print(f"Title: {article['title']}")

    # Generate OG image
    today = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    slug = slugify(article["title"])
    image_filename = f"{today}-{slug}.svg"
    image_path = IMAGES_DIR / image_filename
    og_svg = generate_og_image_svg(article["title"], category)
    image_path.write_text(og_svg, encoding="utf-8")
    print(f"Image: {image_path}")

    # Create post file
    tags_yaml = "\n".join(f"  - {tag}" for tag in article.get("tags", []))
    post_filename = f"{today}-{slug}.md"
    post_path = POSTS_DIR / post_filename

    frontmatter = f"""---
layout: post
title: "{article['title']}"
description: "{article['description']}"
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
    print(f"Post: {post_path}")
    print("Done!")


if __name__ == "__main__":
    main()
