"""
API del Recomendador de Carreras Ecuador.

Envuelve el motor de recomendación (src/04_motor_recomendacion.py) y el test
vocacional RIASEC (backend/test_riasec.py) en endpoints REST que el frontend
(carpeta frontend/) consume.

Correr en desarrollo:
    uvicorn backend.main:app --reload --port 8000
(ejecutar desde la raíz del repo, con las dependencias de requirements.txt
instaladas)
"""
import importlib
import os
import sys
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .test_riasec import DESCRIPCION_DIMENSION, ITEMS_RIASEC, NOMBRE_DIMENSION

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))
motor_mod = importlib.import_module("04_motor_recomendacion")

app = FastAPI(
    title="Recomendador de Carreras Ecuador",
    description="Test vocacional RIASEC + motor de recomendación sobre la oferta académica de las IES del Ecuador (SENESCYT).",
    version="0.1.0",
)

# En dev, sin ALLOWED_ORIGINS definida, acepta cualquier origen (el frontend
# estático corre desde file:// o http://localhost:<puerto variable>). En
# producción, definir ALLOWED_ORIGINS con el/los dominios de Vercel separados
# por coma, p. ej. "https://tucarrera-ecuador.vercel.app".
_allowed_origins = os.environ.get("ALLOWED_ORIGINS")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins.split(",") if _allowed_origins else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Comentario de IA sobre el perfil vocacional (opcional -- ver /api/comentario-perfil).
# La key vive SOLO acá (variable de entorno del backend, nunca en el frontend).
# Si no está configurada, el endpoint devuelve 503 y el frontend lo maneja en
# silencio (sin mostrar error feo al estudiante).
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELOS_URL = "https://api.groq.com/openai/v1/models"

# Groq retira modelos cada cierto tiempo y responde 404 al pedir uno
# decomisado -- así se rompió este endpoint en silencio. En vez de confiar en
# un nombre fijo, se consulta la lista viva de modelos y se prueban por orden
# los que sigan disponibles.
GROQ_MODELOS_PREFERIDOS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "qwen/qwen3.6-27b",
]
# Modelos que no sirven para este comentario: audio (whisper/orpheus),
# moderación (guard/safeguard), sistemas agénticos con herramientas
# (compound) y modelos de otro idioma (allam es árabe).
_PATRONES_MODELO_DESCARTADO = (
    "whisper", "orpheus", "tts", "guard", "compound", "allam",
)

_modelos_candidatos_cache: Optional[list[str]] = None


def _listar_modelos_groq() -> list[str]:
    """IDs de los modelos que la cuenta de Groq tiene disponibles hoy."""
    respuesta = httpx.get(
        GROQ_MODELOS_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        timeout=10.0,
    )
    respuesta.raise_for_status()
    return [m["id"] for m in respuesta.json().get("data", [])]


def _modelos_candidatos(forzar_refresco: bool = False) -> list[str]:
    """Modelos a probar, en orden: primero el configurado por entorno, luego
    los preferidos que sigan vivos, y al final cualquier otro modelo de texto
    de la cuenta. Se cachea: la lista de Groq sólo se consulta al arrancar (o
    cuando una llamada falló y hay que volver a resolver)."""
    global _modelos_candidatos_cache
    if _modelos_candidatos_cache and not forzar_refresco:
        return _modelos_candidatos_cache

    disponibles = _listar_modelos_groq()
    ordenados = [GROQ_MODEL] + [m for m in GROQ_MODELOS_PREFERIDOS if m != GROQ_MODEL]
    candidatos = [m for m in ordenados if m in disponibles]
    candidatos += [
        m for m in disponibles
        if m not in candidatos and not any(p in m for p in _PATRONES_MODELO_DESCARTADO)
    ]

    if not candidatos:
        raise RuntimeError("La cuenta de Groq no expone ningún modelo de chat utilizable.")
    _modelos_candidatos_cache = candidatos
    return candidatos


_motor: Optional["motor_mod.MotorRecomendacion"] = None


def get_motor() -> "motor_mod.MotorRecomendacion":
    global _motor
    if _motor is None:
        _motor = motor_mod.MotorRecomendacion.desde_csv()
    return _motor


# ---------- Modelos de entrada/salida ----------

class RespuestasTest(BaseModel):
    respuestas: dict[str, bool] = Field(
        ..., description="id del ítem (p. ej. 'R3') -> True si le interesa al estudiante"
    )


