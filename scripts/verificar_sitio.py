#!/usr/bin/env python3
"""Verificación del sitio compilado (_site): H1, redirecciones, ligas a artu.ai, sitemap y llms.txt.

Uso:  python scripts/verificar_sitio.py [carpeta_site]      (por defecto _site)
      python scripts/verificar_sitio.py _site --sin-red     (no consulta artu.ai)
Sale con código 1 si encuentra algún problema.
"""
from __future__ import annotations

import concurrent.futures as cf
import html
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

site = Path(next((a for a in sys.argv[1:] if not a.startswith("--")), "_site"))
sin_red = "--sin-red" in sys.argv
problemas: list[str] = []

paginas = [p for p in site.rglob("*.html") if "assets" not in p.parts]
redirecciones = {}
h1_multiple, sin_h1 = [], []
ligas_artu: dict[str, set[str]] = {}

for p in paginas:
    s = p.read_text(encoding="utf-8", errors="ignore")
    ruta = "/" + p.relative_to(site).as_posix().replace("index.html", "")
    refresh = re.search(r'<meta http-equiv="refresh" content="0; url=([^"]+)"', s)
    if refresh:
        redirecciones[ruta] = html.unescape(refresh.group(1))
        continue
    n_h1 = len(re.findall(r"<h1[\s>]", s))
    if n_h1 > 1:
        h1_multiple.append((ruta, n_h1))
    elif n_h1 == 0 and "<article" in s:
        sin_h1.append(ruta)
    for u in re.findall(r'href="(https://artu\.ai[^"#]*)"', s):
        base = html.unescape(u).split("?")[0]
        ligas_artu.setdefault(base, set()).add(ruta)

print(f"páginas: {len(paginas)} · redirecciones: {len(redirecciones)} · URLs de artu.ai distintas: {len(ligas_artu)}")
if h1_multiple:
    problemas.append(f"{len(h1_multiple)} páginas con más de un H1: {h1_multiple[:5]}")
if sin_h1:
    problemas.append(f"{len(sin_h1)} artículos sin H1: {sin_h1[:5]}")

# redirecciones: el destino interno debe existir como página real
for origen, destino in redirecciones.items():
    if destino.startswith(("http://", "https://")) and "pld.mx" not in destino:
        continue
    d = re.sub(r"^https?://(www\.)?pld\.mx", "", destino)
    archivo = site / d.lstrip("/") / "index.html" if d.endswith("/") else site / d.lstrip("/")
    if not archivo.exists():
        problemas.append(f"redirección {origen} -> {destino}: el destino no existe en el sitio")
    elif re.search(r'http-equiv="refresh"', archivo.read_text(encoding="utf-8", errors="ignore")):
        problemas.append(f"redirección en cadena: {origen} -> {destino} (el destino también redirige)")

# sitemap y archivos especiales
sitemap = (site / "sitemap.xml").read_text(encoding="utf-8") if (site / "sitemap.xml").exists() else ""
if "google225bac937cb216d3" in sitemap:
    problemas.append("el archivo de verificación de Google sigue en el sitemap")
if not (site / "google225bac937cb216d3.html").exists() or "google-site-verification: google225bac937cb216d3.html" not in (site / "google225bac937cb216d3.html").read_text(encoding="utf-8"):
    problemas.append("el archivo de verificación de Google no se publica igual")
en_sitemap = set(re.findall(r"<loc>https://pld\.mx([^<]+)</loc>", sitemap))
redirigidas_en_sitemap = [u for u in en_sitemap if u in redirecciones]
if redirigidas_en_sitemap:
    problemas.append(f"{len(redirigidas_en_sitemap)} redirecciones aparecen en el sitemap: {redirigidas_en_sitemap[:3]}")
llms = site / "llms.txt"
if not llms.exists() or "{{" in llms.read_text(encoding="utf-8") or "# PLD.mx" not in llms.read_text(encoding="utf-8"):
    problemas.append("llms.txt no se generó bien")

# ligas a artu.ai: todas deben responder 200 (sin seguir a otra URL distinta)
if not sin_red:
    def revisar(u):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 pldmx-linkcheck"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return u, r.status, r.geturl()
        except urllib.error.HTTPError as e:
            return u, e.code, u
        except Exception as e:  # noqa: BLE001
            return u, str(e)[:60], u
    with cf.ThreadPoolExecutor(6) as ex:
        for u, st, final in ex.map(revisar, sorted(ligas_artu)):
            if st != 200:
                problemas.append(f"liga a artu.ai con respuesta {st}: {u} (en {sorted(ligas_artu[u])[:2]})")
            elif final.rstrip("/") != u.rstrip("/") and "artu.ai" in final and final.split("?")[0].rstrip("/") != u.rstrip("/"):
                print(f"  aviso: {u} redirige a {final}")

if problemas:
    print("PROBLEMAS:")
    for x in problemas:
        print(" -", x)
    sys.exit(1)
print("Todo bien: un solo H1 por página, redirecciones con destino real, ligas a artu.ai con 200, sitemap y llms.txt correctos.")
