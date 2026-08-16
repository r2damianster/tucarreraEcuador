"""
Motor de recomendación de carreras (scikit-learn).

Combina:
  1. Filtro duro por preferencias obligatorias del estudiante (pandas).
  2. Búsqueda por similitud de contenido: sklearn.neighbors.NearestNeighbors
     sobre el vector RIASEC de 6 dimensiones (perfil del estudiante vs.
     perfil de cada oferta académica).
  3. Distancia geográfica (fórmula de Haversine) entre el cantón del
     estudiante y el cantón de la sede, quien puede pesarse como
     "importante" o "indiferente".
  4. Sin diversificación ni tope de resultados: `buscar()` devuelve TODAS las
     carreras que pasan el filtro duro, ordenadas por score y sin duplicados
     de (carrera, IES). El frontend decide cuántas mostrar con un filtro de
     afinidad mínima dinámico (slider) -- ver `frontend/app.js`. El campo
     `tier` (núcleo/intermedio/alejada, usado en el diagrama de afinidad) se
     calcula ahí mismo por umbral de `similitud_riasec`, no acá.

Uso rápido (ver también src/05_demo.py):

    from importlib import import_module
    motor_mod = import_module("04_motor_recomendacion")
    motor = motor_mod.MotorRecomendacion.desde_csv()
    resultados = motor.buscar(perfil_riasec={...}, preferencias={...})
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler

BASE_DIR = Path(__file__).resolve().parent.parent
OFERTA_CSV = BASE_DIR / "data" / "processed" / "oferta_limpia.csv"
CANTONES_CSV = BASE_DIR / "data" / "processed" / "cantones_coordenadas.csv"
MAPEO_CSV = BASE_DIR / "data" / "processed" / "mapeo_riasec_campo_amplio.csv"

DIMENSIONES = ["R", "I", "A", "S", "E", "C"]


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Distancia en km entre dos puntos geográficos (fórmula de Haversine)."""
    if any(pd.isna(v) for v in (lat1, lon1, lat2, lon2)):
        return np.nan
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@dataclass
class Preferencias:
    modalidad: Optional[str] = None          # p. ej. "PRESENCIAL"; None = indiferente
    financiamiento: Optional[str] = None      # p. ej. "PUBLICA"
    tipo_ies: Optional[str] = None            # "UNIVERSIDAD" | "INSTITUTO"
    niveles: Optional[list] = None            # lista de NIVEL_FORMACIÓN aceptados
    provincia_estudiante: Optional[str] = None
    canton_estudiante: Optional[str] = None
    peso_cercania: float = 0.0                # 0 = indiferente ... 1 = solo importa la cercanía
    incluir_posgrado: bool = False


