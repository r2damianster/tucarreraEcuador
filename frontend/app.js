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
  resultadosCompletos: [], // todo lo que devolvió la API para el perfil/preferencias actuales, sin filtrar
  preferenciasActuales: null,
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
  document.querySelector("main").classList.toggle("main-ancho", nombre === "resultados");

  // En desktop el panel de filtros vive abierto como sidebar (no tiene
  // sentido que arranque colapsado si ya hay espacio al lado); en mobile
  // sigue colapsado por defecto para no tapar la pantalla.
  if (nombre === "resultados" && window.matchMedia("(min-width: 860px)").matches) {
    document.getElementById("panel-filtros").open = true;
  }

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
    // Cambiar de provincia vacía el cantón, así que el slider de cercanía
    // vuelve a quedar sin punto de referencia: se apaga y, si ya había
    // resultados calculados con cercanía, hay que recalcularlos.
    const habiaPeso = Number(document.getElementById("pref-cercania").value) > 0;
    sincronizarCercania();
    if (habiaPeso && estado.perfilRiasec) verResultados();
  });

  // El cantón es el origen del cálculo de distancia (Haversine en el motor):
  // sin él, "importancia de cercanía" no tiene desde dónde medir. Este
  // listener se registra antes que el de refetch de más abajo, para que el
  // slider ya esté sincronizado cuando se dispare la búsqueda.
  document.getElementById("pref-canton").addEventListener("change", sincronizarCercania);

  const rango = document.getElementById("pref-cercania");
  rango.addEventListener("input", actualizarEtiquetaCercania);
  sincronizarCercania();

  // El panel de filtros vive en la pantalla de resultados (ver
  // panel-filtros en index.html): cambiar cualquiera de estos vuelve a
  // pedir recomendaciones sin tener que navegar a otra pantalla. "input"
  // en el slider ya actualiza la etiqueta arriba; "change" (se suelta el
  // mouse) es lo que dispara la búsqueda, para no repetirla en cada pixel.
  ["pref-modalidad", "pref-financiamiento", "pref-tipo-ies", "pref-nivel", "pref-canton", "pref-cercania"]
    .forEach((id) => {
      document.getElementById(id).addEventListener("change", () => {
        if (estado.perfilRiasec) verResultados();
      });
    });
}

// Habilita el slider de cercanía sólo si hay cantón elegido; si no lo hay,
// lo apaga y lo devuelve a 0 para que no quede un peso "fantasma" que el
// motor traduciría en score_cercania = 0 para todas las carreras (hundiendo
// el score_final de todo el pool sin ningún criterio geográfico real).
function sincronizarCercania() {
  const rango = document.getElementById("pref-cercania");
  const hayCanton = Boolean(valorOVacio("pref-canton"));
  rango.disabled = !hayCanton;
  if (!hayCanton) rango.value = 0;
  actualizarEtiquetaCercania();
}

function actualizarEtiquetaCercania() {
  const rango = document.getElementById("pref-cercania");
  const valor = Number(rango.value);
  const etiqueta = document.getElementById("valor-cercania");
  if (rango.disabled) {
    etiqueta.textContent = "Elige tu provincia y cantón para activar la cercanía";
    return;
  }
  etiqueta.textContent = valor === 0 ? "Indiferente (0%)" : `${valor}% de importancia`;
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
  };

  estado.preferenciasActuales = preferencias;
  renderFiltrosActivos();
  reiniciarComentarioIA();

  const cont = document.getElementById("lista-resultados");
  cont.innerHTML = `<p class="aviso">Buscando...</p>`;
  mostrarPantalla("resultados");

  try {
    const data = await apiPost("/api/recomendar", { perfil_riasec: estado.perfilRiasec, preferencias });
    // La API devuelve TODO lo que pasa el filtro duro, ordenado por score_final
    // -- ninguna diversificación ni tope acá. El filtro de "afinidad mínima"
    // (slider) decide en el cliente cuánto de esto se muestra, sin volver a
    // pedirle nada al servidor.
    estado.resultadosCompletos = data.resultados;
    aplicarFiltroAfinidad();
  } catch (e) {
    cont.innerHTML = `<p class="error">No se pudo obtener recomendaciones: ${e.message}</p>`;
  }
}