class PerfilRiasec(BaseModel):
    R: float = 0.0
    I: float = 0.0
    A: float = 0.0
    S: float = 0.0
    E: float = 0.0
    C: float = 0.0


class PreferenciasIn(BaseModel):
    modalidad: Optional[str] = None
    financiamiento: Optional[str] = None
    tipo_ies: Optional[str] = None
    niveles: Optional[list[str]] = None
    provincia_estudiante: Optional[str] = None
    canton_estudiante: Optional[str] = None
    peso_cercania: float = Field(0.0, ge=0.0, le=1.0)
    incluir_posgrado: bool = False


class SolicitudRecomendacion(BaseModel):
    perfil_riasec: PerfilRiasec
    preferencias: PreferenciasIn = PreferenciasIn()


class ComentarioPerfilIn(BaseModel):
    perfil_riasec: PerfilRiasec
    campos_principales: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Campos amplios ya calculados por el motor (el prompt no deja que la IA invente otros).",
    )


# ---------- Endpoints ----------

@app.get("/api/salud")
def salud():
    return {"estado": "ok"}


@app.get("/api/test-riasec")
def test_riasec():
    """Devuelve los 60 ítems del test (sin exponer la dimensión de cada uno,
    para no sesgar al estudiante) y la info descriptiva de las 6 dimensiones."""
    items_publicos = [{"id": it["id"], "texto": it["texto"]} for it in ITEMS_RIASEC]
    return {
        "items": items_publicos,
        "dimensiones": [
            {"clave": d, "nombre": NOMBRE_DIMENSION[d], "descripcion": DESCRIPCION_DIMENSION[d]}
            for d in ["R", "I", "A", "S", "E", "C"]
        ],
    }


@app.post("/api/calcular-perfil", response_model=PerfilRiasec)
def calcular_perfil(payload: RespuestasTest):
    ids_validos = {it["id"] for it in ITEMS_RIASEC}
    desconocidos = set(payload.respuestas) - ids_validos
    if desconocidos:
        raise HTTPException(400, f"IDs de ítem desconocidos: {sorted(desconocidos)}")

    conteo = {"R": 0, "I": 0, "A": 0, "S": 0, "E": 0, "C": 0}
    for item in ITEMS_RIASEC:
        if payload.respuestas.get(item["id"]):
            conteo[item["dimension"]] += 1
    # 10 ítems por dimensión -> puntaje 0..1
    return PerfilRiasec(**{k: v / 10 for k, v in conteo.items()})


@app.get("/api/opciones")
def opciones():
    """Valores disponibles para los filtros/preferencias del frontend."""
    oferta = get_motor().oferta
    pregrado = oferta[oferta["ES_PREGRADO"]]
    provincias = sorted(oferta["PROVINCIA"].unique().tolist())
    cantones_por_provincia = (
        oferta[["PROVINCIA", "CANTÓN"]].drop_duplicates()
        .groupby("PROVINCIA")["CANTÓN"].apply(lambda s: sorted(s.unique().tolist())).to_dict()
    )
    return {
        "modalidades": sorted(oferta["MODALIDAD"].unique().tolist()),
        "financiamientos": sorted(oferta["TIPO_FINANCIAMIENTO"].unique().tolist()),
        "tipos_ies": sorted(oferta["TIPO_IES"].unique().tolist()),
        "niveles_pregrado": sorted(pregrado["NIVEL_FORMACIÓN"].unique().tolist()),
        "provincias": provincias,
        "cantones_por_provincia": cantones_por_provincia,
    }


@app.post("/api/recomendar")
def recomendar(payload: SolicitudRecomendacion):
    motor = get_motor()
    prefs = motor_mod.Preferencias(**payload.preferencias.model_dump())
    try:
        resultado = motor.buscar(payload.perfil_riasec.model_dump(), prefs)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"resultados": resultado.to_dict(orient="records")}


