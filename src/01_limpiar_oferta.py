"""
Limpieza y normalización de la base de oferta académica de las IES del Ecuador
(fuente: SENESCYT, datosabiertos.gob.ec).

Qué hace:
  1. Lee el Excel crudo (data/raw/base-datos-abiertos_oferta-academica_05022025.xlsx).
  2. Normaliza texto (tildes, mayúsculas, espacios) en columnas categóricas.
  3. Colapsa CAMPO_AMPLIO (21 valores crudos, con duplicados por tilde/nomenclatura)
     a 10 categorías canónicas (campo del conocimiento tipo CINE/ISCED-F).
  4. Filtra por defecto los niveles de posgrado (el sistema se enfoca en el
     estudiante que recién termina el bachillerato), dejando un flag por si
     se quiere reactivar el posgrado como filtro opcional.
  5. Guarda el resultado limpio en data/processed/oferta_limpia.csv y en
     una base SQLite (data/processed/recomendador.db, tabla "oferta").

Este script es reproducible: si SENESCYT publica una versión más nueva del
Excel, basta con reemplazar el archivo en data/raw y volver a correrlo.
"""
import re
import sqlite3
import unicodedata
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_XLSX = BASE_DIR / "data" / "raw" / "base-datos-abiertos_oferta-academica_05022025.xlsx"
OUT_CSV = BASE_DIR / "data" / "processed" / "oferta_limpia.csv"
OUT_DB = BASE_DIR / "data" / "processed" / "recomendador.db"


def quitar_tildes(texto: str) -> str:
    """Normaliza a mayúsculas sin tildes, útil solo para EMPAREJAR (no para mostrar)."""
    if pd.isna(texto):
        return texto
    texto = str(texto).strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto)
    return texto


# Diccionario de equivalencias CAMPO_AMPLIO (clave = texto sin tildes en mayúsculas
# tal como aparece en el Excel crudo) -> categoría canónica (10 campos, estilo ISCED-F/CINE).
MAPA_CAMPO_AMPLIO = {
    "ADMINISTRACION": "Administración de Empresas y Derecho",
    "ADMINISTRACION DE EMPRESAS Y DERECHO": "Administración de Empresas y Derecho",
    "INGENIERIA, INDUSTRIA Y CONSTRUCCION": "Ingeniería, Industria y Construcción",
    "SALUD Y BIENESTAR": "Salud y Bienestar",
    "SALUD Y SERVICIOS SOCIALES": "Salud y Bienestar",
    "EDUCACION": "Educación",
    "CIENCIAS SOCIALES, PERIODISMO, INFORMACION Y DERECHO": "Ciencias Sociales, Periodismo e Información",
    "CIENCIAS SOCIALES, PERIODISMO E INFORMACION": "Ciencias Sociales, Periodismo e Información",
    "CIENCIAS SOCIALES, EDUCACION COMERCIAL Y DERECHO": "Ciencias Sociales, Periodismo e Información",
    "SERVICIOS": "Servicios",
    "TECNOLOGIAS DE LA INFORMACION Y LA COMUNICACION (TIC)": "Tecnologías de la Información y la Comunicación (TIC)",
    "TECNOLOGIAS DE LA INFORMACION Y COMUNICACION (TIC)": "Tecnologías de la Información y la Comunicación (TIC)",
    "ARTES Y HUMANIDADES": "Artes y Humanidades",
    "HUMANIDADES Y ARTES": "Artes y Humanidades",
    "AGRICULTURA, SILVICULTURA, PESCA Y VETERINARIA": "Agricultura, Silvicultura, Pesca y Veterinaria",
    "AGRICULTURA": "Agricultura, Silvicultura, Pesca y Veterinaria",
    "CIENCIAS NATURALES, MATEMATICAS Y ESTADISTICA": "Ciencias Naturales, Matemáticas y Estadística",
    "CIENCIAS": "Ciencias Naturales, Matemáticas y Estadística",
}

