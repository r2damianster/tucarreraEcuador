"""
Construye la tabla cantón -> (latitud, longitud) que necesita el motor de
recomendación para calcular "cercanía a donde vive el estudiante".

Fuente de coordenadas: gist público "Coordenadas de todos los cantones de
Ecuador" (ver Referencias). Se cruza contra los cantones que realmente
aparecen en la base de oferta académica (99 cantones) y se reporta
cualquier cantón sin coincidencia para revisión manual.
"""
import re
import unicodedata
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_COORDS = BASE_DIR / "data" / "raw" / "cantones_coords_raw.csv"
OFERTA_LIMPIA = BASE_DIR / "data" / "processed" / "oferta_limpia.csv"
OUT_CSV = BASE_DIR / "data" / "processed" / "cantones_coordenadas.csv"

# Cantones que existen más de una vez en el país con el mismo nombre; el gist
# fuente los desambigua como "Nombre (Provincia)". Aquí mapeamos manualmente
# la provincia real (según la división político-administrativa del Ecuador)
# a la que corresponde cada alias.
DESAMBIGUACION = {
    ("BOLIVAR", "CARCHI"): "Bolívar (Carchi)",
    ("BOLIVAR", "MANABI"): "Bolívar (Manabí)",
    ("OLMEDO", "MANABI"): "Olmedo (Manabí)",
    ("OLMEDO", "LOJA"): "Olmedo (Loja)",
}

# El nombre del cantón en la base SENESCYT no siempre coincide con el nombre
# de la cabecera cantonal que usa el gist de coordenadas (p. ej. el cantón
# "Rumiñahui" tiene como cabecera "Sangolquí", y así aparece en la base).
# Se resuelven primero contra otra fila del propio gist:
ALIAS_A_GIST = {
    "SANGOLQUI": "Rumiñahui",
    "BANOS DE AGUA SANTA": "Baños",
    "SAN PEDRO DE PELILEO": "Pelileo",
    "SANTIAGO DE PILLARO": "Píllaro",
    "YANZATZA": "Yantzaza",
}

# Cantones que no aparecen en el gist, o para los que el gist tenía una
# coordenada claramente errónea (verificado cruzando con otras fuentes:
# Wikipedia / geodatos.net / world-airport-codes -- ver Referencias). Estos
# quedan con coordenada verificada a mano y marcados como tal en la columna
# "fuente".
OVERRIDES_MANUALES = {
    ("GENERAL PLAZA", "MORONA SANTIAGO"): (-2.73333, -78.3167038),  # Méndez (cabecera del cantón Santiago/General Plaza)
    ("PUYO", "PASTAZA"): (-1.49156, -78.00337),  # el gist traía la coordenada genérica de la provincia, no de la ciudad
}


def quitar_tildes(texto: str) -> str:
    if pd.isna(texto):
        return texto
    texto = str(texto).strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto)


def main():
    coords = pd.read_csv(RAW_COORDS, sep="|")
    coords["nombre_key"] = coords["nombre"].apply(quitar_tildes)
    # Para los nombres con desambiguación "(Provincia)", guardamos también la
    # clave "limpia" sin el paréntesis, por si el cruce simple ya alcanza.
    coords["nombre_key_simple"] = coords["nombre_key"].str.replace(
        r" \([A-ZÁÉÍÓÚÑ]+\)$", "", regex=True
    )

    oferta = pd.read_csv(OFERTA_LIMPIA)
    cantones_bd = (
        oferta[["PROVINCIA", "CANTÓN", "PROVINCIA_KEY", "CANTON_KEY"]]
        .drop_duplicates()
        .sort_values(["PROVINCIA", "CANTÓN"])
        .reset_index(drop=True)
    )
    print(f"Cantones únicos en la base de oferta: {len(cantones_bd)}")

    filas = []
    sin_match = []
    for _, row in cantones_bd.iterrows():
        prov_key, canton_key = row["PROVINCIA_KEY"], row["CANTON_KEY"]
        fuente = "gist"

        override = OVERRIDES_MANUALES.get((canton_key, prov_key))
        if override:
            lat, lon = override
            fuente = "manual_verificado"
        else:
            alias_gist = ALIAS_A_GIST.get(canton_key)
            alias_desamb = DESAMBIGUACION.get((canton_key, prov_key))
            match = None
            if alias_gist:
                match = coords.loc[coords["nombre_key"] == quitar_tildes(alias_gist)]
            if (match is None or match.empty) and alias_desamb:
                match = coords.loc[coords["nombre"] == alias_desamb]
            if match is None or match.empty:
                match = coords.loc[coords["nombre_key"] == canton_key]
            if match.empty:
                match = coords.loc[coords["nombre_key_simple"] == canton_key]

            if match.empty:
                sin_match.append((row["PROVINCIA"], row["CANTÓN"]))
                lat, lon, fuente = None, None, None
            else:
                lat, lon = float(match.iloc[0]["lat"]), float(match.iloc[0]["lon"])

        filas.append({
            "provincia": row["PROVINCIA"],
            "canton": row["CANTÓN"],
            "provincia_key": prov_key,
            "canton_key": canton_key,
            "lat": lat,
            "lon": lon,
            "fuente": fuente,
        })

    out = pd.DataFrame(filas)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False, encoding="utf-8")
    print(f"Guardado: {OUT_CSV}")
    print(f"Emparejados: {out['lat'].notna().sum()} / {len(out)}")

    if sin_match:
        print("\nCantones SIN coordenadas (completar manualmente en el CSV):")
        for prov, canton in sin_match:
            print(f"  - {canton} ({prov})")
    else:
        print("\nTodos los cantones de la base quedaron emparejados con coordenadas.")


if __name__ == "__main__":
    main()
