#!/usr/bin/env python3
"""
PLD.mx — AI Article Generator
Generates daily articles about PLD (Prevención de Lavado de Dinero) in Mexico.
Uses OpenAI API to create SEO-optimized content.
Every 5th article mentions Artu (artu.ai) in prose; software reviews always do.
El cierre con CTA lo pone el layout (post-cta.html), no el modelo.

Cada post nuevo guarda en `topic:` el tema del que salió, para no repetirlo.
Si todos los temas del pool ya están cubiertos, el modelo propone temas nuevos que
no se empalmen con nada publicado; solo si eso falla se actualiza el artículo más
antiguo sobre un tema (misma URL, `last_modified_at` nuevo).
"""

import os
import sys
import json
import random
import re
import unicodedata
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import yaml
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
    # (nov-2026) Sin temas de top/mejor/ranking/comparativa: se concentran en /top-software-pld/ y en
    # un ranking por giro, que se mantienen a mano con datos verificados (_data/competidores.yml).
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

# Temas prácticos de cola larga (nov-2026, cuando el pool original se agotó). Se revisaron a mano
# contra los títulos publicados, así que solo cuentan como cubiertos cuando un post los trae en
# `topic:`; la comparación por palabras los daba por cubiertos con títulos genéricos como
# «Artículo 18 LFPIORPI: 11 Obligaciones en Actividades Vulnerables».
TEMAS_REVISADOS = [
    "Acumulación de operaciones en seis meses: cómo saber si ya debes presentar aviso",
    "Informe en ceros: qué hacer el mes en que no tuviste operaciones avisables",
    "Calendario mensual de cumplimiento PLD: fechas y tareas para no fallar el día 17",
    "Alta en el portal de prevención de lavado de dinero del SAT paso a paso",
    "Cómo dar de baja o modificar tu registro de actividad vulnerable ante el SAT",
    "Habitualidad y profesionalidad: cuándo tu negocio realiza una actividad vulnerable",
    "Expediente de identificación de persona física: lista de documentos y datos",
    "Expediente de identificación de persona moral: lista de documentos y datos",
    "Clientes extranjeros en actividades vulnerables: cómo identificarlos correctamente",
    "Qué hacer si un cliente se niega a entregar información de identificación",
    "Coincidencia en la Lista de Personas Bloqueadas: qué hacer paso a paso",
    "Matriz de riesgo PLD: cómo ponderar clientes, productos, geografía y canales",
    "Cada cuánto actualizar el expediente del cliente según su nivel de riesgo",
    "Cómo preparar a tu empresa para una visita de verificación del SAT en materia PLD",
    "Errores frecuentes al presentar avisos XML de actividades vulnerables y cómo evitarlos",
    "Señales de alerta de lavado de dinero en la venta de inmuebles",
    "Señales de alerta de lavado de dinero en el arrendamiento de inmuebles",
    "Señales de alerta de lavado de dinero en la venta de vehículos",
    "Señales de alerta de lavado de dinero en joyerías y venta de relojes",
    "Señales de alerta en plataformas de activos virtuales para el cumplimiento PLD",
    "Señales de alerta en la recepción de donativos para asociaciones civiles",
    "Fraccionamiento de operaciones para evadir umbrales: cómo detectarlo",
    "Temario mínimo de la capacitación PLD y cómo conservar la evidencia",
    "Cómo designar al responsable encargado de cumplimiento ante el SAT",
    "Responsabilidades del consejo de administración en la prevención de lavado de dinero",
    "Cómo responder a un requerimiento de información del SAT o la UIF",
    "Debida diligencia de proveedores, socios y terceros en PLD",
    "Beneficiario controlador en fideicomisos: cómo identificarlo",
    "Beneficiario controlador en estructuras corporativas complejas: método práctico",
    "Personas políticamente expuestas como clientes: medidas de debida diligencia",
    "Uso de la e.firma en el cumplimiento PLD: avisos, registro y representantes",
    "Ventas en preventa de vivienda y PLD: obligaciones del desarrollador",
    "Operaciones en dólares en actividades vulnerables: qué considerar para PLD",
    "Préstamos entre particulares: cuándo el mutuo es actividad vulnerable",
    "Grupos empresariales: cómo organizar el cumplimiento PLD entre varias empresas",
    "Compraventa de terrenos y lotes: riesgos de lavado de dinero y controles",
]
TOPIC_POOL = TOPIC_POOL + TEMAS_REVISADOS

# Ya no se generan rankings de software (nov-2026).
ARTU_SOFTWARE_TOPICS: list[str] = []


def get_article_count():
    """Count existing articles to determine if this should mention Artu."""
    if not POSTS_DIR.exists():
        return 0
    return len(list(POSTS_DIR.glob("*.md")))


