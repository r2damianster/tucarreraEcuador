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
    renderResultados(data.resultados);
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
