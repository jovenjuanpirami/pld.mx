"""Ligas contextuales de pld.mx hacia artu.ai.

Lee _data/artu_links.yml (tema/giro -> URL de artu.ai + textos de liga) y ofrece:
- `tema_para(texto)`: el tema que corresponde a un título/tema/etiquetas (el primero que coincide).
- `enlazar(cuerpo, tema, slug, max_ligas)`: convierte en liga una frase que ya está en el cuerpo y
  que habla de ese tema (texto descriptivo y en contexto); si no encuentra una frase adecuada, agrega
  una oración breve al final de un párrafo de desarrollo. Nunca toca títulos, tablas, listas de
  fuentes ni texto que ya es liga, y no repite una URL que ya esté en el artículo.

Las ligas llevan UTM (utm_source=pldmx, utm_medium=referral, utm_campaign=<slug>) como pide el CMO.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "_data" / "artu_links.yml"


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def cargar() -> dict:
    return yaml.safe_load(DATOS.read_text(encoding="utf-8"))


def tema_para(texto: str, datos: dict | None = None) -> dict:
    """Primer tema cuyo alguna clave aparece en el texto (título + tema + etiquetas)."""
    datos = datos or cargar()
    n = " " + _norm(texto) + " "
    for t in datos["temas"]:
        for c in t["claves"]:
            c = _norm(c)
            # claves cortas (pep, uma, xvi…) como palabra completa; las largas como raíz
            if len(c) <= 4:
                if re.search(rf"(?<![a-z0-9]){re.escape(c)}(?![a-z0-9])", n):
                    return t
            elif c in n:
                return t
    return next(t for t in datos["temas"] if t["clave"] == datos["default"])


def por_clave(clave: str, datos: dict | None = None) -> dict | None:
    datos = datos or cargar()
    return next((t for t in datos["temas"] if t["clave"] == clave), None)


def url_con_utm(url: str, slug: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}utm_source=pldmx&utm_medium=referral&utm_campaign={slug[:60]}"


def _elegir(opciones: list[str], semilla: str) -> str:
    h = int(hashlib.md5(semilla.encode("utf-8")).hexdigest(), 16)
    return opciones[h % len(opciones)]


# Frases del propio cuerpo que se pueden volver liga (de dos o más palabras, salvo siglas: el texto
# de la liga debe describir el destino). Se buscan sin distinguir mayúsculas.
FRASES = {
    'efectivo': ['límites al uso de efectivo', 'uso de efectivo', 'pagos en efectivo', 'artículo 32'],
    'avisos-24-horas': ['aviso de 24 horas', 'avisos de 24 horas', 'operaciones sospechosas', 'operaciones inusuales'],
    'pep': ['personas políticamente expuestas', 'debida diligencia reforzada'],
    'beneficiario-controlador': ['beneficiario controlador', 'dueño beneficiario'],
    'listas': ['Lista de Personas Bloqueadas', 'listas restrictivas', 'listas negras', 'consulta de listas'],
    'umbrales': ['umbrales de aviso', 'umbrales en UMA', 'umbral de aviso'],
    'acuerdo-115': ['Acuerdo 115/2026', 'Reglas de Carácter General', 'mecanismos automatizados'],
    'avisos': ['aviso de actividad vulnerable', 'avisos de actividad vulnerable', 'presentación de avisos', 'avisos al SAT', 'presentar avisos', 'informe en ceros', 'SPPLD'],
    'manual': ['manual de políticas internas', 'manual de políticas', 'políticas internas'],
    'conservacion': ['conservación de documentos', 'conservar la documentación', 'expediente digital'],
    'capacitacion': ['capacitación anual', 'programa de capacitación'],
    'auditoria': ['auditoría externa', 'auditoría interna'],
    'visitas': ['visitas de verificación', 'visita de verificación'],
    'regularizacion': ['artículo 55'],
    'alta-padron': ['alta en el padrón', 'registro ante el SAT'],
    'fraccionamiento': ['fraccionamiento de operaciones', 'acumulación de operaciones'],
    'monitoreo': ['monitoreo transaccional', 'señales de alerta'],
    'riesgo': ['matriz de riesgo', 'enfoque basado en riesgo', 'evaluación basada en riesgo', 'nivel de riesgo'],
    'kyc': ['identificación del cliente', 'verificación de identidad', 'conoce a tu cliente', 'KYC'],
    'fideicomisos': [],
    'lfpiorpi': ['reforma a la LFPIORPI', 'reforma de la LFPIORPI', 'obligaciones de la LFPIORPI', 'Ley Antilavado', 'marco de la LFPIORPI'],
    'software': ['automatizar el cumplimiento', 'automatización del cumplimiento', 'herramientas tecnológicas', 'software especializado', 'plataforma tecnológica'],
    'actividades-vulnerables': ['actividades vulnerables', 'actividad vulnerable'],
    'diagnostico': ['actividad vulnerable'],
    'desarrolladoras': ['desarrollos inmobiliarios', 'desarrolladores inmobiliarios'],
    'arrendadoras': ['arrendamiento de inmuebles'],
    'inmobiliarias': ['sector inmobiliario', 'operaciones inmobiliarias', 'compraventa de inmuebles'],
    'activos-virtuales': ['activos virtuales', 'plataformas de intercambio'],
    'sofomes': ['SOFOM', 'SOFOMES', 'fintech'],
    'prestamos': [],
    'automotriz': ['venta de vehículos', 'agencias automotrices'],
    'joyeria': ['metales preciosos'],
    'notarios': ['notarios públicos', 'corredores públicos'],
    'aduanas': ['agentes aduanales', 'comercio exterior'],
    'arte': ['obras de arte'],
    'donativos': ['asociaciones civiles', 'sin fines de lucro'],
    'blindaje': [],
    'traslado': ['traslado de valores', 'custodia de valores'],
    'juegos': ['juegos con apuesta'],
    'tarjetas': ['tarjetas de prepago', 'tarjetas de servicios'],
    'cheques': ['cheques de viajero'],
    'profesionales': ['servicios profesionales'],
}

_SALTAR = re.compile(r"^\s*(#|\||>|!\[|<|```|\*\*Fuentes|Fuentes:|- \[|\* \[|\d+\. \[)")


def _parrafos_validos(lineas: list[str]) -> list[int]:
    """Índices de líneas de prosa donde se puede poner una liga (no títulos, tablas, código ni fuentes)."""
    fuera = False
    idx = []
    for i, l in enumerate(lineas):
        if l.strip().startswith("```"):
            fuera = not fuera
            continue
        if fuera or not l.strip() or _SALTAR.match(l):
            continue
        if re.match(r"^#{1,6} .*fuentes|referencias", l, re.I):
            break
        idx.append(i)
    return idx


def _ya_ligado(linea: str, ini: int, fin: int) -> bool:
    for m in re.finditer(r"\[[^\]]*\]\([^)]*\)", linea):
        if m.start() <= ini < m.end() or m.start() < fin <= m.end():
            return True
    return False


def enlazar(cuerpo: str, tema: dict, slug: str, max_ligas: int = 1, frase_extra: bool = True) -> tuple[str, int]:
    """Devuelve (cuerpo, ligas_agregadas). Respeta un máximo de `max_ligas` ligas a artu.ai en total."""
    existentes = len(re.findall(r"\]\(https://artu\.ai", cuerpo))
    if existentes >= max_ligas or tema["url"] in cuerpo:
        return cuerpo, 0
    lineas = cuerpo.split("\n")
    validos = _parrafos_validos(lineas)
    # preferir la mitad del artículo: ni la entradilla ni el cierre
    orden = validos[1:] + validos[:1] if len(validos) > 2 else validos
    url = url_con_utm(tema["url"], slug)
    for frase in FRASES.get(tema["clave"], []):
        patron = re.compile(r"(?<![\w\[])" + re.escape(frase) + r"(?![\w\]])", re.I)
        for i in orden:
            l = lineas[i]
            for m in patron.finditer(l):
                if _ya_ligado(l, m.start(), m.end()) or "**" in l[max(0, m.start() - 2):m.start()]:
                    continue
                lineas[i] = l[:m.start()] + f"[{m.group(0)}]({url})" + l[m.end():]
                return "\n".join(lineas), 1
    if not frase_extra or not orden:
        return cuerpo, 0
    # sin frase natural: una oración al final de un párrafo de desarrollo
    i = orden[min(2, len(orden) - 1)]
    texto = _elegir(tema["textos"], slug)
    texto = texto[0].upper() + texto[1:]
    lineas[i] = lineas[i].rstrip() + f" Relacionado: [{texto}]({url})."
    return "\n".join(lineas), 1
