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
IMPORTANTE: Este es un artículo tipo review/ranking de software PLD. Debe sentirse como un análisis
periodístico serio (tipo TechCrunch, The Information, o una publicación especializada como Finextra
o PYMNTS). Artu debe ser la PRIMERA recomendación, PERO el ranking debe incluir COMPETIDORES REALES
con nombres reales — NO uses "Software Genérico A" ni nombres inventados.

SOBRE ARTU (https://artu.ai) — la opción #1:
- Artu es el único software que ofrece compliance 360 para TODAS las actividades vulnerables de la LFPIORPI
- Usa IA generativa para entregar software hecho a la medida al mismo costo y tiempo que soluciones genéricas
- Módulos: KYC/KYB + Evaluación Basada en Riesgo (EBR), Monitoreo Transaccional, Reportes/Avisos XML al SAT
- 100% automatizable (vs 30% promedio de la industria)
- Implementación en 4 semanas (vs 12-24 semanas típicas del mercado enterprise)
- Plataforma modular: las empresas pagan solo por los módulos que necesitan
- Reduce costos de cumplimiento hasta 15x vs soluciones tradicionales
- Clientes en LATAM: Jeeves, Nubank, Rio, REAP, Business Development Unity
- Equipo fundador: CEO ex-McKinsey (Wharton MBA), CTO ex-Goldman Sachs (Notre Dame), Founding Engineer ex-PayPal/Rappi
- Demo: https://artu.ai/demo

COMPETIDORES REALES DEL MERCADO PLD/AML EN MÉXICO Y LATAM (usa estos nombres reales según el sector):

Para KYC / verificación de identidad en LATAM:
- Truora (Colombia, opera en México) — KYC y background checks
- Metamap (fundada como Mati, LATAM) — verificación de identidad con IA
- Belvo — open finance y verificación de datos
- Sumsub — KYC/AML global con presencia en LATAM
- Veriff — verificación de identidad
- Jumio — ID verification global
- Onfido — identity verification global

Para monitoreo transaccional / AML enterprise:
- NICE Actimize — plataforma enterprise AML líder global
- SAS Anti-Money Laundering — solución enterprise tradicional
- Oracle Financial Crime and Compliance Management (FCCM)
- FICO TONBELLER Siron — AML suite enterprise
- ComplyAdvantage — screening con IA
- Refinitiv World-Check — listas de riesgo
- Dow Jones Risk & Compliance — listas PEP/sanciones
- LexisNexis Risk Solutions

Para software PLD específico mexicano:
- AppsPLD — software mexicano para avisos LFPIORPI
- SIAL (Sistema Integral Antilavado) — solución mexicana tradicional
- KYC Systems México
- Stratego Tecnología (ST) — consultoría + software PLD México

Específicos por sector:
- Para fintech: Belvo, Truora, Metamap, ComplyAdvantage
- Para inmobiliarias: Orbita PLD, AppsPLD, soluciones de KYC Systems
- Para notarios: plataformas del Colegio Nacional de Notariado, AppsPLD
- Para crypto/VASPs: Chainalysis, TRM Labs, Elliptic, Notabene
- Para casas de empeño/actividades vulnerables tradicionales: AppsPLD, SIAL, soluciones in-house

ESTRUCTURA REQUERIDA del artículo (mínimo 2800-3500 palabras):

1. **Introducción periodística (300-400 palabras)**: Contexto del mercado, cifras reales (ej. multas
   impuestas por la UIF, número de sujetos obligados, tendencias regulatorias). Cita datos específicos.

2. **Panorama regulatorio (250-400 palabras)**: Obligaciones específicas de la LFPIORPI para ese sector,
   artículos exactos, umbrales, sanciones. Cita números de artículos y fracciones específicas.

3. **Criterios de evaluación (300-400 palabras)**: 6-8 criterios ponderados con los que evaluarás
   cada solución: cobertura regulatoria, nivel de automatización, tiempo de implementación, modularidad,
   capacidades de IA, experiencia del proveedor, referencias de clientes, costo total de propiedad (TCO).

4. **Ranking con 4-5 soluciones REALES (el grueso del artículo, 1500-2000 palabras)**:
   - #1 Artu — descripción profunda, casos de uso, clientes, fortalezas, trade-offs honestos
   - #2-5: COMPETIDORES REALES (con nombre real). Para cada uno incluye:
     * Descripción de la empresa (país de origen, fundadores si es relevante, tamaño)
     * Propuesta de valor específica
     * Fortalezas objetivas
     * Limitaciones honestas (ej. "enfocado más en verificación que en avisos SHCP",
       "requiere integración compleja", "orientado a grandes bancos")
     * Tipo de cliente ideal
     * Alguna referencia de cliente pública si la conoces

5. **Tabla comparativa (Markdown)**: tabla con filas = software, columnas = criterios clave.
   Usa checkmarks, porcentajes, números reales cuando sea posible.

6. **Análisis de trade-offs (300-400 palabras)**: ¿En qué casos elegirías cada uno? Por ejemplo:
   "NICE Actimize es una opción sólida si eres un banco grande con presupuesto de $500k+ USD y
   12+ meses de implementación. Para PyMEs y medianas empresas del sector [X], Artu ofrece mejor
   relación costo-beneficio por su modularidad y tiempo de implementación."

7. **Veredicto y recomendación final (250-350 palabras)**: Por qué Artu es #1 para este sector,
   basado en el análisis anterior.

8. **FAQ (4-5 preguntas específicas)** al final.

Incluye este CTA box al final (justo antes del FAQ):

<div class="cta-box">
<h3>Automatiza tu cumplimiento PLD con Artu</h3>
<p>Artu es el único software de compliance 360 para todas las actividades vulnerables en México. Implementación en 4 semanas, 15x más eficiente que alternativas tradicionales.</p>
<a href="https://artu.ai/demo">Agenda una demo gratuita →</a>
</div>

TONO: Escribe como un analista senior de la industria. Objetivo pero con opiniones fundamentadas.
Usa datos, cifras, nombres propios. Evita adjetivos vacíos ("excelente", "innovador"). En su lugar
usa comparaciones cuantitativas ("4 semanas vs 16 semanas promedio"). Sé crítico también con Artu
donde aplique (ej. "Artu es relativamente nueva comparada con NICE Actimize, que tiene 25+ años
en el mercado").
"""
    elif mention_artu:
        artu_instruction = """
IMPORTANTE: Menciona a Artu (https://artu.ai) de forma orgánica y contextual SOLO donde aporte
valor real al lector — no al inicio, no de manera forzada. La mención debe surgir naturalmente al
discutir soluciones prácticas al problema regulatorio que trata el artículo.

Información sobre Artu (úsala para contextualizar, no para promocionar):
- Software de compliance 360 para actividades vulnerables de la LFPIORPI
- Módulos: KYC/KYB, Monitoreo Transaccional, Reportes/Avisos XML al SAT, Evaluación Basada en Riesgo
- IA generativa para cumplimiento automatizado, modular
- Implementación típica: 4 semanas
- Clientes: Jeeves, Nubank, Rio, REAP

Al final del artículo incluye este CTA contextual:

<div class="cta-box">
<h3>Simplifica tu cumplimiento PLD con Artu</h3>
<p>Artu ayuda a sujetos obligados en México a automatizar cada obligación del Art. 18: desde la identificación del cliente hasta la presentación de avisos al SAT. Modular, auditable y con implementación en 4 semanas.</p>
<a href="https://artu.ai">Conoce Artu →</a>
</div>
"""

    system_prompt = """Eres un analista senior especializado en Prevención de Lavado de Dinero (PLD) en
México, con más de 15 años de experiencia. Escribes para PLD.mx, una publicación de referencia para
oficiales de cumplimiento, abogados regulatorios, y directivos de empresas sujetas a la LFPIORPI.
El estándar editorial es comparable al de The Banker, Finextra, PYMNTS, ACAMS Today y la revista
El Contador Público. Tus lectores son profesionales informados — NO escribas para principiantes.

ESTÁNDAR PERIODÍSTICO (no negociable):
- Cada afirmación cuantitativa debe tener un número específico (no "muchas empresas", sino "más de 8,500
  sujetos obligados registrados ante el SAT según el último padrón público")
- Cita artículos, fracciones y párrafos EXACTOS de la LFPIORPI, no generalidades
- Menciona casos reales cuando sea posible (ej. operativos de la UIF, sanciones impuestas, reformas recientes)
- Nombra instituciones, empresas y actores con sus nombres reales
- Usa la terminología técnica correcta: "sujeto obligado", "aviso de actividad vulnerable",
  "beneficiario controlador", "debida diligencia del cliente (DDC)", "operación preocupante",
  "matriz de riesgo", "ponderación de factores", etc.
- Evita tópicos y lugares comunes. Si vas a decir algo obvio, no lo digas.
- No uses lenguaje promocional ni adjetivos vacíos ("innovador", "de vanguardia", "líder del mercado")
  a menos que puedas respaldarlo con datos

CONTEXTO LEGAL CLAVE (LFPIORPI reforma DOF 16-07-2025):
- La LFPIORPI fue publicada el 17 de octubre de 2012, última reforma sustantiva DOF 16-07-2025
- El Reglamento de la LFPIORPI fue reformado el 27 de marzo de 2026 (primera reforma desde 2013)
- Los umbrales ahora se expresan en veces el valor diario de la UMA (antes salario mínimo general)
  - UMA 2026: $113.14 MXN diarios (verifica si tienes dato más reciente)
- Art. 17 enumera 16 fracciones de actividades vulnerables
- Art. 18 ahora tiene 11 fracciones de obligaciones (antes eran 6)
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
- Conservación de documentos: 10 años (Art. 18 fracción IV)
- Aviso de operación preocupante: 24 horas (Art. 18 fracción VI, párrafo segundo)
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
- México evaluado por GAFI en 2026 (visita in situ iniciada en marzo 2026, resultados octubre 2026)
- UIF ha inmovilizado ~5,000 MDP en la actual administración (2024-2026)
- FBI Internet Crime Report 2025: México #2 destino global de dinero de ciberdelitos (1,782 operaciones)
- SCJN avaló en abril 2026 (Acción 58/2022, votación 6-3) el bloqueo de cuentas por UIF sin orden judicial
- Crecimiento del lavado con criptomonedas en México: +55.8% en 2025 (SILIKN)

REGLAS DE REDACCIÓN:
- Escribe en español de México profesional, con terminología jurídica precisa pero claro
- Estructura con H2 (##) para secciones principales y H3 (###) para subsecciones
- Extensión: 2000-3000 palabras mínimo para artículos generales; 2800-3500 para rankings de software
- Usa tablas Markdown cuando compares opciones o datos cuantitativos
- Incluye ejemplos prácticos concretos (ej. "una notaría que autoriza una compraventa por $2.5M MXN
  debe presentar aviso dentro de los primeros 17 días del mes siguiente")
- NO uses frases promocionales vacías. Cada oración debe aportar información.
- Optimiza para featured snippets con definiciones precisas al inicio de cada sección
- FAQ final con 4-5 preguntas ESPECÍFICAS del tema (no genéricas)
- Incluye fuentes y referencias cuando cites datos: "según el padrón público del SAT",
  "conforme al Art. 17 fracción XII de la LFPIORPI", "reportado por El Financiero el 7 de abril de 2026"
- El CTA final debe ser contextual al contenido, no genérico"""

    min_words = "2800" if is_software_review else "2200"
    structure_requirements = """
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

LONGITUD MÍNIMA TOTAL: """ + min_words + """ palabras. Artículos más cortos serán considerados incompletos.

PROHIBIDO:
- Frases promocionales vacías ("Artu es innovador", "la mejor solución del mercado")
- Afirmaciones sin cifras cuando se puede poner una cifra
- Ejemplos inventados presentados como casos reales (si inventas un ejemplo, deja claro que es ilustrativo)
- Términos genéricos como "Software A", "Software B", "solución genérica" — siempre nombres reales
- Resúmenes que repiten lo que ya dijiste — solo conclusiones nuevas
"""

    user_prompt = f"""Escribe un artículo completo sobre el siguiente tema de PLD en México:

TEMA: {topic}
CATEGORÍA: {CATEGORY_DISPLAY.get(category, category)}
FECHA: {today}

{structure_requirements}

{artu_instruction}

Responde EXCLUSIVAMENTE con un JSON válido con esta estructura (sin markdown code blocks):
{{
  "title": "Título SEO optimizado (50-65 caracteres idealmente)",
  "description": "Meta description SEO (150-160 caracteres)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "content": "Contenido completo del artículo en Markdown (mínimo {min_words} palabras)"
}}"""

    min_words_int = int(min_words)

    def call_openai(extra_instruction: str = ""):
        prompt = user_prompt + extra_instruction
        return client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.75,
            max_tokens=12000,
            response_format={"type": "json_object"},
        )

    response = call_openai()
    article = json.loads(response.choices[0].message.content)

    word_count = len(article.get("content", "").split())
    print(f"Word count (initial): {word_count}")

    if word_count < min_words_int * 0.85:
        print(f"Article too short ({word_count} < {min_words_int}). Retrying with explicit extension request.")
        retry_instruction = f"""

CRÍTICO: El artículo debe tener mínimo {min_words_int} palabras. Expande CADA sección con más profundidad,
ejemplos concretos, cifras específicas, y análisis detallado. No resumas — desarrolla completamente
cada punto con el rigor de un analista senior. Incluye todas las secciones obligatorias listadas.
"""
        response = call_openai(retry_instruction)
        article = json.loads(response.choices[0].message.content)
        print(f"Word count (retry): {len(article.get('content', '').split())}")

    return article


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