def should_mention_artu(topic: str):
    """Every 5th article mentions Artu in prose; software reviews always do.

    The end-of-article CTA is rendered by the layout for every post, so the
    prose mention only needs to appear where it adds context.
    """
    if topic in ARTU_SOFTWARE_TOPICS:
        return True
    count = get_article_count()
    return (count + 1) % 5 == 0


STOPWORDS = {
    "de", "la", "el", "en", "y", "para", "del", "los", "las", "a", "con", "por", "su", "sus",
    "que", "un", "una", "al", "como", "mexico", "mexicana", "mexicanas", "mexicano", "mexicanos",
    "pld", "lfpiorpi", "guia", "2025", "2026", "2027", "art", "articulo", "ley", "sobre", "the",
    "e", "o", "u", "es", "mas", "segun", "clave", "claves", "todos", "todas", "nuevo", "nueva",
    "nuevos", "nuevas", "empresa", "empresas", "completa", "completo", "practica", "practicas",
}


def _keywords(text: str) -> set:
    """Raíces de las palabras clave de un título: sin acentos, minúsculas, sin palabras vacías.

    Se recorta cada palabra a sus primeros cinco caracteres para que
    "presentar"/"presentarlos" o "inmobiliaria"/"inmobiliarias" cuenten como la misma.
    """
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    words = [w for w in re.findall(r"[a-z0-9]+", text) if w not in STOPWORDS and len(w) > 2]
    return {SYNONYMS.get(w, w)[:5] for w in words}


# Palabras distintas que expresan la misma intención de búsqueda.
SYNONYMS = {
    "sistema": "software", "sistemas": "software", "plataforma": "software",
    "plataformas": "software", "herramienta": "software", "herramientas": "software",
    "solucion": "software", "soluciones": "software",
    "mejores": "mejor", "top": "mejor", "ranking": "mejor", "comparativa": "mejor",
}


def _existing_posts():
    """Posts publicados como (ruta, keywords del título, fecha de frescura, refresh_permitido,
    tema de origen | None, título).

    La fecha de frescura es `last_modified_at` si existe, si no la del archivo, para
    que un artículo recién actualizado no vuelva a elegirse al día siguiente.
    Un post con `refresh: false` en el front matter nunca se sobrescribe.
    """
    posts = []
    for f in POSTS_DIR.glob("*.md"):
        if "resumen-semanal" in f.name:
            continue
        head = f.read_text(encoding="utf-8")[:2500]
        m = re.search(r'^title:\s*"?(.*?)"?\s*$', head, re.M)
        if not m:
            continue
        mod = re.search(r"^last_modified_at:\s*(\d{4}-\d{2}-\d{2})", head, re.M)
        fresh = max(f.name[:10], mod.group(1) if mod else "")
        refresh_ok = not re.search(r"^refresh:\s*false", head, re.M)
        t = re.search(r'^topic:\s*"?(.*?)"?\s*$', head, re.M)
        posts.append((f, _keywords(m.group(1)), fresh, refresh_ok, t.group(1) if t else None, m.group(1)))
    return posts


def _covers(topic_words: set, title_words: set) -> bool:
    """Un post cubre un tema si comparten el 60 % de las palabras del más corto.

    Coeficiente de solapamiento en vez de Jaccard: los temas del pool traen
    aclaraciones entre paréntesis que el título publicado no repite, y eso no
    debe contar en contra.
    """
    if not topic_words or not title_words:
        return False
    return len(topic_words & title_words) / min(len(topic_words), len(title_words)) >= 0.6


def pick_topic(client: OpenAI | None = None):
    """Elige un tema del pool que aún no esté cubierto por ningún post.

    Un tema está cubierto si algún post lo trae en `topic:` o si su título se empalma
    con el tema (antes solo contaba el título, y un tema genérico como «Tendencias de PLD
    en México para el año actual» nunca se daba por cubierto: salió 12 días seguidos).
    Si todos están cubiertos, el modelo propone uno nuevo; si no lo logra, devuelve el
    post más viejo (por frescura) sobre uno de ellos para actualizarlo en su misma URL.

    Devuelve (tema, ruta_del_post_a_actualizar | None).
    """
    posts = _existing_posts()
    available = []
    stale = []  # (frescura, tema, ruta) del post más antiguo que cubre cada tema
    for topic in TOPIC_POOL:
        tw = _keywords(topic)
        if topic in TEMAS_REVISADOS:
            matches = [p for p in posts if p[4] == topic]
        else:
            matches = [p for p in posts if p[4] == topic or _covers(tw, p[1])]
        if not matches:
            available.append(topic)
            continue
        oldest = min(matches, key=lambda p: p[2])
        if oldest[3]:
            stale.append((oldest[2], topic, oldest[0]))

    if available:
        return random.choice(available), None
    if client is not None:
        nuevo = _propose_topic(client, posts)
        if nuevo:
            print(f"Tema propuesto por el modelo: {nuevo}")
            return nuevo, None
    if stale:
        stale.sort(key=lambda s: s[0])
        _, topic, path = stale[0]
        return topic, path
    return random.choice(TOPIC_POOL), None


