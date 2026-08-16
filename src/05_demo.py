"""
Demo de extremo a extremo: corre todo el pipeline (limpieza -> coordenadas ->
mapeo RIASEC -> motor de recomendación) y prueba el motor con 2 perfiles de
estudiante distintos, para verificar que el pipeline funciona.

Ejecutar desde la raíz del proyecto:
    python src/05_demo.py
"""
import importlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

limpiar = importlib.import_module("01_limpiar_oferta")
cantones = importlib.import_module("02_cantones_coordenadas")
mapeo = importlib.import_module("03_mapeo_riasec")
motor_mod = importlib.import_module("04_motor_recomendacion")


def correr_pipeline():
    print("=" * 70)
    print("PASO 1/3 - Limpieza de la oferta académica")
    print("=" * 70)
    limpiar.main()

    print("\n" + "=" * 70)
    print("PASO 2/3 - Coordenadas de cantones")
    print("=" * 70)
    cantones.main()

    print("\n" + "=" * 70)
    print("PASO 3/3 - Mapeo RIASEC -> campo amplio")
    print("=" * 70)
    mapeo.main()


def mostrar(titulo, df):
    print(f"\n--- {titulo} ---")
    if df.empty:
        print("(sin resultados: revisa los filtros, quizá son demasiado estrictos)")
        return
    with __import__("pandas").option_context("display.max_colwidth", 45, "display.width", 160):
        print(df.to_string(index=False))


def main():
    correr_pipeline()

    motor = motor_mod.MotorRecomendacion.desde_csv()

    print("\n" + "=" * 70)
    print("PRUEBA 1 - Perfil Investigativo/Realista, indiferente a ubicación,")
    print("           solo modalidad presencial, en Quito, sin importar cercanía")
    print("=" * 70)
    perfil_1 = {"R": 0.8, "I": 0.9, "A": 0.1, "S": 0.1, "E": 0.1, "C": 0.2}
    prefs_1 = motor_mod.Preferencias(
        modalidad="PRESENCIAL",
        peso_cercania=0.0,
        top_n=10,
    )
    resultado_1 = motor.buscar(perfil_1, prefs_1)
    mostrar("Top 10 recomendaciones (perfil Investigativo/Realista)", resultado_1)

    print("\n" + "=" * 70)
    print("PRUEBA 2 - Perfil Social/Artístico, estudiante en Loja, la cercanía")
    print("           importa mucho (peso 0.6), modalidad indiferente")
    print("=" * 70)
    perfil_2 = {"R": 0.0, "I": 0.1, "A": 0.7, "S": 0.9, "E": 0.2, "C": 0.1}
    prefs_2 = motor_mod.Preferencias(
        canton_estudiante="LOJA",
        peso_cercania=0.6,
        top_n=10,
    )
    resultado_2 = motor.buscar(perfil_2, prefs_2)
    mostrar("Top 10 recomendaciones (perfil Social/Artístico, prioriza cercanía a Loja)", resultado_2)

    print("\n" + "=" * 70)
    print("PRUEBA 3 - Exploración por clústeres vocacionales (KMeans, uso de")
    print("           navegación, no depende de un perfil puntual)")
    print("=" * 70)
    clusters = motor.explorar_clusters_vocacionales(n_clusters=10)
    resumen_clusters = (
        clusters.groupby("cluster_vocacional")["CAMPO_AMPLIO_NORMALIZADO"]
        .agg(lambda s: s.value_counts().idxmax())
        .rename("campo_amplio_dominante")
    )
    conteo = clusters["cluster_vocacional"].value_counts().rename("n_carreras")
    mostrar("Clústeres vocacionales encontrados", pd.concat([resumen_clusters, conteo], axis=1))


if __name__ == "__main__":
    main()