@app.post("/api/comentario-perfil")
def comentario_perfil(payload: ComentarioPerfilIn):
    """Comentario breve generado por IA (Groq) sobre el perfil vocacional del
    estudiante. Solo recibe los 6 puntajes RIASEC y los campos amplios que YA
    calculó el motor (nunca deja que el modelo invente carreras/universidades
    por su cuenta -- ver el prompt). Falla en silencio (503) si no hay key
    configurada, se acabó la cuota gratuita de Groq, o cualquier otro error:
    es una función decorativa, nunca debe tumbar ni bloquear el resto de la
    app."""
    if not GROQ_API_KEY:
        raise HTTPException(503, "Comentario con IA no configurado en este servidor.")

    dims = payload.perfil_riasec.model_dump()
    resumen_perfil = ", ".join(f"{NOMBRE_DIMENSION[d]} {round(v * 100)}%" for d, v in dims.items())
    campos = ", ".join(payload.campos_principales[:3]) or "sin campos destacados todavía"

    prompt = (
        "Redactá un comentario breve (100 a 150 palabras) sobre el perfil vocacional RIASEC "
        f"(modelo de Holland) de un estudiante ecuatoriano de bachillerato: {resumen_perfil}. "
        f"Los campos de estudio más afines a ese perfil, ya calculados por un sistema aparte "
        f"(no los cambies ni agregues otros, no inventes carreras ni universidades): {campos}. "
        "Español neutro, tono reflexivo y motivador, en tercera persona o hablándole directo "
        "al estudiante sobre SU perfil -- pero NUNCA en primera persona como si vos fueras un "
        "orientador vocacional, un profesor o cualquier persona real: sos un comentario "
        "automático, no un interlocutor. No digas 'conversá conmigo' ni nada que sugiera que "
        "hay una relación o seguimiento continuo con quien escribe esto. Describí qué tipo de "
        "actividades y ambientes de trabajo suelen encajarle a alguien con este perfil. No "
        "prometas éxito laboral ni resultados garantizados. Cerrá recordando que la decisión "
        "final de qué estudiar es del estudiante, y que conviene conversarlo con un orientador "
        "vocacional real (una persona, no este comentario)."
    )

    try:
        comentario = _pedir_comentario_a_groq(prompt)
    except Exception as e:
        print(f"[comentario-perfil] no se pudo generar: {e}")
        raise HTTPException(503, "No se pudo generar el comentario en este momento.")

    return {"comentario": comentario}


def _pedir_comentario_a_groq(prompt: str) -> str:
    """Pide el comentario probando los modelos disponibles por orden. Pasa al
    siguiente si Groq rechaza el modelo (404) o si devuelve texto vacío --
    esto último pasa con los modelos de razonamiento, que pueden consumir
    todo el presupuesto de tokens razonando y dejar `content` en blanco."""
    fallos = []
    for modelo in _modelos_candidatos():
        try:
            respuesta = httpx.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": modelo,
                    "messages": [{"role": "user", "content": prompt}],
                    # Holgado a propósito: el comentario pedido son 100-150
                    # palabras, pero un modelo de razonamiento gasta tokens
                    # antes de escribir la respuesta visible.
                    "max_tokens": 1500,
                    "temperature": 0.7,
                    # Los modelos gpt-oss aceptan este parámetro y con él
                    # razonan menos; los que no lo soportan lo ignoran.
                    "reasoning_effort": "low",
                },
                timeout=30.0,
            )
            if respuesta.status_code >= 400:
                # El cuerpo trae el motivo real (modelo decomisado, cuota
                # agotada, key inválida); raise_for_status lo descartaba, que
                # fue justamente lo que ocultó la causa la vez pasada.
                fallos.append(f"{modelo}: HTTP {respuesta.status_code} {respuesta.text[:200]}")
                continue
            comentario = (respuesta.json()["choices"][0]["message"].get("content") or "").strip()
            if not comentario:
                fallos.append(f"{modelo}: respondió 200 con content vacío")
                continue
            return comentario
        except Exception as e:
            fallos.append(f"{modelo}: {e}")

    # Ningún modelo sirvió: puede que la lista cacheada esté vieja.
    _modelos_candidatos(forzar_refresco=True)
    raise RuntimeError("Ningún modelo de Groq devolvió comentario. " + " | ".join(fallos)[:500])


@app.get("/api/diagnostico-ia")
def diagnostico_ia():
    """Estado de la integración con Groq, para diagnosticar sin entrar al
    servidor. NO expone la API key: sólo si está presente y su longitud."""
    estado = {
        "key_configurada": bool(GROQ_API_KEY),
        "key_longitud": len(GROQ_API_KEY) if GROQ_API_KEY else 0,
        "modelo_preferido": GROQ_MODEL,
        "modelos_candidatos": _modelos_candidatos_cache,
    }
    if not GROQ_API_KEY:
        estado["error"] = "Falta GROQ_API_KEY en el entorno del backend."
        return estado
    try:
        estado["modelos_disponibles"] = sorted(_listar_modelos_groq())
        estado["modelos_candidatos"] = _modelos_candidatos(forzar_refresco=True)
    except Exception as e:
        estado["error"] = str(e)[:300]
    return estado