# ─── Temas nuevos cuando el pool se agota ────────────────────────────────────

def _propose_topic(client: OpenAI, posts) -> str | None:
    """Pide al modelo temas que el sitio aún no cubre y devuelve el primero que no se
    empalma con ningún título publicado ni con el pool. None si no encuentra uno."""
    titulos = sorted({p[5] for p in posts})
    prompt = (
        "Eres editor de PLD.mx, un medio especializado en prevención de lavado de dinero (PLD) "
        "y la LFPIORPI en México. Estos son los títulos que ya publicamos:\n\n"
        + "\n".join(f"- {t}" for t in titulos)
        + "\n\nPropón 12 temas NUEVOS para artículos de búsqueda de cola larga: dudas prácticas y "
        "concretas que tiene el responsable de cumplimiento de una empresa que realiza actividades "
        "vulnerables (cómo hacer algo, qué hacer ante una situación, criterios para decidir). "
        "Reglas: que ninguno repita o reformule un título de la lista; nada de tendencias, "
        "rankings de software ni noticias; sin cifras ni fechas específicas en el tema; en español "
        "de México; máximo 110 caracteres cada uno. "
        'Responde solo JSON: {"temas": ["...", "..."]}'
    )
    try:
        r = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.9,
        )
        temas = json.loads(r.choices[0].message.content).get("temas", [])
    except Exception as exc:  # sin red / respuesta inválida → se cae al modo actualización
        print(f"No se pudieron proponer temas nuevos: {exc}")
        return None
    ocupados = [p[1] for p in posts] + [_keywords(t) for t in TOPIC_POOL]
    for tema in temas:
        tema = str(tema).strip().strip('"')
        tw = _keywords(tema)
        if len(tw) >= 3 and not any(_covers(tw, o) for o in ocupados):
            return tema
    return None


def pick_category(topic: str) -> str:
    """Infer category from topic."""
    topic_lower = topic.lower()
    if topic_lower.startswith(("mejor software", "mejor plataforma", "mejores sistemas", "mejores software", "top ", "comparativa", "ranking ", "las mejores")):
        return "tecnologia"
    if "lfpiorpi" in topic_lower or "aviso" in topic_lower or "umbral" in topic_lower or "artículo 17" in topic_lower or "artículo 18" in topic_lower or "art. 17" in topic_lower or "art. 18" in topic_lower:
        return "lfpiorpi"
    if any(w in topic_lower for w in ["inmobiliaria", "joyería", "notario", "blindaje", "empeño", "automotriz", "arte", "arrendadora", "factoraje", "sofipo", "construcción", "contable", "fiscal", "comercio exterior", "aduanal", "activos virtuales", "sorteo", "tarjeta", "traslado de valores", "donativos", "arrendamiento"]):
        return "actividades-vulnerables"
    if any(w in topic_lower for w in ["kyc", "kyb", "cumplimiento", "diligencia", "señales de alerta", "expediente", "identificación", "identificar", "matriz de riesgo", "evaluación basada", "requerimiento", "personas políticamente", "efectivo", "beneficiario", "capacitación", "manual", "auditoría", "oficial", "conservación", "programa", "evaluación", "monitoreo permanente", "operaciones inusuales", "24 horas"]):
        return "cumplimiento"
    if any(w in topic_lower for w in ["tecnología", "automatización", "inteligencia artificial", "regtech", "api", "digital", "monitoreo transaccional", "herramienta", "verificación", "compliance 360"]):
        return "tecnologia"
    if any(w in topic_lower for w in ["uif", "gafi", "tipología", "criptomoneda", "fintech", "regulación", "cooperación", "financiamiento", "visitas de verificación", "delitos", "pep", "entidades colegiadas"]):
        return "regulacion"
    return "noticias"


