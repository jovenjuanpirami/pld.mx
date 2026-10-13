/* Entrevista para el Manual de Cumplimiento PLD — corre completa en el navegador.
   Nada se envía a ningún servidor: las respuestas viven en localStorage de este navegador hasta que el
   cliente descarga su archivo (o las borra). Réplica del motor de entrevista del generador (misma lógica
   de visibilidad, repetición por fracción, defaults y bloqueos) para que el archivo sea 1:1 compatible. */
(function () {
  'use strict';
  const root = document.getElementById('entrevista');
  if (!root) return;
  const DATA_URL = root.dataset.datos;
  const HASH = (root.dataset.hash || '').trim();
  const KEY = 'pldmx_entrevista_v1';
  const KEY_OK = 'pldmx_entrevista_ok';
  const DIAS_RETENCION = 7;

  let D = null;              // datos de la entrevista (módulos + catálogo)
  let A = {};                // respuestas
  let modIdx = 0;
  let intentoGuardar = false;

  // ------------------------------------------------------------ utilidades
  const $ = (sel, el) => (el || document).querySelector(sel);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const vacio = (v) => v == null || v === '' || (Array.isArray(v) && v.length === 0) || (typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length === 0);
  const hoyISO = () => new Date().toISOString().slice(0, 10);
  const key = (qid, fr) => (fr ? `${qid}[${fr}]` : qid);
  const fraccion = (id) => D.catalogo.fracciones.find((f) => f.id === id);
  const idLegal = (fr) => (fraccion(fr) || { id_legal: fr }).id_legal;

  async function sha256(t) {
    const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(t));
    return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, '0')).join('');
  }
  function guardarLocal() {
    try { localStorage.setItem(KEY, JSON.stringify({ guardado: Date.now(), respuestas: A })); } catch (e) { /* modo privado */ }
  }
  function cargarLocal() {
    try {
      const raw = localStorage.getItem(KEY); if (!raw) return {};
      const obj = JSON.parse(raw);
      if (Date.now() - (obj.guardado || 0) > DIAS_RETENCION * 86400000) { localStorage.removeItem(KEY); return {}; }
      return obj.respuestas || {};
    } catch (e) { return {}; }
  }
  function borrarLocal() { try { localStorage.removeItem(KEY); sessionStorage.removeItem(KEY_OK); } catch (e) { /* nada */ } }

  // ------------------------------------------------------------ motor (réplica de dsl.py / engine.py)
  function get(qid, fr) {
    qid = qid.replace('{fr}', fr || '');
    if (qid in A) return A[qid];
    if (fr && key(qid, fr) in A) return A[key(qid, fr)];
    return undefined;
  }
  function evaluate(cond, fr) {
    if (!cond) return true;
    if (cond.all) return cond.all.every((c) => evaluate(c, fr));
    if (cond.any) return cond.any.some((c) => evaluate(c, fr));
    if (cond.not) return !evaluate(cond.not, fr);
    const v = get(cond.q, fr);
    if ('eq' in cond) return v === cond.eq;
    if ('ne' in cond) return v !== cond.ne;
    if ('in' in cond) return cond.in.includes(v);
    if ('includes' in cond) return Array.isArray(v) && v.includes(cond.includes);
    if ('includes_any' in cond) return Array.isArray(v) && cond.includes_any.some((e) => v.includes(e));
    return true;
  }
  function fraccionesSeleccionadas() {
    const sel = A.B1 || [];
    return D.catalogo.fracciones.map((f) => f.id).filter((id) => sel.includes(id));
  }
  function incisosActivos(fr) {
    const f = fraccion(fr); const sel = A[key('B2', fr)];
    return sel && sel.length ? f.incisos.filter((i) => sel.includes(i.id)) : f.incisos;
  }
  function identificacionSiempreObligatoria() {
    return fraccionesSeleccionadas().some((fr) => incisosActivos(fr).some((i) => i.identificacion_siempre));
  }
  function ponderacionesDefault() { return [Object.assign({}, D.catalogo.ponderaciones_artu)]; }
  function defaultRule(qid) {
    if (qid === 'D9') {
      if (A.A3 === 'PF') return A.A1;
      return { CONSEJO: 'Consejo de Administración', ADMIN_UNICO: 'Administrador Único', COMITE_TECNICO: 'Comité Técnico' }[A.A9];
    }
    if (qid === 'F3') return ponderacionesDefault();
    if (qid === 'L1') {
      if (A.F9 === 'ALTO') return 'EXTERNA';
      if ((A.F9 === 'BAJO' || A.F9 === 'MEDIO') && A.D15) return 'INTERNA';
      return 'EXTERNA';
    }
    return undefined;
  }
  function opcionesDe(q, fr) {
    if (q.opciones) return q.opciones;
    if (q.opciones_dinamicas === 'fracciones') return D.catalogo.fracciones.map((f) => ({ valor: f.id, label: `Fracción ${f.id_legal} — ${f.nombre}` }));
    if (q.opciones_dinamicas === 'incisos') return fr ? fraccion(fr).incisos.map((i) => ({ valor: i.id, label: i.descripcion })) : [];
    if (q.opciones_de_respuesta) {
      const items = A[q.opciones_de_respuesta.q] || [];
      return items.filter((it) => it && it[q.opciones_de_respuesta.campo]).map((it) => ({ valor: String(it[q.opciones_de_respuesta.campo]), label: String(it[q.opciones_de_respuesta.campo]) }));
    }
    return [];
  }
  function instancia(q, mod, fr) {
    if (!evaluate(q.show_if, fr)) return null;
    if (q.mostrar_solo_si_mas_de_un_inciso && fr && fraccion(fr).incisos.length <= 1) return null;
    const inst = {
      id: key(q.id, fr), base: q.id, modulo: mod, fr, texto: fr ? q.texto.replace('{fr}', idLegal(fr)) : q.texto, tipo: q.tipo,
      requerido: !!q.requerido, ayuda: q.ayuda || '', opciones: opcionesDe(q, fr), item_schema: q.item_schema || null, max_items: q.max_items || null,
      validacion: q.validacion || null, para_llm: !!q.para_llm, bloqueada: false, nota: '', default: undefined, default_origen: null,
    };
    // bloqueos legales / de la metodología
    if (inst.base === 'L1' && A.F9 === 'ALTO') { inst.bloqueada = true; inst.nota = 'Con resultado ALTO la auditoría debe ser externa (Reglas, Art. 44).'; }
    if (inst.base === 'E2' && identificacionSiempreObligatoria()) { inst.bloqueada = true; inst.nota = 'Al menos una de tus actividades exige identificar a todo cliente sin importar el monto.'; }
    if ((inst.base === 'F2' || inst.base === 'F3') && (A.F1 || 'ARTU') === 'ARTU') { inst.bloqueada = true; inst.nota = 'La metodología de riesgo de Artu fija estos valores; se muestran como referencia.'; }
    if (inst.base === 'L2' && (A.L1 || defaultRule('L1')) === 'EXTERNA') { inst.requerido = false; inst.nota = 'Si aún no has designado auditor externo, déjalo vacío.'; }
    // defaults (mismo orden que el generador)
    if (inst.bloqueada) {
      if (inst.base === 'L1') { inst.default = 'EXTERNA'; inst.default_origen = 'rule'; }
      if (inst.base === 'E2') { inst.default = 'SIEMPRE'; inst.default_origen = 'rule'; }
      if (inst.base === 'F2') { inst.default = '3'; inst.default_origen = 'rule'; }
      if (inst.base === 'F3') { inst.default = ponderacionesDefault(); inst.default_origen = 'rule'; }
    }
    if (inst.default === undefined && q.default_from && !vacio(A[q.default_from])) { inst.default = A[q.default_from]; inst.default_origen = 'from'; }
    if (inst.default === undefined && q.default_rule) { const v = defaultRule(q.default_rule); if (!vacio(v)) { inst.default = v; inst.default_origen = 'rule'; } }
    if (inst.default === undefined && 'default' in q) { inst.default = q.default === 'today' ? hoyISO() : q.default; inst.default_origen = 'default'; }
    return inst;
  }
  function instancias(modId) {
    const mod = D.modulos.find((m) => m.id === modId); const out = [];
    for (const q of mod.preguntas) {
      if (q.repeat_for) { for (const fr of fraccionesSeleccionadas()) { const i = instancia(q, modId, fr); if (i) out.push(i); } }
      else { const i = instancia(q, modId, null); if (i) out.push(i); }
    }
    return out;
  }
  function valorEfectivo(inst) { return inst.id in A && !vacio(A[inst.id]) ? A[inst.id] : inst.default; }
  function progreso() {
    const porMod = {}; let total = 0, contestadas = 0;
    for (const m of D.modulos) {
      const insts = instancias(m.id).filter((i) => i.requerido);
      const c = insts.filter((i) => !vacio(A[i.id]) || i.bloqueada).length;
      porMod[m.id] = { total: insts.length, contestadas: c }; total += insts.length; contestadas += c;
    }
    return { total, contestadas, pct: total ? Math.round(100 * contestadas / total) : 0, modulos: porMod };
  }
  function validar(inst, v) {
    const errs = [];
    if (inst.requerido && vacio(v) && !inst.bloqueada) { errs.push('Esta respuesta es obligatoria.'); return errs; }
    if (vacio(v)) return errs;
    const t = inst.tipo;
    if (t === 'number' || t === 'percent' || t === 'currency') {
      const n = Number(v); if (Number.isNaN(n)) errs.push('Debe ser un número.');
      else { if (t === 'percent' && (n < 0 || n > 100)) errs.push('Debe estar entre 0 y 100.'); if (t === 'currency' && n < 0) errs.push('No puede ser negativo.'); }
    }
    if (t === 'date' && !/^\d{4}-\d{2}-\d{2}$/.test(String(v))) errs.push('Fecha inválida.');
    if (inst.item_schema && Array.isArray(v)) {
      v.forEach((it, i) => { const faltan = Object.keys(inst.item_schema).filter((k) => it[k] == null || it[k] === ''); if (faltan.length) errs.push(`Fila ${i + 1}: completa ${faltan.join(', ')}.`); });
    }
    const val = inst.validacion;
    if (val === 'email' && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(v))) errs.push('Escribe un correo válido.');
    if (val && val.startsWith('regex:') && !new RegExp(val.slice(6)).test(String(v).trim().toUpperCase())) errs.push('El formato no es válido (revisa el RFC).');
    if (val && /^\d+\.\.\d+$/.test(val)) { const [a, b] = val.split('..').map(Number); if (Number(v) < a || Number(v) > b) errs.push(`Debe estar entre ${a} y ${b}.`); }
    if (val === 'cada valor <= 6' && Array.isArray(v) && v.some((it) => Object.values(it).some((x) => Number(x) > 6))) errs.push('El máximo legal es 6 meses.');
    if (val === '>=5' && Number(v) < 5) errs.push('La ley exige al menos 5 años de experiencia; el manual lo marcará como riesgo.');
    return errs;
  }
  function legible(inst, v) {
    if (vacio(v)) return '—';
    if (inst.opciones && inst.opciones.length) { const m = Object.fromEntries(inst.opciones.map((o) => [String(o.valor), o.label])); return (Array.isArray(v) ? v : [v]).map((x) => m[String(x)] || String(x)).join(', '); }
    if (typeof v === 'boolean') return v ? 'Sí' : 'No';
    if (Array.isArray(v)) { if (v.length && typeof v[0] === 'object') return v.map((it) => Object.entries(it).map(([k, x]) => `${k}: ${x === true ? 'Sí' : x === false ? 'No' : x}`).join(', ')).join('; '); return v.join(', '); }
    if (inst.tipo === 'currency') return '$' + Number(v).toLocaleString('es-MX', { minimumFractionDigits: 2 }) + ' MXN';
    if (inst.tipo === 'percent') return v + ' %';
    return String(v);
  }
  function respuestasCompletas() {
    // materializa defaults de preguntas bloqueadas y B2 automático (igual que hace el generador)
    const out = Object.assign({}, A);
    for (const m of D.modulos) for (const inst of instancias(m.id)) {
      if (inst.bloqueada && vacio(out[inst.id]) && inst.default !== undefined) out[inst.id] = inst.default;
    }
    for (const fr of fraccionesSeleccionadas()) { const f = fraccion(fr); const k = key('B2', fr); if (f.incisos.length === 1 && !(k in out)) out[k] = [f.incisos[0].id]; }
    return out;
  }

  // ------------------------------------------------------------ UI
  function toast(txt) {
    let t = $('#ent-toast'); if (!t) { t = document.createElement('div'); t.id = 'ent-toast'; t.className = 'toast'; root.appendChild(t); }
    t.textContent = txt; t.classList.add('ver'); clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('ver'), 1800);
  }
  function campo(inst) {
    const v = valorEfectivo(inst); const dis = inst.bloqueada ? 'disabled' : ''; const n = esc(inst.id);
    switch (inst.tipo) {
      case 'text': case 'email': return `<input type="text" name="${n}" value="${esc(v ?? '')}" ${dis}>`;
      case 'textarea': return `<textarea name="${n}" ${dis} placeholder="${inst.para_llm ? 'Escríbelo con tus palabras, como se lo explicarías a un colega; nosotros lo redactamos en el manual.' : 'Escribe aquí…'}">${esc(v ?? '')}</textarea>`;
      case 'number': case 'percent': case 'currency': return `<span style="display:inline-flex;align-items:center"><input type="number" step="any" name="${n}" value="${esc(v ?? '')}" ${dis} ${inst.tipo === 'percent' ? 'min="0" max="100"' : ''}>${inst.tipo === 'percent' ? '<span class="sufijo">%</span>' : inst.tipo === 'currency' ? '<span class="sufijo">MXN</span>' : ''}</span>`;
      case 'date': return `<input type="date" name="${n}" value="${esc(v ?? '')}" ${dis} style="max-width:240px">`;
      case 'boolean': return `<div class="opciones pills"><label><input type="radio" name="${n}" value="true" ${v === true ? 'checked' : ''} ${dis}> Sí</label><label><input type="radio" name="${n}" value="false" ${v === false ? 'checked' : ''} ${dis}> No</label></div>`;
      case 'select': return `<select name="${n}" ${dis}><option value="">— Selecciona —</option>${inst.opciones.map((o) => `<option value="${esc(o.valor)}" ${v != null && String(v) === String(o.valor) ? 'selected' : ''}>${esc(o.label)}</option>`).join('')}</select>`;
      case 'multiselect': { const sel = (v || []).map(String); return `<div class="opciones${inst.opciones.length > 6 ? ' grid' : ''}">${inst.opciones.map((o) => `<label><input type="checkbox" name="${n}" value="${esc(o.valor)}" ${sel.includes(String(o.valor)) ? 'checked' : ''} ${dis}> ${esc(o.label)}</label>`).join('') || '<span class="muted">Sin opciones todavía (depende de otra respuesta).</span>'}</div>`; }
      case 'list': {
        const items = Array.isArray(v) && v.length ? v : [{}]; const campos = Object.entries(inst.item_schema || {});
        const fila = (it, i) => `<div class="fila">${campos.map(([c, t]) => { const val = it[c]; let input;
          if (t.startsWith('select:')) input = `<select name="${n}__${i}__${c}" ${dis}><option value="">—</option>${t.slice(7, -1).split(', ').map((o) => `<option ${val === o ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select>`;
          else if (t === 'boolean') input = `<select name="${n}__${i}__${c}" ${dis}><option value="false" ${!val ? 'selected' : ''}>No</option><option value="true" ${val ? 'selected' : ''}>Sí</option></select>`;
          else if (t === 'number' || t === 'percent' || t === 'currency') input = `<input type="number" step="any" name="${n}__${i}__${c}" value="${esc(val ?? '')}" ${dis}>`;
          else if (t === 'date') input = `<input type="date" name="${n}__${i}__${c}" value="${esc(val ?? '')}" ${dis}>`;
          else input = `<input type="text" name="${n}__${i}__${c}" value="${esc(val ?? '')}" ${dis}>`;
          return `<div><label>${esc(c.replace(/_/g, ' '))}</label>${input}</div>`; }).join('')}</div>`;
        return `<div class="lista" data-q="${n}" data-campos='${esc(JSON.stringify(inst.item_schema))}' data-max="${inst.max_items || 0}">${items.map(fila).join('')}</div>${!inst.bloqueada && (!inst.max_items || inst.max_items > 1) ? `<button type="button" class="btn sec mini" data-agregar="${n}">+ Agregar</button>` : ''}`;
      }
      default: return '';
    }
  }
  function leerCampo(inst, form) {
    const n = inst.id;
    switch (inst.tipo) {
      case 'boolean': { const el = form.querySelector(`input[name="${CSS.escape(n)}"]:checked`); return el ? el.value === 'true' : undefined; }
      case 'multiselect': return [...form.querySelectorAll(`input[name="${CSS.escape(n)}"]:checked`)].map((e) => e.value);
      case 'list': {
        const campos = Object.entries(inst.item_schema || {}); const filas = [];
        form.querySelectorAll(`.lista[data-q="${CSS.escape(n)}"] .fila`).forEach((f) => {
          const it = {}; let lleno = false;
          campos.forEach(([c, t]) => { const el = f.querySelector(`[name$="__${c}"]`); let val = el ? el.value : '';
            if (t === 'boolean') val = val === 'true'; else if (t === 'number' || t === 'percent' || t === 'currency') val = val === '' ? null : Number(val); else val = String(val).trim();
            if (val !== '' && val !== null && val !== false) lleno = true; it[c] = val; });
          if (lleno) filas.push(it);
        });
        return filas;
      }
      case 'number': case 'percent': case 'currency': { const el = form.querySelector(`[name="${CSS.escape(n)}"]`); if (!el || el.value === '') return undefined; const x = Number(el.value); return Number.isNaN(x) ? el.value : x; }
      default: { const el = form.querySelector(`[name="${CSS.escape(n)}"]`); return el ? String(el.value).trim() : undefined; }
    }
  }
  function leerFormulario(modId) {
    const form = $('#ent-form'); if (!form) return;
    for (const inst of instancias(modId)) {
      if (inst.bloqueada) { if (inst.default !== undefined) A[inst.id] = inst.default; continue; }
      const v = leerCampo(inst, form);
      if (v === undefined || v === '') delete A[inst.id]; else A[inst.id] = v;
    }
    guardarLocal();
  }
  function errores(modId) {
    const out = {}; for (const inst of instancias(modId)) { const e = validar(inst, A[inst.id]); if (e.length) out[inst.id] = e; } return out;
  }
  function render() {
    const mod = D.modulos[modIdx]; const insts = instancias(mod.id); const p = progreso(); const errs = intentoGuardar ? errores(mod.id) : {};
    const pasos = D.modulos.map((m, i) => { const pm = p.modulos[m.id]; const listo = pm.total && pm.contestadas >= pm.total; return `<button type="button" class="paso ${i === modIdx ? 'activo' : listo ? 'listo' : ''}" data-ir="${i}" title="${esc(m.nombre)}"><span class="n">${listo && i !== modIdx ? '✓' : i + 1}</span><span class="txt">${esc(m.nombre)}</span><span class="cnt">${pm.contestadas}/${pm.total}</span></button>`; }).join('');
    root.innerHTML = `
      <div class="layout">
        <aside><div class="card"><p class="eyebrow">Tu entrevista</p><div class="lista-pasos">${pasos}</div>
          <p class="muted mini" style="margin:12px 0 0">Tus respuestas se guardan solo en este navegador. Nada se envía a internet hasta que descargues tu archivo.</p></div></aside>
        <div><div class="card">
          <div class="muted" style="display:flex;justify-content:space-between"><span>Progreso: ${p.contestadas} de ${p.total} respuestas obligatorias</span><span>${p.pct} %</span></div>
          <div class="progreso"><div style="width:${p.pct}%"></div></div>
          <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap"><span class="eyebrow">Módulo ${modIdx + 1} de ${D.modulos.length}</span><span class="muted mini">${insts.length} pregunta${insts.length !== 1 ? 's' : ''}${mod.minutos ? ` · unos ${mod.minutos} min` : ''}</span></div>
          <h1 style="margin:0 0 10px">${esc(mod.nombre)}</h1>
          ${mod.descripcion ? `<p class="intro">${esc(mod.descripcion)}</p>` : ''}
          ${intentoGuardar && Object.keys(errs).length ? `<p class="aviso">Revisa ${Object.keys(errs).length} respuesta${Object.keys(errs).length > 1 ? 's' : ''} marcada${Object.keys(errs).length > 1 ? 's' : ''} abajo.</p>` : ''}
          <form id="ent-form" onsubmit="return false">
            ${insts.map((inst) => `<div class="pregunta" id="p-${esc(inst.id)}">
              <span class="titulo">${esc(inst.texto)}${inst.requerido ? ' <span class="muted" title="obligatoria">*</span>' : ''}${vacio(A[inst.id]) && inst.default !== undefined ? `<span class="origen">${inst.default_origen === 'from' ? 'Copiado de otra respuesta' : 'Valor sugerido'}</span>` : ''}</span>
              ${inst.ayuda ? `<p class="ayuda-txt">${esc(inst.ayuda)}</p>` : ''}${inst.nota ? `<p class="nota">${esc(inst.nota)}</p>` : ''}
              ${campo(inst)}
              ${(errs[inst.id] || []).map((e) => `<div class="error">${esc(e)}</div>`).join('')}
            </div>`).join('') || '<p class="muted">Este módulo no tiene preguntas aplicables con tus respuestas actuales.</p>'}
            <div class="acciones barra">
              <span class="muted mini" style="flex-basis:100%">Las respuestas sugeridas cuentan al guardar. Puedes cerrar y volver cuando quieras desde esta misma computadora.</span>
              ${modIdx > 0 ? '<button type="button" class="btn sec" data-nav="anterior">← Anterior</button>' : ''}
              <button type="button" class="btn ok" data-nav="siguiente">${modIdx + 1 < D.modulos.length ? 'Guardar y siguiente →' : 'Guardar y terminar →'}</button>
              <button type="button" class="btn sec" data-nav="guardar">Guardar</button>
            </div>
          </form>
        </div></div>
      </div>`;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  function renderFinal() {
    const p = progreso(); const completa = p.total > 0 && p.contestadas >= p.total;
    const faltan = []; for (const m of D.modulos) { const pm = p.modulos[m.id]; if (pm.contestadas < pm.total) faltan.push(m); }
    const resumen = D.modulos.map((m) => { const insts = instancias(m.id); if (!insts.length) return ''; return `<h2>${esc(m.id)}. ${esc(m.nombre)}</h2><table class="resumen">${insts.map((i) => `<tr><th>${esc(i.texto)}</th><td>${esc(legible(i, valorEfectivo(i)))}</td></tr>`).join('')}</table>`; }).join('');
    const emp = A.A1 || '';
    root.innerHTML = `
      <div class="card" style="max-width:900px;margin:0 auto">
        <p class="eyebrow">Entrevista ${completa ? 'completa' : 'incompleta'}</p>
        <h1 style="margin:0 0 8px">${completa ? '¡Listo! Descarga tus respuestas' : 'Aún faltan respuestas'}</h1>
        ${completa
          ? `<p>Descarga tu <strong>archivo de respuestas</strong> y envíalo a Artu: con él elaboramos tu Manual de Políticas Internas. Si quieres conservar una copia legible, también puedes guardarlo en PDF.</p>
             <div class="acciones" style="margin-top:14px"><button type="button" class="btn ok" data-accion="descargar">Descargar mi archivo de respuestas</button><button type="button" class="btn sec" data-accion="pdf">Guardar en PDF</button><button type="button" class="btn sec" data-accion="volver">← Revisar respuestas</button></div>
             <p class="muted mini" style="margin-top:14px">Al descargar, tus respuestas se borran de este navegador por tu privacidad. Guarda el archivo (<code>respuestas-…json</code>) y envíalo tal cual; no lo edites.</p>`
          : `<p>Faltan respuestas obligatorias (${p.contestadas} de ${p.total}). Módulos pendientes: ${faltan.map((m) => `<a href="#" data-ir-mod="${esc(m.id)}">${esc(m.nombre)}</a>`).join(', ')}.</p>
             <div class="acciones"><button type="button" class="btn ok" data-ir-mod="${esc(faltan[0].id)}">Completar →</button></div>`}
        <details style="margin-top:22px"><summary class="muted">Ver todas mis respuestas</summary><div style="margin-top:12px">${resumen}</div></details>
        <p class="muted mini" style="margin-top:22px"><a href="#" data-accion="borrar">Borrar mis respuestas de este navegador</a></p>
      </div>
      <div class="ent-print" style="display:none"><h1>Cuestionario para el Manual de Políticas Internas PLD</h1><p>${esc(emp)}${A.A4 ? ' · RFC ' + esc(A.A4) : ''} · ${new Date().toLocaleDateString('es-MX')}</p>${resumen}</div>`;
    window.scrollTo({ top: 0 });
  }
  function descargar() {
    const r = respuestasCompletas();
    const paquete = Object.assign({ _formato: 'pldmx-entrevista/1', _version_entrevista: D.version_entrevista, _generado: new Date().toISOString(), _empresa: A.A1 || '', _rfc: A.A4 || '' }, r);
    const rfc = String(A.A4 || 'respuestas').replace(/[^A-Za-z0-9]/g, '').slice(0, 13) || 'respuestas';
    const blob = new Blob([JSON.stringify(paquete, null, 1)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `respuestas-${rfc}-${hoyISO()}.json`; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    borrarLocal();
    toast('Archivo descargado. Tus respuestas ya no están en este navegador.');
  }
  function imprimir() { const pr = $('.ent-print'); if (pr) { pr.style.display = 'block'; window.print(); setTimeout(() => { pr.style.display = 'none'; }, 500); } }

  root.addEventListener('click', (e) => {
    const t = e.target.closest('[data-nav],[data-ir],[data-ir-mod],[data-accion],[data-agregar]'); if (!t) return;
    if (t.dataset.agregar) { const cont = root.querySelector(`.lista[data-q="${CSS.escape(t.dataset.agregar)}"]`); const max = Number(cont.dataset.max || 0); const n = cont.querySelectorAll('.fila').length; if (max && n >= max) return; const fila = cont.querySelector('.fila').cloneNode(true); fila.querySelectorAll('input,select').forEach((el) => { el.name = el.name.replace(/__\d+__/, `__${n}__`); if (el.tagName === 'SELECT') el.selectedIndex = 0; else el.value = ''; }); cont.appendChild(fila); return; }
    if (t.dataset.nav) {
      const mod = D.modulos[modIdx]; leerFormulario(mod.id);
      if (t.dataset.nav === 'guardar') { intentoGuardar = false; render(); toast('✓ Guardado'); return; }
      if (t.dataset.nav === 'anterior') { intentoGuardar = false; modIdx = Math.max(0, modIdx - 1); render(); return; }
      const errs = errores(mod.id); intentoGuardar = true;
      if (Object.keys(errs).length) { render(); const first = root.querySelector('.error'); if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }
      intentoGuardar = false;
      if (modIdx + 1 < D.modulos.length) { modIdx += 1; render(); toast(`✓ Módulo ${mod.id} guardado`); } else { renderFinal(); }
      return;
    }
    if (t.dataset.ir !== undefined) { leerFormulario(D.modulos[modIdx].id); intentoGuardar = false; modIdx = Number(t.dataset.ir); render(); return; }
    if (t.dataset.irMod) { e.preventDefault(); modIdx = D.modulos.findIndex((m) => m.id === t.dataset.irMod); intentoGuardar = true; render(); return; }
    if (t.dataset.accion === 'descargar') { descargar(); return; }
    if (t.dataset.accion === 'pdf') { imprimir(); return; }
    if (t.dataset.accion === 'volver') { modIdx = 0; render(); return; }
    if (t.dataset.accion === 'borrar') { e.preventDefault(); if (confirm('¿Borrar todas tus respuestas de este navegador?')) { A = {}; borrarLocal(); modIdx = 0; render(); } }
  });
  // autoguardado y re-render al cambiar (aparecen las preguntas dependientes)
  root.addEventListener('change', (e) => {
    const form = $('#ent-form'); if (!form || !form.contains(e.target)) return;
    const activo = document.activeElement && document.activeElement.name;
    leerFormulario(D.modulos[modIdx].id); render();
    if (activo) { const el = root.querySelector(`[name="${CSS.escape(activo)}"]`); if (el && el.type !== 'radio' && el.type !== 'checkbox') el.focus(); }
    toast('✓ Guardado');
  });

  // ------------------------------------------------------------ puerta de acceso y arranque
  function renderGate(error) {
    root.innerHTML = `<div class="card gate"><div class="logo">Entrevista para tu Manual de Cumplimiento PLD</div>
      <p class="muted" style="margin:10px 0 18px">Escribe la contraseña que te compartió Artu para comenzar. La entrevista toma unos 35 minutos y puedes pausarla.</p>
      <form id="gate"><input type="password" id="gate-pw" placeholder="Contraseña" autocomplete="off" style="margin-bottom:12px">${error ? '<div class="error" style="margin-bottom:12px">Contraseña incorrecta.</div>' : ''}<button class="btn ok" style="width:100%">Comenzar →</button></form></div>`;
    $('#gate').addEventListener('submit', async (e) => { e.preventDefault(); const h = await sha256($('#gate-pw').value.trim()); if (h === HASH) { try { sessionStorage.setItem(KEY_OK, '1'); } catch (x) { /* nada */ } arrancar(); } else renderGate(true); });
  }
  function arrancar() { A = cargarLocal(); modIdx = 0; render(); }
  fetch(DATA_URL, { cache: 'no-store' }).then((r) => r.json()).then((d) => {
    D = d;
    let ok = false; try { ok = sessionStorage.getItem(KEY_OK) === '1'; } catch (x) { /* nada */ }
    if (!HASH || ok) arrancar(); else renderGate(false);
  }).catch(() => { root.innerHTML = '<div class="card"><p class="error">No se pudo cargar la entrevista. Recarga la página.</p></div>'; });

  // para pruebas automatizadas
  window.__entrevista = { instancias: (m) => instancias(m).map((i) => ({ id: i.id, requerido: i.requerido, bloqueada: i.bloqueada })), progreso, respuestasCompletas, set: (obj) => { A = Object.assign({}, obj); guardarLocal(); modIdx = 0; render(); }, final: renderFinal, get: () => A };
})();
