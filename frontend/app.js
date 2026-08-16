// Frontend del Recomendador de Carreras Ecuador.
// Vanilla JS, sin dependencias -- consume la API de backend/main.py.
//
// Si sirves este archivo desde un origen distinto al de la API (por
// ejemplo abriendo index.html directo con file://), ajusta API_BASE.
const API_BASE = window.API_BASE || "http://127.0.0.1:8000";

const estado = {
  items: [],
  respuestas: {},        // id_item -> true/false
  perfilRiasec: null,
  opciones: null,
  cantonesPorProvincia: {},
};

// ---------- Utilidades ----------
async function apiGet(ruta) {
  const r = await fetch(`${API_BASE}${ruta}`);
  if (!r.ok) throw new Error(`GET ${ruta} -> ${r.status}`);
  return r.json();
}
async function apiPost(ruta, body) {
  const r = await fetch(`${API_BASE}${ruta}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const detalle = await r.text();
    throw new Error(`POST ${ruta} -> ${r.status}: ${detalle}`);
  }
  return r.json();
}

function mostrarPantalla(nombre) {
  document.querySelectorAll("section.pantalla").forEach((s) => s.classList.remove("visible"));
  document.getElementById(`pantalla-${nombre}`).classList.add("visible");

  const orden = { test: 1, preferencias: 2, resultados: 3 };
  document.querySelectorAll(".pasos .paso").forEach((el) => {
    const n = Number(el.dataset.paso);
    el.classList.toggle("activo", n === orden[nombre]);
    el.classList.toggle("hecho", n < orden[nombre]);
  });
}

// ---------- Paso 1: test vocacional ----------
async function iniciarTest() {
  const data = await apiGet("/api/test-riasec");
  estado.items = data.items;
  const contenedor = document.getElementById("lista-items");
  contenedor.innerHTML = "";

  data.items.forEach((item) => {
    const fila = document.createElement("div");
    fila.className = "item-test";
    fila.innerHTML = `
      <div class="texto">${item.texto}</div>
      <div class="switch-grupo" data-id="${item.id}">
        <button type="button" class="si">Me interesa</button>
        <button type="button" class="no">No me interesa</button>
      </div>`;
    contenedor.appendChild(fila);
  });

  contenedor.addEventListener("click", (ev) => {
    const boton = ev.target.closest("button");
    if (!boton) return;
    const grupo = boton.closest(".switch-grupo");
    const id = grupo.dataset.id;
    const valor = boton.classList.contains("si");
    estado.respuestas[id] = valor;
    grupo.querySelectorAll("button").forEach((b) => b.classList.remove("activo"));
    boton.classList.add("activo");
    actualizarProgresoTest();
  });
}

function actualizarProgresoTest() {
  const respondidos = Object.keys(estado.respuestas).length;
  const total = estado.items.length;
  document.getElementById("barra-test").style.width = `${(respondidos / total) * 100}%`;
  document.getElementById("btn-ir-preferencias").disabled = respondidos < total;
}

async function irAPreferencias() {
  estado.perfilRiasec = await apiPost("/api/calcular-perfil", { respuestas: estado.respuestas });
  renderResumenPerfil();
  if (!estado.opciones) await cargarOpciones();
  mostrarPantalla("preferencias");
}

const NOMBRES_DIM = { R: "Realista", I: "Investigativo", A: "Artístico", S: "Social", E: "Emprendedor", C: "Convencional" };

function renderResumenPerfil() {
  const cont = document.getElementById("resumen-perfil");
  cont.innerHTML = "";
  Object.entries(estado.perfilRiasec).forEach(([dim, valor]) => {
    const div = document.createElement("div");
    div.className = "barra-dim";
    div.innerHTML = `
      <div class="nombre">${NOMBRES_DIM[dim]} — ${Math.round(valor * 100)}%</div>
      <div class="barra-fondo"><div style="width:${valor * 100}%"></div></div>`;
    cont.appendChild(div);
  });
}

// ---------- Paso 2: preferencias ----------
async function cargarOpciones() {
  const data = await apiGet("/api/opciones");
  estado.opciones = data;
  estado.cantonesPorProvincia = data.cantones_por_provincia;

  llenarSelect("pref-modalidad", data.modalidades);
  llenarSelect("pref-financiamiento", data.financiamientos);
  llenarSelect("pref-tipo-ies", data.tipos_ies);
  llenarSelect("pref-nivel", data.niveles_pregrado);
  llenarSelect("pref-provincia", data.provincias);

  document.getElementById("pref-provincia").addEventListener("change", (ev) => {
    const cantones = estado.cantonesPorProvincia[ev.target.value] || [];
    llenarSelect("pref-canton", cantones);
  });

  const rango = document.getElementById("pref-cercania");
  rango.addEventListener("input", () => {
    const v = Number(rango.value);
    document.getElementById("valor-cercania").textContent =
      v === 0 ? "Indiferente (0%)" : `${v}% de importancia`;
  });
}

function llenarSelect(idSelect, valores) {
  const select = document.getElementById(idSelect);
  const primera = select.options[0];
  select.innerHTML = "";
  select.appendChild(primera);
  valores.forEach((v) => {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = titleCase(v);
    select.appendChild(opt);
  });
}

function titleCase(texto) {
  return texto.toLowerCase().replace(/(^|\s|\()([a-záéíóúñ])/g, (m, sep, letra) => sep + letra.toUpperCase());
}

// ---------- Paso 3: resultados ----------
async function verResultados() {
  const preferencias = {
    modalidad: valorOVacio("pref-modalidad"),
    financiamiento: valorOVacio("pref-financiamiento"),
    tipo_ies: valorOVacio("pref-tipo-ies"),
    niveles: valorOVacio("pref-nivel") ? [document.getElementById("pref-nivel").value] : null,
    provincia_estudiante: valorOVacio("pref-provincia"),
    canton_estudiante: valorOVacio("pref-canton"),
    peso_cercania: Number(document.getElementById("pref-cercania").value) / 100,
    top_n: 12,
  };

  const cont = document.getElementById("lista-resultados");
  cont.innerHTML = `<p class="aviso">Buscando...</p>`;
  mostrarPantalla("resultados");

  try {
    const data = await apiPost("/api/recomendar", { perfil_riasec: estado.perfilRiasec, preferencias });
    const resultados = data.resultados;
    // Si el 100% cayó en "alejada" es porque la API no manda `tier` todavía
    // (backend desactualizado) -- resolverTier() lo usa como fallback seguro,
    // pero en ese caso no filtramos la lista: mostramos todo, como antes de
    // que existiera el diagrama de afinidad, en vez de dejarla vacía.
    const sinTiersReales = resultados.length > 0 && resultados.every((r) => resolverTier(r) === "alejada");
    renderResultados(sinTiersReales ? resultados : resultados.filter((r) => resolverTier(r) !== "alejada"));
    renderDiagrama(resultados);
  } catch (e) {
    cont.innerHTML = `<p class="error">No se pudo obtener recomendaciones: ${e.message}</p>`;
  }
}

function valorOVacio(id) {
  const v = document.getElementById(id).value;
  return v === "" ? null : v;
}

function renderResultados(resultados) {
  const cont = document.getElementById("lista-resultados");
  if (!resultados.length) {
    cont.innerHTML = `<p class="aviso">No se encontraron carreras con esos filtros. Prueba relajando alguna preferencia.</p>`;
    return;
  }
  cont.innerHTML = "";
  resultados.forEach((r) => {
    const div = document.createElement("div");
    div.className = "resultado-item";
    div.innerHTML = `
      <h3>${titleCase(r.NOMBRE_CARRERA)}</h3>
      <div class="ies">${titleCase(r.NOMBRE_IES)} · ${titleCase(r.CANTÓN)}, ${titleCase(r.PROVINCIA)}</div>
      <div class="etiquetas">
        <span class="tag">${titleCase(r.CAMPO_AMPLIO_NORMALIZADO)}</span>
        <span class="tag">${titleCase(r.MODALIDAD)}</span>
        <span class="tag">${titleCase(r.TIPO_FINANCIAMIENTO)}</span>
        <span class="tag">Afinidad ${Math.round(r.similitud_riasec * 100)}%</span>
      </div>`;
    cont.appendChild(div);
  });
}

// ---------- Diagrama de afinidad (círculos concéntricos, tipo Euler) ----------
const CENTRO_DIAGRAMA = 170;
const BANDAS_TIER = {
  nucleo: [0, 58],
  intermedio: [58, 122],
  alejada: [122, 162],
};
const NOMBRE_TIER = {
  nucleo: "Núcleo afín",
  intermedio: "Afinidad intermedia",
  alejada: "Más alejada",
};
const TIERS_VALIDOS = new Set(["nucleo", "intermedio", "alejada"]);
// Si la API no manda un tier reconocido (p. ej. backend viejo sin esta
// funcionalidad todavía desplegado), cae a "alejada" en vez de romper el
// render o mostrar "undefined" -- pero de forma consistente en todos lados
// (bucket del punto, conteo de la leyenda y etiqueta del detalle usan esta
// misma función, nunca el r.tier crudo).
function resolverTier(r) {
  return TIERS_VALIDOS.has(r.tier) ? r.tier : "alejada";
}
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5)); // ~137.5°, distribución tipo girasol

function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}

function ubicarPuntosEnBanda(lista, [radioMin, radioMax]) {
  const n = lista.length;
  return lista.map((resultado, i) => {
    // sqrt reparte los puntos por área (no por radio) para que no se
    // amontonen cerca del borde interno de la banda.
    const fraccionRadio = n <= 1 ? 0.5 : Math.sqrt((i + 0.5) / n);
    const radio = radioMin + fraccionRadio * (radioMax - radioMin);
    const angulo = i * GOLDEN_ANGLE;
    return {
      resultado,
      x: CENTRO_DIAGRAMA + radio * Math.cos(angulo),
      y: CENTRO_DIAGRAMA + radio * Math.sin(angulo),
    };
  });
}

function renderDiagrama(resultados) {
  const cont = document.getElementById("diagrama-afinidad");
  const leyenda = document.getElementById("dv-leyenda");
  if (!resultados.length) {
    cont.innerHTML = "";
    leyenda.innerHTML = "";
    return;
  }

  const porTier = { nucleo: [], intermedio: [], alejada: [] };
  resultados.forEach((r) => porTier[resolverTier(r)].push(r));
  Object.values(porTier).forEach((lista) => lista.sort((a, b) => b.score_final - a.score_final));

  const puntos = ["nucleo", "intermedio", "alejada"].flatMap((tier) =>
    ubicarPuntosEnBanda(porTier[tier], BANDAS_TIER[tier])
  );

  const anillos = Object.values(BANDAS_TIER)
    .map(([, radioMax]) => `<circle class="dv-anillo" cx="${CENTRO_DIAGRAMA}" cy="${CENTRO_DIAGRAMA}" r="${radioMax}" />`)
    .join("");

  const puntosSvg = puntos
    .map(({ resultado, x, y }, i) => {
      const cx = x.toFixed(1);
      const cy = y.toFixed(1);
      const titulo = `${escaparHtml(resultado.NOMBRE_CARRERA)} — ${Math.round(resultado.similitud_riasec * 100)}% afinidad`;
      return `
        <circle class="dv-punto ${resolverTier(resultado)}" cx="${cx}" cy="${cy}" r="5" data-idx="${i}"><title>${titulo}</title></circle>
        <circle class="dv-punto-hit" cx="${cx}" cy="${cy}" r="12" data-idx="${i}" />`;
    })
    .join("");

  cont.innerHTML = `
    <svg viewBox="0 0 340 340" role="img" aria-label="Diagrama de afinidad de carreras recomendadas">
      ${anillos}
      ${puntosSvg}
      <circle class="dv-centro" cx="${CENTRO_DIAGRAMA}" cy="${CENTRO_DIAGRAMA}" r="3.5" />
    </svg>`;

  cont.querySelectorAll("[data-idx]").forEach((el) => {
    const { resultado } = puntos[Number(el.dataset.idx)];
    el.addEventListener("mouseenter", () => mostrarDetalleDiagrama(resultado));
    el.addEventListener("click", () => mostrarDetalleDiagrama(resultado));
  });

  renderLeyendaDiagrama(resultados);
}

function mostrarDetalleDiagrama(r) {
  const cont = document.getElementById("dv-detalle");
  cont.innerHTML = `
    <h4>${titleCase(r.NOMBRE_CARRERA)}</h4>
    <div class="ies">${titleCase(r.NOMBRE_IES)} · ${titleCase(r.CANTÓN)}, ${titleCase(r.PROVINCIA)}</div>
    <div class="etiquetas">
      <span class="tag">${titleCase(r.CAMPO_AMPLIO_NORMALIZADO)}</span>
      <span class="tag">${NOMBRE_TIER[resolverTier(r)]}</span>
      <span class="tag">Afinidad ${Math.round(r.similitud_riasec * 100)}%</span>
    </div>`;
}

function renderLeyendaDiagrama(resultados) {
  const cont = document.getElementById("dv-leyenda");
  const nAlejada = resultados.filter((r) => resolverTier(r) === "alejada").length;
  cont.innerHTML = `
    <div class="item"><span class="swatch" style="background:var(--tier-nucleo)"></span>Núcleo afín</div>
    <div class="item"><span class="swatch" style="background:var(--tier-intermedio)"></span>Afinidad intermedia</div>
    <div class="item"><span class="swatch" style="background:var(--tier-alejada)"></span>Más alejadas (máx. ${nAlejada})</div>`;
}

// ---------- Navegación ----------
document.getElementById("btn-ir-preferencias").addEventListener("click", irAPreferencias);
document.getElementById("btn-volver-test").addEventListener("click", () => mostrarPantalla("test"));
document.getElementById("btn-ver-resultados").addEventListener("click", verResultados);
document.getElementById("btn-volver-preferencias").addEventListener("click", () => mostrarPantalla("preferencias"));
document.getElementById("btn-reiniciar").addEventListener("click", () => {
  estado.respuestas = {};
  document.querySelectorAll(".switch-grupo button").forEach((b) => b.classList.remove("activo"));
  actualizarProgresoTest();
  mostrarPantalla("test");
});

mostrarPantalla("test");
iniciarTest().catch((e) => {
  document.getElementById("lista-items").innerHTML =
    `<p class="error">No se pudo conectar con la API (${API_BASE}). ¿Está corriendo "uvicorn backend.main:app"? Detalle: ${e.message}</p>`;
});