STRUCTURE = """
ESTRUCTURA OBLIGATORIA DEL CONTENIDO (cumple cada sección, no omitas ninguna):

1. **Introducción analítica (mínimo 300 palabras)**: Contexto de mercado con cifras específicas. Si es un
   tema regulatorio, explica qué cambió y cuándo (fecha exacta del DOF). Si es un tema sectorial, da
   cifras del tamaño del sector en México.

2. **Marco legal detallado (mínimo 400 palabras)**: Cita artículos, fracciones y párrafos exactos de la
   LFPIORPI. Explica cómo aplica a la pregunta específica del tema. Incluye umbrales en UMA y su
   equivalente en pesos mexicanos aproximado para 2026.

3. **Análisis práctico (mínimo 500 palabras)**: Cómo se implementa en la práctica. Ejemplos concretos
   con cifras (no "una empresa hizo X", sino "una inmobiliaria que vende 12 unidades por $2.8M MXN
   mensuales tendría que presentar Y avisos por mes"). Procedimientos paso a paso.

4. **Riesgos y consecuencias (mínimo 300 palabras)**: Sanciones específicas aplicables con montos
   calculados en UMA. Casos documentados si los conoces. Implicaciones operativas del incumplimiento.

5. **Mejores prácticas (mínimo 400 palabras)**: Qué están haciendo los sujetos obligados avanzados.
   Procesos, controles, documentación. Usa bullet points y subsecciones con H3.

6. **Tabla comparativa o de datos (Markdown)**: Incluye AL MENOS UNA tabla relevante al tema
   (ej. umbrales por actividad vulnerable, plazos de reporte, comparación de obligaciones antes/después
   de la reforma, etc.)

7. **Conclusión estratégica (200-300 palabras)**: No un resumen pasivo — una recomendación accionable
   con base en lo expuesto.

8. **FAQ OBLIGATORIO — 5 preguntas específicas del tema** al final del artículo, cada una con
   respuesta de 80-120 palabras. Las preguntas deben ser las que un profesional se haría realmente
   (no genéricas tipo "¿qué es la LFPIORPI?"). Ejemplo para EBR: "¿Debo actualizar mi matriz de riesgo
   cada vez que incorporo un producto nuevo?" "¿La EBR documentada sustituye al Manual de Políticas
   Internas o son documentos separados?"

LONGITUD MÍNIMA TOTAL: {min_words} palabras. Artículos más cortos serán considerados incompletos.

PROHIBIDO:
- Frases promocionales vacías ("Artu es innovador", "la mejor solución del mercado")
- Afirmaciones sin cifras cuando se puede poner una cifra
- Ejemplos inventados presentados como casos reales (si inventas un ejemplo, deja claro que es ilustrativo)
- Nombrar proveedores de software o servicios de PLD distintos de Artu, o atribuir a una empresa real
  clientes, precios o limitaciones
- Rankings, tops o comparativas de software (se concentran en /top-software-pld/)
- Resúmenes que repiten lo que ya dijiste — solo conclusiones nuevas
"""