function renderFiltrosActivos() {
  const cont = document.getElementById("filtros-activos");
  const p = estado.preferenciasActuales;
  if (!p) {
    cont.innerHTML = "";
    return;
  }

  const chips = [];
  if (p.modalidad) chips.push(titleCase(p.modalidad));
  if (p.financiamiento) chips.push(titleCase(p.financiamiento));
  if (p.tipo_ies) chips.push(titleCase(p.tipo_ies));
  if (p.niveles && p.niveles.length) chips.push(titleCase(p.niveles[0]));
  // provincia_estudiante no afecta el score (solo canton_estudiante, ver
  // motor `_score_cercania`) -- no se usa acá para no sugerir un efecto
  // que no existe.
  if (p.peso_cercania > 0 && p.canton_estudiante) {
    chips.push(`Cerca de ${titleCase(p.canton_estudiante)} · ${Math.round(p.peso_cercania * 100)}%`);
  }

  const chipsHtml = chips.length
    ? chips.map((c) => `<span class="tag">${c}</span>`).join("")
    : `<span class="tag chip-filtro-vacio">Sin filtros de búsqueda (todas las modalidades, financiamientos y ubicaciones)</span>`;

  cont.innerHTML = `
    <div class="chips-wrap">${chipsHtml}</div>
    <button type="button" class="link-editar" id="btn-editar-filtros">Editar filtros</button>`;
  document.getElementById("btn-editar-filtros").addEventListener("click", () => {
    const panel = document.getElementById("panel-filtros");
    panel.open = true;
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

// ---------- Comentario sobre el perfil (IA, opcional) ----------
async function generarComentarioIA() {
  const boton = document.getElementById("btn-comentario-ia");
  const cont = document.getElementById("comentario-ia");
  boton.disabled = true;
  boton.textContent = "Generando...";
  cont.innerHTML = "";

  // Los campos amplios se los damos ya calculados por nuestro propio motor
  // -- el prompt del backend no deja que la IA invente otros ni mencione
  // carreras/universidades por su cuenta.
  const camposPrincipales = [...new Set(
    estado.resultadosCompletos
      .slice()
      .sort((a, b) => b.score_final - a.score_final)
      .map((r) => r.CAMPO_AMPLIO_NORMALIZADO)
  )].slice(0, 3);

  try {
    const data = await apiPost("/api/comentario-perfil", {
      perfil_riasec: estado.perfilRiasec,
      campos_principales: camposPrincipales,
    });
    cont.innerHTML = `
      <div class="comentario-texto">${escaparHtml(data.comentario).replace(/\n+/g, "<br>")}</div>
      <div class="comentario-nota">Comentario generado por IA (Groq/Llama) -- orientativo, no reemplaza asesoría vocacional profesional.</div>`;
    boton.style.display = "none";
  } catch (e) {
    // Falla silenciosa a propósito (cuota gratuita agotada, timeout, etc.):
    // sin mensaje de error feo, solo se avisa que no está disponible ahora.
    cont.innerHTML = `<p class="aviso">Comentario no disponible por ahora. Probá de nuevo más tarde.</p>`;
    boton.disabled = false;
    boton.textContent = "Generar comentario sobre tu perfil (IA)";
  }
}

function reiniciarComentarioIA() {
  const boton = document.getElementById("btn-comentario-ia");
  boton.style.display = "";
  boton.disabled = false;
  boton.textContent = "Generar comentario sobre tu perfil (IA)";
  document.getElementById("comentario-ia").innerHTML = "";
}

function valorOVacio(id) {
  const v = document.getElementById(id).value;
  return v === "" ? null : v;
}

function aplicarFiltroAfinidad() {
  const umbral = Number(document.getElementById("filtro-afinidad").value) / 100;
  // Se filtra por score_final (afinidad RIASEC + cercanía ya mezcladas, el
  // mismo puntaje que ordena la lista) y no por similitud_riasec pura --
  // si no, subir "importancia de cercanía" a 100% reordenaba todo por
  // distancia pero el umbral seguía dejando pasar cualquier cosa lejana con
  // buena afinidad RIASEC (Galápagos incluido), sin importar cuán lejos.
  const filtrados = estado.resultadosCompletos.filter((r) => r.score_final >= umbral);
  renderResultados(filtrados, umbral);
  renderDiagrama(filtrados);
}

function renderResultados(resultados, umbralActual) {
  const cont = document.getElementById("lista-resultados");
  if (!resultados.length) {
    const hayResultadosSinFiltrar = estado.resultadosCompletos.length > 0;
    cont.innerHTML = hayResultadosSinFiltrar
      ? `<p class="aviso">Ninguna carrera llega a ${Math.round(umbralActual * 100)}% de afinidad. Bajá el filtro "Afinidad mínima a mostrar" de arriba para ver más opciones.</p>`
      : `<p class="aviso">No se encontraron carreras con esos filtros. Prueba relajando alguna preferencia.</p>`;
    return;
  }
  const contador = document.createElement("p");
  contador.className = "contador-resultados";
  contador.textContent = `Mostrando ${resultados.length} de ${estado.resultadosCompletos.length} carreras que cumplen tus filtros.`;
  cont.innerHTML = "";
  cont.appendChild(contador);
  const pesoCercania = (estado.preferenciasActuales && estado.preferenciasActuales.peso_cercania) || 0;
  resultados.forEach((r) => {
    const div = document.createElement("div");
    div.className = "resultado-item";
    const chipCercania = pesoCercania > 0
      ? `<span class="tag">Cercanía ${Math.round(r.score_cercania * 100)}%</span>`
      : "";
    div.innerHTML = `
      <h3>${titleCase(r.NOMBRE_CARRERA)}</h3>
      <div class="ies">${titleCase(r.NOMBRE_IES)} · ${titleCase(r.CANTÓN)}, ${titleCase(r.PROVINCIA)}</div>
      <div class="etiquetas">
        <span class="tag">${titleCase(r.CAMPO_AMPLIO_NORMALIZADO)}</span>
        <span class="tag">${titleCase(r.MODALIDAD)}</span>
        <span class="tag">${titleCase(r.TIPO_FINANCIAMIENTO)}</span>
        <span class="tag">Afinidad ${Math.round(r.similitud_riasec * 100)}%</span>
        ${chipCercania}
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
// Tier = umbral sobre score_final (afinidad RIASEC ya mezclada con cercanía
// según el peso que el estudiante le dio -- NO sobre similitud_riasec pura).
// Usar similitud pura acá desacoplaba el anillo de lo que el slider de
// afinidad mínima realmente filtra: con "importancia de cercanía" al 100%,
// una carrera lejana con buena afinidad RIASEC (Galápagos, por ejemplo)
// terminaba en "núcleo" aunque el ranking real la mandara al final por
// distancia. Con score_final, ambos quedan consistentes.
const UMBRAL_NUCLEO = 0.8;
const UMBRAL_INTERMEDIO = 0.5;
function calcularTier(puntaje) {
  if (puntaje >= UMBRAL_NUCLEO) return "nucleo";
  if (puntaje >= UMBRAL_INTERMEDIO) return "intermedio";
  return "alejada";
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
  resultados.forEach((r) => porTier[calcularTier(r.score_final)].push(r));
  Object.values(porTier).forEach((lista) => lista.sort((a, b) => b.score_final - a.score_final));

  // El diagrama es un vistazo visual, no un listado -- con el slider mostrando
  // todo, un anillo puede tener cientos de carreras y dibujarlas todas sería
  // un borrón ilegible. Se muestra una muestra de las mejores de cada anillo;
  // la lista de abajo (sin este tope) sigue teniendo el detalle completo.
  const MAX_PUNTOS_POR_ANILLO = 24;
  const porTierRecortado = {
    nucleo: porTier.nucleo.slice(0, MAX_PUNTOS_POR_ANILLO),
    intermedio: porTier.intermedio.slice(0, MAX_PUNTOS_POR_ANILLO),
    alejada: porTier.alejada.slice(0, MAX_PUNTOS_POR_ANILLO),
  };

  const puntos = ["nucleo", "intermedio", "alejada"].flatMap((tier) =>
    ubicarPuntosEnBanda(porTierRecortado[tier], BANDAS_TIER[tier])
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
        <circle class="dv-punto ${calcularTier(resultado.score_final)}" cx="${cx}" cy="${cy}" r="5" data-idx="${i}"><title>${titulo}</title></circle>
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

  renderLeyendaDiagrama(porTier, MAX_PUNTOS_POR_ANILLO);
}

function mostrarDetalleDiagrama(r) {
  const cont = document.getElementById("dv-detalle");
  const pesoCercania = (estado.preferenciasActuales && estado.preferenciasActuales.peso_cercania) || 0;
  const chipCercania = pesoCercania > 0
    ? `<span class="tag">Cercanía ${Math.round(r.score_cercania * 100)}%</span>`
    : "";
  cont.innerHTML = `
    <h4>${titleCase(r.NOMBRE_CARRERA)}</h4>
    <div class="ies">${titleCase(r.NOMBRE_IES)} · ${titleCase(r.CANTÓN)}, ${titleCase(r.PROVINCIA)}</div>
    <div class="etiquetas">
      <span class="tag">${titleCase(r.CAMPO_AMPLIO_NORMALIZADO)}</span>
      <span class="tag">${NOMBRE_TIER[calcularTier(r.score_final)]}</span>
      <span class="tag">Afinidad ${Math.round(r.similitud_riasec * 100)}%</span>
      ${chipCercania}
    </div>`;
}

function renderLeyendaDiagrama(porTier, maxPorAnillo) {
  const cont = document.getElementById("dv-leyenda");
  const etiquetaConteo = (tier) => {
    const total = porTier[tier].length;
    return total > maxPorAnillo ? `${total}, mostrando ${maxPorAnillo}` : `${total}`;
  };
  cont.innerHTML = `
    <div class="item"><span class="swatch" style="background:var(--tier-nucleo)"></span>Núcleo afín (${etiquetaConteo("nucleo")})</div>
    <div class="item"><span class="swatch" style="background:var(--tier-intermedio)"></span>Afinidad intermedia (${etiquetaConteo("intermedio")})</div>
    <div class="item"><span class="swatch" style="background:var(--tier-alejada)"></span>Más alejadas (${etiquetaConteo("alejada")})</div>`;
}

document.getElementById("btn-comentario-ia").addEventListener("click", generarComentarioIA);

document.getElementById("filtro-afinidad").addEventListener("input", (ev) => {
  document.getElementById("valor-filtro-afinidad").textContent = `Desde ${ev.target.value}%`;
  aplicarFiltroAfinidad();
});

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
