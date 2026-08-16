"""
Tabla de pesos RIASEC por campo amplio de conocimiento (las 10 categorías
canónicas producidas por 01_limpiar_oferta.py).

Esta tabla es el puente entre el test vocacional (que produce un puntaje de
0 a 1 en cada una de las 6 dimensiones de Holland: Realista, Investigativo,
Artístico, Social, Emprendedor, Convencional) y las carreras reales de la
base de oferta académica.

Es un insumo CURADO A MANO -- no viene en los datos abiertos de SENESCYT.
Los pesos no son excluyentes (una carrera puede aportar a más de una
dimensión) y quedan documentados aquí para que un orientador vocacional
los pueda revisar y ajustar antes de usarlos en producción.
"""
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_CSV = BASE_DIR / "data" / "processed" / "mapeo_riasec_campo_amplio.csv"

DIMENSIONES = ["R", "I", "A", "S", "E", "C"]

# campo amplio canónico -> pesos en [0, 1] por dimensión RIASEC
MAPEO = {
    "Educación": {"R": 0.0, "I": 0.1, "A": 0.2, "S": 1.0, "E": 0.1, "C": 0.1},
    "Artes y Humanidades": {"R": 0.0, "I": 0.1, "A": 1.0, "S": 0.3, "E": 0.1, "C": 0.0},
    "Ciencias Sociales, Periodismo e Información": {"R": 0.0, "I": 0.2, "A": 0.3, "S": 0.4, "E": 0.6, "C": 0.1},
    "Administración de Empresas y Derecho": {"R": 0.0, "I": 0.1, "A": 0.0, "S": 0.2, "E": 0.7, "C": 0.5},
    "Ciencias Naturales, Matemáticas y Estadística": {"R": 0.2, "I": 1.0, "A": 0.0, "S": 0.0, "E": 0.0, "C": 0.2},
    "Tecnologías de la Información y la Comunicación (TIC)": {"R": 0.3, "I": 0.4, "A": 0.1, "S": 0.0, "E": 0.2, "C": 0.6},
    "Ingeniería, Industria y Construcción": {"R": 0.8, "I": 0.3, "A": 0.1, "S": 0.0, "E": 0.1, "C": 0.1},
    "Agricultura, Silvicultura, Pesca y Veterinaria": {"R": 0.9, "I": 0.3, "A": 0.0, "S": 0.1, "E": 0.0, "C": 0.0},
    "Salud y Bienestar": {"R": 0.1, "I": 0.6, "A": 0.0, "S": 0.6, "E": 0.1, "C": 0.1},
    "Servicios": {"R": 0.5, "I": 0.1, "A": 0.1, "S": 0.5, "E": 0.3, "C": 0.3},
}


def main():
    df = pd.DataFrame.from_dict(MAPEO, orient="index")[DIMENSIONES]
    df.index.name = "campo_amplio_normalizado"
    df = df.reset_index()
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")
    print(f"Guardado: {OUT_CSV}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