# Niveles de formación que entran al flujo principal del recomendador
# (se excluye por defecto el cuarto nivel / posgrado).
NIVELES_PREGRADO = {
    "TERCER NIVEL O PREGRADO",
    "TERCER NIVEL TECNICO SUPERIOR",
    "TERCER NIVEL TECNOLOGICO SUPERIOR",
    "TERCER NIVEL TECNOLOGICO SUPERIOR UNIVERSITARIO",
    "EDUCACION SUPERIOR DE GRADO O TERCER NIVEL",
}


def normalizar_campo_amplio(valor: str) -> str:
    clave = quitar_tildes(valor)
    if clave not in MAPA_CAMPO_AMPLIO:
        raise KeyError(
            f"CAMPO_AMPLIO sin mapeo: {valor!r} (clave normalizada {clave!r}). "
            "Agrega este valor a MAPA_CAMPO_AMPLIO en 01_limpiar_oferta.py."
        )
    return MAPA_CAMPO_AMPLIO[clave]


def canonizar_grafia(df, columna_visible: str, columna_clave: str):
    """Unifica la grafía visible de un lugar dentro de cada clave sin tildes.

    La base de SENESCYT trae el mismo cantón escrito de dos formas (p. ej.
    "SAMBORONDÓN" en 355 filas y "SAMBORONDON" en 1). Ambas comparten
    CANTON_KEY, así que sin unificar la grafía el cantón se cuenta dos veces
    y la tabla de coordenadas termina con la clave duplicada -- lo que en el
    motor duplica por merge toda la oferta de ese cantón. Nos quedamos con la
    grafía más frecuente.
    """
    frecuencias = (
        df.groupby([columna_clave, columna_visible]).size()
        .rename("filas").reset_index()
        .sort_values([columna_clave, "filas"], ascending=[True, False])
    )
    grafia_canonica = (
        frecuencias.drop_duplicates(columna_clave)
        .set_index(columna_clave)[columna_visible]
    )
    return df[columna_clave].map(grafia_canonica)


def main():
    df = pd.read_excel(RAW_XLSX)
    print(f"Filas leídas: {len(df)}")

    # Normalización básica de texto en columnas clave (preserva tildes para mostrar).
    for col in ["NOMBRE_IES", "NOMBRE_CARRERA", "PROVINCIA", "CANTÓN", "TIPO_IES",
                "TIPO_FINANCIAMIENTO", "MODALIDAD", "NIVEL_FORMACIÓN"]:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].str.replace(r"\s+", " ", regex=True)

    # CAMPO_AMPLIO -> 10 categorías canónicas
    df["CAMPO_AMPLIO_NORMALIZADO"] = df["CAMPO_AMPLIO"].apply(normalizar_campo_amplio)

    # Flag de nivel de pregrado (para filtrar posgrado por defecto en la app)
    df["ES_PREGRADO"] = df["NIVEL_FORMACIÓN"].apply(quitar_tildes).isin(NIVELES_PREGRADO)

    # Clave de emparejamiento cantón (sin tildes) para cruzar con la tabla de coordenadas
    df["CANTON_KEY"] = df["CANTÓN"].apply(quitar_tildes)
    df["PROVINCIA_KEY"] = df["PROVINCIA"].apply(quitar_tildes)

    # Una sola grafía visible por clave, para no contar dos veces el mismo cantón
    df["CANTÓN"] = canonizar_grafia(df, "CANTÓN", "CANTON_KEY")
    df["PROVINCIA"] = canonizar_grafia(df, "PROVINCIA", "PROVINCIA_KEY")
    print(f"Cantones únicos: {df['CANTON_KEY'].nunique()}")

    resumen = df["CAMPO_AMPLIO_NORMALIZADO"].value_counts()
    print("\nDistribución por campo amplio normalizado:")
    print(resumen.to_string())

    print(f"\nRegistros de pregrado (excluye posgrado): {df['ES_PREGRADO'].sum()} / {len(df)}")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")
    print(f"\nGuardado: {OUT_CSV}")

    with sqlite3.connect(OUT_DB) as con:
        df.to_sql("oferta", con, if_exists="replace", index=False)
    print(f"Guardado: {OUT_DB} (tabla 'oferta')")


if __name__ == "__main__":
    main()