SYSTEM_PROMPT = """Eres un analista senior especializado en Prevención de Lavado de Dinero (PLD) en
México, con más de 15 años de experiencia. Escribes para PLD.mx, una publicación de referencia para
oficiales de cumplimiento, abogados regulatorios, y directivos de empresas sujetas a la LFPIORPI.
El estándar editorial es comparable al de The Banker, Finextra, PYMNTS, ACAMS Today y la revista
El Contador Público. Tus lectores son profesionales informados — NO escribas para principiantes.

ESTÁNDAR PERIODÍSTICO (no negociable):
- Cada afirmación cuantitativa debe tener un número específico (no "muchas empresas", sino "más de 8,500
  sujetos obligados registrados ante el SAT según el último padrón público")
- Cita artículos, fracciones y párrafos EXACTOS de la LFPIORPI, no generalidades
- Menciona casos reales cuando sea posible (ej. operativos de la UIF, sanciones impuestas, reformas recientes)
- Nombra instituciones y autoridades con sus nombres reales. NO nombres proveedores de software o
  servicios de PLD distintos de Artu, y nunca atribuyas a una empresa real clientes, precios o
  limitaciones
- Usa la terminología técnica correcta: "sujeto obligado", "aviso de actividad vulnerable",
  "beneficiario controlador", "debida diligencia del cliente (DDC)", "aviso de 24 horas",
  "matriz de riesgo", "ponderación de factores", etc.
- Evita tópicos y lugares comunes. Si vas a decir algo obvio, no lo digas.
- No uses lenguaje promocional ni adjetivos vacíos ("innovador", "de vanguardia", "líder del mercado")
  a menos que puedas respaldarlo con datos

CONTEXTO LEGAL CLAVE (LFPIORPI reforma DOF 16-07-2025):
- La LFPIORPI fue publicada el 17 de octubre de 2012, última reforma sustantiva DOF 16-07-2025
- El Reglamento de la LFPIORPI fue reformado el 27 de marzo de 2026 (primera reforma desde 2013)
- Los umbrales ahora se expresan en veces el valor diario de la UMA (antes salario mínimo general)
  - UMA 2026: $117.31 MXN diarios (vigente desde el 1 de febrero de 2026)
- Art. 17 tiene 17 fracciones de actividades vulnerables (I a XVI y V Bis); la XII (fe pública) tiene apartados A a D.
  No digas «16 actividades vulnerables»: esa cifra es anterior a la reforma de 2025
- Art. 18 tiene 12 fracciones (I a XI y IV Bis); IV Bis es el padrón. Las fracciones VII a XI entran en vigor
  según las Reglas de Carácter General (Acuerdo 115/2026, DOF 07-08-2026, en vigor el 30-nov-2026): EBR y manual
  01-03-2027; mecanismos automatizados 01-06-2027; capacitación desde 2027; primera auditoría en 2028
- Nuevas obligaciones del Art. 18 tras reforma 2025:
  * Fracción VII: Evaluación Basada en Riesgos (EBR) documentada
  * Fracción VIII: Manual de Políticas Internas PLD/FT
  * Fracción IX: Capacitación anual al personal
  * Fracción X: Mecanismos automatizados de monitoreo
  * Fracción XI: Auditoría PLD (interna o externa)
- Beneficiario Controlador: definición ampliada en fracción III del Art. 3 — incluye "beneficiario final"
  y "propietario real". Control efectivo directo o indirecto del 25% del capital o votos.
- Nueva fracción V Bis Art. 17: Desarrollo Inmobiliario (recepción de recursos para construcción)
- Fracción XVI Art. 17: activos virtuales, ahora incluye operaciones con ciudadanos mexicanos
  desde cualquier jurisdicción (alineado con FATF Recommendation 15)
- PEP (Persona Políticamente Expuesta) definida en fracción IX Bis del Art. 3
- Representante Encargada de Cumplimiento: fracción XII Bis del Art. 3
- Conservación de documentos: al menos 10 años desde la fecha de la actividad vulnerable, física o electrónica (Art. 18 fracción IV)
- Aviso de 24 horas por sospecha o indicios (Art. 18 fracción VI, párrafo segundo; art. 7 Bis del Reglamento).
  «Operación inusual», «interna preocupante» y «relevante» son términos del sector financiero (disposiciones del
  art. 115 de la Ley de Instituciones de Crédito), NO de la LFPIORPI: no los uses para actividades vulnerables
- Capítulo IV Bis (Arts. 33 Bis, Ter, Quáter): régimen del Beneficiario Controlador
- Sanciones Art. 54: multas de 200 a 65,000 UMA ($22,628 a $7,354,100 MXN aprox.) o 10-100% del valor
  de la operación
- Delitos Art. 62: prisión de 2 a 8 años por declarar falsamente; Art. 63: 4 a 10 años por usar
  recursos de procedencia ilícita

ACTORES REALES DEL ECOSISTEMA PLD MÉXICO (usa estos nombres cuando sea relevante):
- Autoridades: UIF (Unidad de Inteligencia Financiera — dependiente de SHCP), SAT (coordina la supervisión
  de actividades vulnerables a través de la AGACE), CNBV, Condusef, FGR
- Titular actual de UIF: Omar Reyes Colmenares (2024-presente)
- Organismos internacionales: GAFI (FATF), GAFILAT, Grupo Egmont
- Asociaciones profesionales: ACAMS México, Asociación Mexicana de Oficiales de Cumplimiento (AMOC),
  Asociación de Bancos de México (ABM), Asociación Mexicana de Instituciones de Seguros (AMIS)
- Colegios profesionales: Colegio Nacional del Notariado Mexicano, Colegio Nacional de Correduría Pública
- Medios especializados: El Financiero, Expansión, Forbes México, El Economista, Reforma

DATOS Y CIFRAS ÚTILES (usa cuando sea relevante):
- México está en la quinta ronda de evaluación mutua del GAFI (visita in situ en marzo de 2026); no cites fechas de publicación del informe que no puedas respaldar
- UIF ha inmovilizado ~5,000 MDP en la actual administración (2024-2026)
- FBI Internet Crime Report 2025: México #2 destino global de dinero de ciberdelitos (1,782 operaciones)
- SCJN avaló en abril 2026 (Acción 58/2022, votación 6-3) el bloqueo de cuentas por UIF sin orden judicial
- Crecimiento del lavado con criptomonedas en México: +55.8% en 2025 (SILIKN)

REGLAS DE REDACCIÓN:
- Escribe en español de México profesional, con terminología jurídica precisa pero claro
- Estructura con H2 (##) para secciones principales y H3 (###) para subsecciones
- Extensión: 2000-3000 palabras mínimo para artículos generales; 2800-3500 para rankings de software
- Usa tablas Markdown cuando compares opciones o datos cuantitativos, PERO acompáñalas siempre
  de un párrafo descriptivo previo que resuma la misma información en prosa (los oyentes del podcast
  no ven la tabla)
- Incluye ejemplos prácticos concretos (ej. "una notaría que autoriza una compraventa por 2.5 millones
  de pesos debe presentar aviso dentro de los primeros 17 días del mes siguiente")
- NO uses frases promocionales vacías. Cada oración debe aportar información.
- Optimiza para featured snippets con definiciones precisas al inicio de cada sección
- FAQ final con 4-5 preguntas ESPECÍFICAS del tema (no genéricas)
- Incluye fuentes y referencias cuando cites datos: "según el padrón público del SAT",
  "conforme al Art. 17 fracción XII de la LFPIORPI", "reportado por El Financiero el 7 de abril de 2026"
- NO agregues cajas de CTA ni botones: el sitio pone su propio cierre al final del artículo
- NO pongas un título H1 (#) en el contenido: el título va aparte. Empieza con un párrafo

ESCRITURA APTA PARA AUDIO (los artículos se convierten en episodios de podcast con TTS):
- Cada artículo será leído en voz alta por una voz sintética para nuestro podcast en Spotify.
  Por eso debe funcionar tanto leído como escuchado.
- Expande las siglas la PRIMERA vez que las mencionas dentro de la prosa, de forma natural:
  "la Ley Federal para la Prevención e Identificación de Operaciones con Recursos de Procedencia
  Ilícita, conocida como LFPIORPI" — después puedes usar la sigla libremente.
- Lo mismo con KYC, KYB, EBR, UIF, SAT, SHCP, GAFI, UMA, PEP, VASP, DOF, AML.
- NUNCA hagas referencias visuales como "como se muestra en la tabla siguiente", "ver gráfica",
  "en la imagen anterior", "más abajo en este artículo". Usa frases neutras: "como se detalla
  a continuación", "como veremos en seguida", "según los datos que se presentan".
- Escribe los números grandes con palabras o en formato hablable. "8,025 UMA" sí, pero los montos
  largos en pesos prefiere expandirlos: "ocho mil veinticinco veces la UMA, aproximadamente
  novecientos mil pesos" en lugar de "$908,098.50 MXN".
- Las listas con bullets deben tener un párrafo introductorio que las resuma en prosa, para que
  el oyente entienda el contexto antes de los bullets. Las listas suenan abruptas si llegan sin
  introducción.
- Usa transiciones entre secciones que funcionen en audio: "Pasemos ahora a...", "Una vez entendido
  esto, vale la pena preguntarse...", "Otro punto crítico es...".
- Evita signos especiales que el TTS pronuncia raro: %, &, # como símbolo (úsalo solo como heading),
  caracteres extranjeros sin contexto. Si necesitas el símbolo % di "por ciento".
- Los títulos H2/H3 deben ser frases informativas, no slogans. "Obligaciones del Beneficiario
  Controlador bajo el Artículo 33 Bis" — no "Lo que TODO sujeto obligado debe saber".
- Cuando cites un artículo de ley, di "Artículo dieciocho fracción séptima" o "Artículo 18,
  fracción VII" — el TTS lee ambos formatos bien, pero el segundo es más limpio."""