class MotorRecomendacion:
    def __init__(self, oferta: pd.DataFrame, cantones: pd.DataFrame, mapeo: pd.DataFrame):
        self.oferta = oferta.merge(
            cantones[["provincia_key", "canton_key", "lat", "lon"]],
            left_on=["PROVINCIA_KEY", "CANTON_KEY"],
            right_on=["provincia_key", "canton_key"],
            how="left",
        )
        self.oferta = self.oferta.merge(
            mapeo, left_on="CAMPO_AMPLIO_NORMALIZADO", right_on="campo_amplio_normalizado", how="left"
        )

        pesos = self.oferta[DIMENSIONES].to_numpy(dtype=float)
        sumas = pesos.sum(axis=1, keepdims=True)
        sumas[sumas == 0] = 1.0
        self.oferta[[f"vec_{d}" for d in DIMENSIONES]] = pesos / sumas

    @classmethod
    def desde_csv(cls) -> "MotorRecomendacion":
        oferta = pd.read_csv(OFERTA_CSV)
        cantones = pd.read_csv(CANTONES_CSV)
        mapeo = pd.read_csv(MAPEO_CSV)
        return cls(oferta, cantones, mapeo)

    def _filtrar_duro(self, prefs: Preferencias) -> pd.DataFrame:
        df = self.oferta
        df = df[df["ES_PREGRADO"] | prefs.incluir_posgrado]
        if prefs.modalidad:
            df = df[df["MODALIDAD"].str.upper() == prefs.modalidad.upper()]
        if prefs.financiamiento:
            df = df[df["TIPO_FINANCIAMIENTO"].str.upper() == prefs.financiamiento.upper()]
        if prefs.tipo_ies:
            df = df[df["TIPO_IES"].str.upper() == prefs.tipo_ies.upper()]
        if prefs.niveles:
            niveles_upper = [n.upper() for n in prefs.niveles]
            df = df[df["NIVEL_FORMACIÓN"].str.upper().isin(niveles_upper)]
        return df.reset_index(drop=True)

    def _score_cercania(self, df: pd.DataFrame, prefs: Preferencias) -> pd.Series:
        if not prefs.canton_estudiante:
            return pd.Series(0.0, index=df.index)
        canton_ref = self.oferta.loc[
            (self.oferta["CANTON_KEY"] == prefs.canton_estudiante.upper())
        ]
        if canton_ref.empty or pd.isna(canton_ref.iloc[0]["lat"]):
            return pd.Series(0.0, index=df.index)
        lat0, lon0 = canton_ref.iloc[0]["lat"], canton_ref.iloc[0]["lon"]

        dist = df.apply(lambda r: haversine_km(lat0, lon0, r["lat"], r["lon"]), axis=1)
        dist = dist.fillna(dist.max() if dist.notna().any() else 0.0)
        if dist.max() == dist.min():
            return pd.Series(1.0, index=df.index)
        # invertir: más cerca -> score más alto, escalado 0-1
        prox = 1 - MinMaxScaler().fit_transform(dist.to_numpy().reshape(-1, 1)).ravel()
        return pd.Series(prox, index=df.index)

    def buscar(self, perfil_riasec: dict, prefs: Preferencias) -> pd.DataFrame:
        """
        perfil_riasec: dict con puntajes 0-1 para R, I, A, S, E, C (salen del
        test vocacional). No hace falta que sumen 1, se normalizan aquí.
        """
        vector_estudiante = np.array([perfil_riasec.get(d, 0.0) for d in DIMENSIONES], dtype=float)
        if vector_estudiante.sum() == 0:
            raise ValueError("El perfil RIASEC del estudiante no puede estar vacío.")
        vector_estudiante = vector_estudiante / vector_estudiante.sum()

        candidatos = self._filtrar_duro(prefs)
        if candidatos.empty:
            return candidatos

        matriz = candidatos[[f"vec_{d}" for d in DIMENSIONES]].to_numpy()

        # Búsqueda por similitud con NearestNeighbors (algoritmo de búsqueda
        # de scikit-learn) en el espacio RIASEC. Se pide el ranking completo
        # (k = todos los candidatos, no un top-k chico) a propósito: como el
        # vector RIASEC hoy solo toma ~10 direcciones distintas (una por
        # campo amplio), truncar temprano a un k pequeño puede dejar TODO el
        # pool ocupado por el único campo más cercano (si tiene muchas
        # ofertas) y la diversificación posterior nunca llega a ver los
        # demás campos. Con un dataset de unos pocos miles de filas, pedirle
        # a NearestNeighbors el ranking completo sigue siendo barato.
        k = len(candidatos)
        vecinos = NearestNeighbors(n_neighbors=k, metric="cosine")
        vecinos.fit(matriz)
        distancias, indices = vecinos.kneighbors(vector_estudiante.reshape(1, -1))
        similitud = 1 - distancias.ravel()  # cosine distance -> similitud

        pool = candidatos.iloc[indices.ravel()].copy()
        pool["similitud_riasec"] = similitud

        pool["score_cercania"] = self._score_cercania(pool, prefs).values
        pool["score_final"] = (
            (1 - prefs.peso_cercania) * pool["similitud_riasec"]
            + prefs.peso_cercania * pool["score_cercania"]
        )
        pool = pool.sort_values("score_final", ascending=False)

        resultado = self._deduplicar(pool)
        columnas = [
            "NOMBRE_CARRERA", "NOMBRE_IES", "CAMPO_AMPLIO_NORMALIZADO", "PROVINCIA", "CANTÓN",
            "MODALIDAD", "TIPO_FINANCIAMIENTO", "NIVEL_FORMACIÓN", "similitud_riasec",
            "score_cercania", "score_final",
        ]
        return resultado[columnas].reset_index(drop=True)

    @staticmethod
    def _deduplicar(pool: pd.DataFrame) -> pd.DataFrame:
        """Quita filas repetidas de la misma pareja (carrera, IES) -- ocurre
        en la fuente SENESCYT (variantes de modalidad/jornada que igual pasan
        el filtro duro, o duplicados de carga) -- quedándose con la de mejor
        score_final. No recorta ni diversifica por campo amplio: el pool ya
        viene ordenado por score_final descendente, así que a quien consuma
        el resultado (frontend) le queda decidir cuántas filas mostrar."""
        return pool.drop_duplicates(subset=["NOMBRE_CARRERA", "NOMBRE_IES"], keep="first")

    def explorar_clusters_vocacionales(self, n_clusters: int = 10) -> pd.DataFrame:
        """Uso exploratorio (no forma parte de una búsqueda puntual): agrupa
        TODAS las combinaciones únicas (carrera, campo amplio) de la base en
        n_clusters clústeres vocacionales con sklearn.cluster.KMeans sobre el
        vector RIASEC, para navegación tipo "explora por familia de interés"
        en el frontend. Devuelve una fila por carrera única con su clúster."""
        base = self.oferta.drop_duplicates(subset=["NOMBRE_CARRERA", "CAMPO_AMPLIO_NORMALIZADO"]).copy()
        matriz = base[[f"vec_{d}" for d in DIMENSIONES]].to_numpy()
        n_clusters = min(n_clusters, len(base))
        km = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
        base["cluster_vocacional"] = km.fit_predict(matriz)
        return base[["NOMBRE_CARRERA", "CAMPO_AMPLIO_NORMALIZADO", "cluster_vocacional"]].reset_index(drop=True)