# ─── Datos de Artu y ligas a artu.ai ──────────────────────────────────────────

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import artu_links  # noqa: E402

ARTU = yaml.safe_load((RAIZ / "_data" / "artu.yml").read_text(encoding="utf-8"))
TOP_POSTS = RAIZ / "_data" / "top_posts.yml"


def _artu_contexto() -> str:
    funciones = "\n".join(f"- {f['nombre']}: {f['detalle']}" for f in ARTU["funciones"])
    return (f"Información sobre {ARTU['nombre']} ({ARTU['url']}). Úsala para contextualizar, no para promocionar:\n"
            f"{ARTU['descripcion']}\n{funciones}\n"
            f"- Implementación: {ARTU['implementacion']} ({ARTU['implementacion_detalle']}).\n"
            f"- Trabajo mensual: {ARTU['tiempo_mensual']}.\n"
            "No atribuyas a Artu nada que no esté en esta lista: ni cifras de eficiencia, ni porcentajes de "
            "automatización, ni precios, ni clientes.")


def _instruccion_ligas(tema: dict) -> str:
    textos = "; ".join(f"«{t}»" for t in tema["textos"])
    return f"""
LIGAS A ARTU.AI (obligatorio): incluye 1 o 2 ligas en Markdown, dentro de párrafos de desarrollo
(no en títulos, no en la introducción, no en la conclusión ni en el FAQ), hacia esta página:
{tema['url']}
El texto de la liga debe describir lo que el lector encontrará y encajar en la oración. Inspírate en:
{textos}. Varía el texto: no uses «software PLD», «haz clic aquí» ni «Artu» como texto de la liga.
Escribe la URL tal cual, sin parámetros."""


def _post_proceso(contenido: str, tema: dict, slug: str) -> str:
    """Quita el H1, agrega UTM a las ligas de artu.ai y asegura al menos una liga en contexto."""
    lineas = contenido.strip("\n").split("\n")
    while lineas and not lineas[0].strip():
        lineas.pop(0)
    if lineas and lineas[0].startswith("# "):
        lineas.pop(0)
    contenido = "\n".join("#" + l if l.startswith("# ") else l for l in lineas).strip("\n")

    def utm(m):
        url = m.group(2)
        if "utm_source=" in url:
            return m.group(0)
        return f"{m.group(1)}({artu_links.url_con_utm(url, slug)})"
    contenido = re.sub(r"(\[[^\]]+\])\((https://artu\.ai[^)\s]*)\)", utm, contenido)
    if tema["url"] not in contenido:  # la página del tema siempre va ligada (máximo 3 ligas a artu.ai)
        contenido, _ = artu_links.enlazar(contenido, tema, slug, max_ligas=3)
    return contenido


def generate_article(client: OpenAI, topic: str, category: str, mention_artu: bool, tema: dict):
    """Genera un artículo nuevo con OpenAI."""
    today = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    artu_instruction = ""
    if mention_artu:
        artu_instruction = ("IMPORTANTE: menciona a Artu de forma orgánica solo donde aporte valor real al lector "
                            "(no al inicio, no de manera forzada), al discutir cómo resolver en la práctica el "
                            "problema del artículo.\n" + _artu_contexto())
    min_words = "2200"
    structure_requirements = STRUCTURE.replace("{min_words}", min_words)
    user_prompt = f"""Escribe un artículo completo sobre el siguiente tema de PLD en México:

TEMA: {topic}
CATEGORÍA: {CATEGORY_DISPLAY.get(category, category)}
FECHA: {today}

{structure_requirements}
{_instruccion_ligas(tema)}

{artu_instruction}

Responde EXCLUSIVAMENTE con un JSON válido con esta estructura (sin markdown code blocks):
{{
  "title": "Título SEO (máximo 56 caracteres, con la búsqueda principal al inicio)",
  "description": "Meta description SEO (140-155 caracteres, con el beneficio concreto)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "content": "Contenido completo del artículo en Markdown, sin título H1 (mínimo {min_words} palabras)"
}}"""
    min_words_int = int(min_words)

    def call_openai(extra_instruction: str = ""):
        return client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt + extra_instruction}],
            temperature=0.75,
            max_tokens=12000,
            response_format={"type": "json_object"},
        )

    article = json.loads(call_openai().choices[0].message.content)
    word_count = len(article.get("content", "").split())
    print(f"Word count (initial): {word_count}")
    if word_count < min_words_int * 0.85:
        print(f"Article too short ({word_count} < {min_words_int}). Retrying with explicit extension request.")
        retry = (f"\n\nCRÍTICO: El artículo debe tener mínimo {min_words_int} palabras. Expande CADA sección con más "
                 "profundidad, ejemplos concretos y cifras específicas. Incluye todas las secciones obligatorias.\n")
        article = json.loads(call_openai(retry).choices[0].message.content)
        print(f"Word count (retry): {len(article.get('content', '').split())}")
    return article


def refresh_article(client: OpenAI, path: Path, tema: dict) -> str | None:
    """Actualiza un post existente en su misma URL: mejora el cuerpo actual en lugar de reescribirlo
    desde cero (conserva estructura, datos correctos y ligas). Devuelve el cuerpo nuevo o None."""
    original = path.read_text(encoding="utf-8")
    _, front, body = original.split("---", 2)
    title = re.search(r'^title:\s*"?(.*?)"?\s*$', front, re.M).group(1)
    today = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    prompt = f"""Actualiza este artículo ya publicado en PLD.mx. Es de los que más impresiones tienen en Google,
así que el objetivo es que responda mejor la búsqueda, no cambiarle el tema.

TÍTULO (no lo cambies): {title}
FECHA DE HOY: {today}

Reglas:
- Conserva el tema, la estructura de secciones y todo lo que ya es correcto. Corrige lo desactualizado
  (UMA 2026, reformas, fechas) y elimina lo que no puedas respaldar.
- Mejora lo que falte: respuesta directa en el primer párrafo, definiciones precisas al inicio de cada
  sección, ejemplos con cifras (marcados como ilustrativos), al menos una tabla, y un FAQ de 5 preguntas
  específicas si no lo tiene.
- Conserva todas las ligas existentes, en especial las de artu.ai, con su mismo texto.
- No agregues título H1, cajas de CTA ni nombres de proveedores de software distintos de Artu.
- Longitud: igual o mayor que la actual.
{_instruccion_ligas(tema)}

Responde EXCLUSIVAMENTE con un JSON válido: {{"content": "artículo completo en Markdown", "cambios": ["resumen de cada cambio"]}}

ARTÍCULO ACTUAL:
{body.strip()}"""
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=14000,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    nuevo = data.get("content", "")
    if len(nuevo.split()) < len(body.split()) * 0.9:
        print(f"Actualización descartada: quedó más corta ({len(nuevo.split())} vs {len(body.split())} palabras)")
        return None
    for c in data.get("cambios", [])[:10]:
        print(f"  cambio: {c}")
    return nuevo


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


def _modo_del_dia() -> str:
    """Lunes, miércoles y viernes: artículo nuevo. Martes y jueves: actualización de uno de los posts con
    más impresiones. Fines de semana: nada. MODO=nuevo|actualizar|nada lo fuerza (ejecución manual)."""
    forzado = os.environ.get("MODO", "").strip().lower()
    if forzado in ("nuevo", "actualizar", "nada"):
        return forzado
    dia = datetime.now(ZoneInfo("America/Mexico_City")).weekday()
    return {0: "nuevo", 1: "actualizar", 2: "nuevo", 3: "actualizar", 4: "nuevo"}.get(dia, "nada")


def _frescura(path: Path) -> str:
    head = path.read_text(encoding="utf-8")[:3000]
    mod = re.search(r"^last_modified_at:\s*(\d{4}-\d{2}-\d{2})", head, re.M)
    return max(path.name[:10], mod.group(1) if mod else "")


def pick_refresh() -> Path | None:
    """El post de _data/top_posts.yml (los de más impresiones) que lleva más tiempo sin actualizarse,
    siempre que no se haya tocado en los últimos 30 días y no tenga `refresh: false`."""
    if not TOP_POSTS.exists():
        return None
    lista = yaml.safe_load(TOP_POSTS.read_text(encoding="utf-8")).get("posts", [])
    limite = (datetime.now(ZoneInfo("America/Mexico_City")) - timedelta(days=30)).strftime("%Y-%m-%d")
    candidatos = []
    for item in lista:
        f = RAIZ / item["archivo"]
        if not f.exists():
            continue
        head = f.read_text(encoding="utf-8")[:3000]
        if re.search(r"^refresh:\s*false", head, re.M):
            continue
        fresco = _frescura(f)
        if fresco <= limite:
            candidatos.append((fresco, f))
    return min(candidatos)[1] if candidatos else None


def _tema_de_post(front: str) -> dict:
    datos = artu_links.cargar()
    clave = re.search(r"^artu_tema:\s*(\S+)", front, re.M)
    if clave and artu_links.por_clave(clave.group(1), datos):
        return artu_links.por_clave(clave.group(1), datos)
    title = re.search(r'^title:\s*"?(.*?)"?\s*$', front, re.M).group(1)
    return artu_links.tema_para(title, datos)


def actualizar(client: OpenAI, path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    _, front, _body = original.split("---", 2)
    tema = _tema_de_post(front)
    print(f"Modo actualización: {path.name} (tema artu.ai: {tema['clave']})")
    nuevo = refresh_article(client, path, tema)
    if not nuevo:
        return False
    nuevo = _post_proceso(nuevo, tema, path.stem[11:])
    today = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    front = re.sub(r"^last_modified_at:.*\n?", "", front, flags=re.M).rstrip("\n")
    if not re.search(r"^artu_tema:", front, re.M):
        front += f"\nartu_tema: {tema['clave']}"
    front += f"\nlast_modified_at: {today}\n"
    path.write_text(f"---{front}---\n\n{nuevo}\n", encoding="utf-8")
    print(f"Post actualizado: {path}")
    return True


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable is required")
        sys.exit(1)
    client = OpenAI(api_key=api_key)
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    modo = _modo_del_dia()
    print(f"Modo del día: {modo}")
    if modo == "nada":
        print("Hoy no toca publicar (fin de semana).")
        return
    if modo == "actualizar":
        objetivo = pick_refresh()
        if objetivo and actualizar(client, objetivo):
            print("Done!")
        else:
            print("No hubo actualización hoy.")
        return

    topic, refresh_path = pick_topic(client)
    if refresh_path:
        # el pool y las propuestas se agotaron: en lugar de duplicar, se mejora un post existente
        actualizar(client, refresh_path)
        return

    category = pick_category(topic)
    mention_artu = should_mention_artu(topic)
    tema = artu_links.tema_para(topic, artu_links.cargar())
    print(f"Topic: {topic}")
    print(f"Category: {category}")
    print(f"Mention Artu: {mention_artu}")
    print(f"Tema artu.ai: {tema['clave']} -> {tema['url']}")

    article = generate_article(client, topic, category, mention_artu, tema)
    print(f"Title: {article['title']}")
    today = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    slug = slugify(article["title"])
    contenido = _post_proceso(article["content"], tema, slug)

    image_filename = f"{today}-{slug}.svg"
    image_path = IMAGES_DIR / image_filename
    image_path.write_text(generate_og_image_svg(article["title"], category), encoding="utf-8")
    print(f"Image: {image_path}")

    tags_yaml = "\n".join(f"  - {tag}" for tag in article.get("tags", []))
    post_path = POSTS_DIR / f"{today}-{slug}.md"
    titulo = article["title"].replace('"', "'")
    descripcion = article["description"].replace('"', "'")
    frontmatter = f"""---
layout: post
title: "{titulo}"
description: "{descripcion}"
date: {today}
categories:
  - {category}
tags:
{tags_yaml}
image: /assets/images/posts/{image_filename}
author: Equipo PLD.mx
topic: "{topic.replace('"', '')}"
artu_tema: {tema['clave']}
---

{contenido}
"""
    post_path.write_text(frontmatter, encoding="utf-8")
    ligas = len(re.findall(r"\]\(https://artu\.ai", contenido))
    print(f"Post: {post_path} ({ligas} liga(s) a artu.ai)")
    print("Done!")


if __name__ == "__main__":
    main()
