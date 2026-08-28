# -*- coding: utf-8 -*-
"""Genera los diagramas del deck de Slidev como SVG, con datos reales del motor.

Todos los números salen de:
  - data/processed/oferta_limpia.csv (8014 filas)
  - data/processed/mapeo_riasec_campo_amplio.csv
  - data/processed/cantones_coordenadas.csv
  - src/04_motor_recomendacion.py (vectores, similitudes, clústeres)
y están anotados como comentario en cada bloque.

Uso:  python gen_diagramas.py <directorio_destino>
"""
import io
import math
import os
import random

ANCHO, ALTO = 900, 430

INK, SOFT, MUTED = "#1f2933", "#52606d", "#7b8794"
BORDER, PANEL = "#d9e2ec", "#f5f7fa"
BLUE, DEEP, NAVY = "#2a78d6", "#1c5cab", "#0d366b"
ORANGE, AQUA = "#eb6834", "#1baf7a"

CABECERA = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 430" role="img" aria-label="__ALT__">
<style>
  text { font-family: 'Segoe UI', Inter, Helvetica, Arial, sans-serif; }
  .titulo   { font-size: 19px; font-weight: 600; fill: #1f2933; }
  .etiqueta { font-size: 14px; fill: #52606d; }
  .dato     { font-size: 15px; font-weight: 600; fill: #1f2933; }
  .pie      { font-size: 12px; fill: #7b8794; }
  .codigo   { font-family: Consolas, 'Cascadia Mono', monospace; font-size: 13px; fill: #1c5cab; }
</style>
<rect width="900" height="430" fill="#ffffff"/>
<defs>
  <marker id="flecha" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="#52606d"/>
  </marker>
  <marker id="flecha-azul" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="#2a78d6"/>
  </marker>
  <marker id="flecha-naranja" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="#eb6834"/>
  </marker>
</defs>
"""


def escapar(contenido):
    return str(contenido).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def guardar(nombre, alt, cuerpo, destino):
    contenido = CABECERA.replace("__ALT__", escapar(alt)) + cuerpo + "\n</svg>\n"
    ruta = os.path.join(destino, nombre)
    io.open(ruta, "w", encoding="utf-8", newline="\n").write(contenido)
    print("escrito", nombre, len(contenido), "bytes")


def texto(x, y, contenido, clase="etiqueta", anchor="start", estilo=""):
    atributo_estilo = f' style="{estilo}"' if estilo else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" class="{clase}" text-anchor="{anchor}"{atributo_estilo}>'
            f'{escapar(contenido)}</text>')


def caja(x, y, ancho, alto, relleno=PANEL, borde=BORDER, radio=10):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{ancho:.1f}" height="{alto:.1f}" '
            f'rx="{radio}" fill="{relleno}" stroke="{borde}"/>')


def barra(x, y, ancho, alto, valor, color, fondo=PANEL):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{ancho:.1f}" height="{alto}" rx="{alto / 2:.1f}" '
            f'fill="{fondo}" stroke="{BORDER}"/>\n'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{ancho * valor:.1f}" height="{alto}" '
            f'rx="{alto / 2:.1f}" fill="{color}"/>')


DIMENSIONES = [
    ("R", "Realista", "manos, máquinas"),
    ("I", "Investigativo", "analizar, resolver"),
    ("A", "Artístico", "crear, expresar"),
    ("S", "Social", "ayudar, enseñar"),
    ("E", "Emprendedor", "liderar, negociar"),
    ("C", "Convencional", "ordenar, procesar"),
]

# Perfil de ejemplo, el mismo en toda la serie de diagramas.
PERFIL = {"R": 0.2, "I": 0.8, "A": 0.3, "S": 0.6, "E": 0.2, "C": 0.3}


# ------------------------------------------------------------------ 1. RIASEC
def diagrama_riasec(destino):
    centro_x, centro_y, radio = 250, 246, 102
    # (anchor, dx, dy_nombre, dy_glosa) por dimensión, en el orden de DIMENSIONES
    colocacion = [
        ("middle", 0, -46, -30),   # R arriba
        ("start", 34, -2, 16),     # I derecha-arriba
        ("start", 34, -2, 16),     # A derecha-abajo
        ("middle", 0, 48, 65),     # S abajo
        ("end", -34, -2, 16),      # E izquierda-abajo
        ("end", -34, -2, 16),      # C izquierda-arriba
    ]

    partes = [
        texto(40, 46, "Las 6 dimensiones de Holland", "titulo"),
        texto(40, 68, "Adyacentes = intereses afines · opuestas = antagónicas", "pie"),
    ]

    vertices = {}
    for indice, (letra, _, _) in enumerate(DIMENSIONES):
        angulo = math.radians(-90 + indice * 60)
        vertices[letra] = (centro_x + radio * math.cos(angulo), centro_y + radio * math.sin(angulo))

    poligono = " ".join(f"{vertices[d[0]][0]:.1f},{vertices[d[0]][1]:.1f}" for d in DIMENSIONES)
    partes.append(f'<polygon points="{poligono}" fill="none" stroke="{BORDER}" stroke-width="2"/>')

    letras = [d[0] for d in DIMENSIONES]
    for i in range(6):
        for j in range(i + 2, 6):
            if i == 0 and j == 5:
                continue
            x1, y1 = vertices[letras[i]]
            x2, y2 = vertices[letras[j]]
            partes.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                          f'stroke="{BORDER}" stroke-width="1" opacity="0.7"/>')

    for indice, (letra, nombre, glosa) in enumerate(DIMENSIONES):
        x, y = vertices[letra]
        anchor, dx, dy_nombre, dy_glosa = colocacion[indice]
        partes.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="24" fill="{BLUE}"/>')
        partes.append(f'<text x="{x:.1f}" y="{y + 7:.1f}" text-anchor="middle" '
                      f'style="font-size:19px;font-weight:700;fill:#ffffff">{letra}</text>')
        partes.append(texto(x + dx, y + dy_nombre, nombre, "dato", anchor))
        partes.append(texto(x + dx, y + dy_glosa, glosa, "pie", anchor))

    panel_x, panel_y = 570, 108
    partes.append(caja(panel_x - 28, panel_y - 58, 318, 250))
    partes.append(texto(panel_x - 8, panel_y - 30, "Un perfil = 6 números", "titulo"))
    partes.append(texto(panel_x - 8, panel_y - 10, "60 ítems sí/no · 10 por dimensión", "pie"))
    for indice, (letra, _, _) in enumerate(DIMENSIONES):
        valor = PERFIL[letra]
        y = panel_y + 24 + indice * 26
        partes.append(texto(panel_x - 8, y + 5, letra, "dato"))
        partes.append(barra(panel_x + 14, y - 7, 190, 14, valor, BLUE, "#ffffff"))
        partes.append(texto(panel_x + 218, y + 5, f"{valor:.1f}", "dato"))
    partes.append(texto(panel_x - 8, panel_y + 208, "Ese vector es la entrada del motor.", "pie"))

    guardar("riasec-hexagono.svg",
            "Hexágono RIASEC de Holland y el perfil del estudiante como vector de seis dimensiones",
            "\n".join(partes), destino)


# ------------------------------------------------------------- 2. filtro duro
def diagrama_filtro(destino):
    # Cascada real sobre data/processed/oferta_limpia.csv.
    etapas = [
        ("Oferta vigente completa", 8014, "df"),
        ("Solo pregrado", 5142, "df[df['ES_PREGRADO']]"),
        ("Modalidad presencial", 3038, "df[df['MODALIDAD'] == 'PRESENCIAL']"),
        ("Financiamiento público", 1340, "df[df['TIPO_FINANCIAMIENTO'] == 'PÚBLICA']"),
        ("Universidad, no instituto", 939, "df[df['TIPO_IES'] == 'UNIVERSIDAD']"),
    ]
    partes = [
        texto(40, 46, "El filtro duro recorta antes de que corra un solo algoritmo", "titulo"),
        texto(40, 68, "Álgebra de conjuntos sobre un DataFrame · máscaras booleanas encadenadas con &",
              "pie"),
    ]
    ancho_max = 372
    for indice, (rotulo, cantidad, codigo) in enumerate(etapas):
        y = 104 + indice * 58
        ancho = ancho_max * cantidad / etapas[0][1]
        color = NAVY if indice == 0 else BLUE
        partes.append(texto(40, y + 2, rotulo, "dato"))
        partes.append(texto(40, y + 21, codigo, "codigo"))
        partes.append(f'<rect x="470" y="{y - 14:.1f}" width="{ancho_max}" height="26" rx="6" '
                      f'fill="{PANEL}" stroke="{BORDER}"/>')
        partes.append(f'<rect x="470" y="{y - 14:.1f}" width="{ancho:.1f}" height="26" rx="6" '
                      f'fill="{color}"/>')
        dentro = ancho > 76
        partes.append(texto(470 + ancho + (-10 if dentro else 10), y + 5, f"{cantidad}", "dato",
                            "end" if dentro else "start",
                            "fill:#ffffff" if dentro else ""))
        if indice < len(etapas) - 1:
            partes.append(f'<line x1="656" y1="{y + 14:.1f}" x2="656" y2="{y + 38:.1f}" '
                          f'stroke="{MUTED}" stroke-width="1.5" marker-end="url(#flecha)"/>')

    partes.append(caja(40, 376, 820, 40, "#ffffff"))
    partes.append(texto(58, 401,
                        "No es machine learning: es el recorte que deja al motor trabajar solo sobre "
                        "lo que el estudiante sí puede estudiar.",
                        "etiqueta"))
    guardar("filtrado-pandas.svg",
            "Cascada del filtro duro: de 8014 carreras a 939 tras cuatro máscaras booleanas",
            "\n".join(partes), destino)


# --------------------------------------------------------- 3. TF-IDF + campo
def diagrama_tfidf(destino):
    # Valores reales del motor para dos carreras del mismo campo amplio
    # ("Ciencias Sociales, Periodismo e Información").
    campo = {"R": 0.0, "I": 0.125, "A": 0.188, "S": 0.25, "E": 0.375, "C": 0.062}
    casos = [
        ("Marketing", "E", 0.228, 0.469),
        ("Contabilidad y Auditoría", "C", 0.392, 0.203),
    ]
    letras = [d[0] for d in DIMENSIONES]
    columna_x, ancho_celda = 322, 52

    partes = [
        texto(40, 46, "El nombre de la carrera desempata dentro del mismo campo amplio", "titulo"),
        texto(40, 68, "Campo amplio «Ciencias Sociales, Periodismo e Información» · "
                      "338 carreras compartían este vector", "pie"),
    ]

    def fila_vector(x, y, vector, color):
        salida = []
        for indice, letra in enumerate(letras):
            valor = vector.get(letra, 0.0)
            celda_x = x + indice * ancho_celda
            intensidad = min(valor / 0.5, 1.0)
            salida.append(f'<rect x="{celda_x:.1f}" y="{y:.1f}" width="{ancho_celda - 4}" height="30" '
                          f'rx="5" fill="{color}" fill-opacity="{0.12 + 0.78 * intensidad:.2f}"/>')
            relleno = "#ffffff" if intensidad > 0.55 else INK
            salida.append(f'<text x="{celda_x + (ancho_celda - 4) / 2:.1f}" y="{y + 20:.1f}" '
                          f'text-anchor="middle" '
                          f'style="font-size:13px;font-weight:600;fill:{relleno}">{valor:.2f}</text>')
        return salida

    for indice, letra in enumerate(letras):
        partes.append(texto(columna_x + indice * ancho_celda + 24, 106, letra, "dato", "middle"))

    partes.append(texto(40, 130, "Vector del campo amplio", "dato"))
    partes.append(texto(40, 148, "idéntico para las 338 carreras", "pie"))
    partes.extend(fila_vector(columna_x, 112, campo, BLUE))
    partes.append(texto(646, 130, "85%", "dato"))
    partes.append(texto(646, 148, "del vector final", "pie"))

    for fila, (nombre, dimension, senal, final) in enumerate(casos):
        y = 192 + fila * 100
        partes.append(texto(40, y + 20, nombre, "dato"))
        partes.append(texto(40, y + 38, f"señal TF-IDF en {dimension} = {senal:.3f}", "pie"))
        partes.extend(fila_vector(columna_x, y + 4, {dimension: senal}, ORANGE))
        partes.append(texto(646, y + 22, "15%", "dato"))
        partes.append(texto(646, y + 40, "señal de texto", "pie"))
        partes.append(f'<line x1="706" y1="{y + 18:.1f}" x2="738" y2="{y + 18:.1f}" stroke="{MUTED}" '
                      f'stroke-width="1.5" marker-end="url(#flecha)"/>')
        partes.append(texto(750, y + 12, "vector final", "pie"))
        partes.append(texto(750, y + 34, f"{dimension} = {final:.3f}", "dato"))

    partes.append(caja(40, 372, 820, 42, "#ffffff"))
    partes.append(texto(58, 398,
                        "Mismo campo, distinto vector: Marketing carga en E (0.469) y Contabilidad "
                        "en C (0.203). Antes empataban en 99.5%.", "etiqueta"))
    guardar("tfidf-campo-amplio.svg",
            "Vector de carrera: 85% del campo amplio más 15% de señal TF-IDF sobre el nombre",
            "\n".join(partes), destino)


# ------------------------------------------------------------- 4. coseno / NN
def diagrama_coseno(destino):
    # Similitudes coseno reales contra el perfil PERFIL.
    carreras = [
        ("Medicina", 0.936),
        ("Contabilidad y Auditoría", 0.724),
        ("Marketing", 0.597),
        ("Ingeniería Mecánica", 0.428),
    ]
    origen_x, origen_y, largo = 210, 358, 236
    angulo_perfil = 78.0

    partes = [
        texto(40, 46, "La afinidad es el ángulo entre dos vectores", "titulo"),
        texto(40, 68, "NearestNeighbors con métrica coseno · no cuenta la magnitud, solo la dirección",
              "pie"),
        f'<line x1="{origen_x}" y1="{origen_y}" x2="{origen_x + 300}" y2="{origen_y}" '
        f'stroke="{BORDER}" stroke-width="1.5"/>',
        f'<line x1="{origen_x}" y1="{origen_y}" x2="{origen_x}" y2="{origen_y - 262}" '
        f'stroke="{BORDER}" stroke-width="1.5"/>',
    ]

    def punta(angulo_grados, longitud):
        rad = math.radians(angulo_grados)
        return origen_x + longitud * math.cos(rad), origen_y - longitud * math.sin(rad)

    fin_x, fin_y = punta(angulo_perfil, largo)
    partes.append(f'<line x1="{origen_x}" y1="{origen_y}" x2="{fin_x:.1f}" y2="{fin_y:.1f}" '
                  f'stroke="{BLUE}" stroke-width="3" marker-end="url(#flecha-azul)"/>')
    partes.append(texto(fin_x - 10, fin_y - 16, "perfil del estudiante", "dato", "middle",
                        f"fill:{DEEP}"))

    for indice, (nombre, similitud) in enumerate(carreras):
        angulo = angulo_perfil - math.degrees(math.acos(similitud))
        fin_x, fin_y = punta(angulo, largo - 26)
        partes.append(f'<line x1="{origen_x}" y1="{origen_y}" x2="{fin_x:.1f}" y2="{fin_y:.1f}" '
                      f'stroke="{ORANGE}" stroke-width="2" opacity="{1 - indice * 0.16:.2f}" '
                      f'marker-end="url(#flecha-naranja)"/>')
        partes.append(texto(fin_x + 10, fin_y - 2, nombre, "pie"))

    rad_perfil = math.radians(angulo_perfil)
    rad_ultimo = math.radians(angulo_perfil - math.degrees(math.acos(carreras[-1][1])))
    radio_arco = 76
    ax, ay = origen_x + radio_arco * math.cos(rad_perfil), origen_y - radio_arco * math.sin(rad_perfil)
    bx, by = origen_x + radio_arco * math.cos(rad_ultimo), origen_y - radio_arco * math.sin(rad_ultimo)
    partes.append(f'<path d="M {ax:.1f} {ay:.1f} A {radio_arco} {radio_arco} 0 0 1 {bx:.1f} {by:.1f}" '
                  f'fill="none" stroke="{MUTED}" stroke-width="1.5" stroke-dasharray="4 3"/>')
    partes.append(texto(origen_x + 74, origen_y - 66, "θ", "dato"))

    panel_x = 560
    partes.append(caja(panel_x, 96, 300, 296, "#ffffff"))
    partes.append(texto(panel_x + 20, 126, "cos θ = afinidad", "titulo"))
    partes.append(texto(panel_x + 20, 148, "θ chico → cos θ → 1 → perfiles parecidos", "pie"))
    for indice, (nombre, similitud) in enumerate(carreras):
        y = 190 + indice * 46
        partes.append(texto(panel_x + 20, y, nombre, "etiqueta"))
        partes.append(barra(panel_x + 20, y + 8, 190, 16, similitud, ORANGE))
        partes.append(texto(panel_x + 280, y + 21, f"{similitud:.3f}", "dato", "end"))
    partes.append(texto(panel_x + 20, 374, "El pool vuelve completo y ordenado, sin top-k.", "pie"))

    guardar("similitud-coseno.svg",
            "Similitud coseno entre el perfil del estudiante y cuatro carreras, con valores reales",
            "\n".join(partes), destino)


# --------------------------------------------------------------- 5. haversine
def diagrama_haversine(destino):
    # Coordenadas reales (cantones_coordenadas.csv), distancias con haversine_km()
    # y scores de cercanía de una búsqueda real desde MANTA.
    cantones = {
        "Quito": (-0.2155, -78.5014),
        "Portoviejo": (-1.0528, -80.4534),
        "Manta": (-1.0322, -80.8222),
        "Guayaquil": (-2.1899, -79.8877),
    }
    distancias = [("Portoviejo", 41), ("Guayaquil", 165), ("Quito", 274)]
    cercania = [("Manta", 1.000), ("Portoviejo", 0.961), ("Guayaquil", 0.844), ("Quito", 0.742)]

    lon_min, lon_max = -81.5, -78.0
    lat_min, lat_max = -2.6, 0.2
    marco_x, marco_y, marco_w, marco_h = 56, 96, 372, 292

    def proyectar(lat, lon):
        x = marco_x + (lon - lon_min) / (lon_max - lon_min) * marco_w
        y = marco_y + (lat_max - lat) / (lat_max - lat_min) * marco_h
        return x, y

    partes = [
        texto(40, 46, "Haversine: distancia real entre el cantón del estudiante y el de la sede",
              "titulo"),
        texto(40, 68, "Coordenadas por cantón · radio terrestre 6371 km · el arco, no la línea recta",
              "pie"),
        caja(marco_x, marco_y, marco_w, marco_h, "#fbfcfd"),
    ]
    for grado in range(-81, -77):
        x, _ = proyectar(0, grado)
        if marco_x < x < marco_x + marco_w:
            partes.append(f'<line x1="{x:.1f}" y1="{marco_y}" x2="{x:.1f}" y2="{marco_y + marco_h}" '
                          f'stroke="{BORDER}" stroke-width="1" opacity="0.7"/>')
            partes.append(texto(x, marco_y + marco_h + 16, f"{grado}°", "pie", "middle"))
    for grado in range(-2, 1):
        _, y = proyectar(grado, -80)
        if marco_y < y < marco_y + marco_h:
            partes.append(f'<line x1="{marco_x}" y1="{y:.1f}" x2="{marco_x + marco_w}" y2="{y:.1f}" '
                          f'stroke="{BORDER}" stroke-width="1" opacity="0.7"/>')
            partes.append(texto(marco_x - 8, y + 4, f"{grado}°", "pie", "end"))

    manta_x, manta_y = proyectar(*cantones["Manta"])
    for nombre, kilometros in distancias:
        destino_x, destino_y = proyectar(*cantones[nombre])
        curvatura = {"Portoviejo": 0.16, "Guayaquil": -0.16}.get(nombre, 0.12)
        medio_x = (manta_x + destino_x) / 2 + (destino_y - manta_y) * curvatura
        medio_y = (manta_y + destino_y) / 2 - (destino_x - manta_x) * curvatura
        partes.append(f'<path d="M {manta_x:.1f} {manta_y:.1f} Q {medio_x:.1f} {medio_y:.1f} '
                      f'{destino_x:.1f} {destino_y:.1f}" fill="none" stroke="{BLUE}" stroke-width="2" '
                      f'stroke-dasharray="5 4" opacity="0.85"/>')
        etiqueta_y = medio_y - 22 if nombre == "Portoviejo" else medio_y
        partes.append(f'<rect x="{medio_x - 31:.1f}" y="{etiqueta_y - 12:.1f}" width="62" height="21" '
                      f'rx="10" fill="#ffffff" stroke="{BORDER}"/>')
        partes.append(texto(medio_x, etiqueta_y + 3, f"{kilometros} km", "pie", "middle"))

    for nombre, (lat, lon) in cantones.items():
        x, y = proyectar(lat, lon)
        es_origen = nombre == "Manta"
        partes.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{8 if es_origen else 6}" '
                      f'fill="{NAVY if es_origen else BLUE}" stroke="#ffffff" stroke-width="2"/>')
        if es_origen:
            partes.append(texto(x - 13, y + 2, nombre, "dato", "end"))
            partes.append(texto(x - 13, y + 19, "tu cantón", "pie", "end"))
        else:
            partes.append(texto(x + 12, y + 5, nombre, "dato"))

    partes.append(caja(462, 96, 398, 132, "#ffffff"))
    partes.append(texto(482, 124, "De kilómetros a score", "titulo"))
    partes.append(texto(482, 148, "MinMaxScaler invierte y escala la distancia a [0, 1],", "etiqueta"))
    partes.append(texto(482, 168, "para que sea comparable con la afinidad RIASEC.", "etiqueta"))
    partes.append(texto(482, 196, "0 km → cercanía 1.00", "dato"))
    partes.append(texto(482, 214, "la sede más lejana del pool → cercanía 0.00", "pie"))

    partes.append(caja(462, 244, 398, 148, PANEL))
    partes.append(texto(482, 272, "Cercanía de las sedes desde Manta", "titulo"))
    for indice, (nombre, valor) in enumerate(cercania):
        y = 300 + indice * 24
        partes.append(texto(482, y + 4, nombre, "etiqueta"))
        partes.append(barra(614, y - 7, 160, 12, valor, BLUE, "#ffffff"))
        partes.append(texto(840, y + 4, f"{valor:.2f}", "dato", "end"))
    guardar("haversine.svg",
            "Distancias reales desde Manta a Portoviejo, Guayaquil y Quito, y su score de cercanía",
            "\n".join(partes), destino)


# ------------------------------------------------------- 6. score final + dedup
def diagrama_score(destino):
    # Filas reales de buscar() con peso_cercania = 0.3 y cantón MANTA.
    filas = [
        ("Laboratorio Clínico", "ULEAM · Manta", 0.937, 1.000, 0.956, "sede en el mismo cantón"),
        ("Laboratorio Clínico", "U. Central · Quito", 0.937, 0.742, 0.879, "misma afinidad, 274 km"),
    ]
    partes = [
        texto(40, 46, "Un solo score decide el orden", "titulo"),
        texto(40, 68, "El estudiante mueve el peso de la cercanía con un slider; acá vale 0.3", "pie"),
        caja(40, 92, 820, 52, PANEL),
        texto(60, 124, "score_final = (1 − 0.3) × similitud_riasec + 0.3 × score_cercanía",
              "codigo", "start", "font-size:16px"),
    ]

    partes.append(texto(40, 178, "Misma carrera, dos sedes", "dato"))
    for rotulo, x in (("afinidad RIASEC", 470), ("cercanía", 618), ("score final", 768)):
        partes.append(texto(x, 178, rotulo, "pie", "middle"))
    for indice, (carrera, sede, riasec, cerca, final, nota) in enumerate(filas):
        y = 200 + indice * 62
        partes.append(caja(40, y, 820, 50, "#ffffff", BORDER, 8))
        partes.append(texto(60, y + 22, carrera, "dato"))
        partes.append(texto(60, y + 40, sede, "pie"))
        for valor, x, color in ((riasec, 470, BLUE), (cerca, 618, ORANGE)):
            partes.append(barra(x - 58, y + 28, 116, 10, valor, color))
            partes.append(texto(x, y + 20, f"{valor:.3f}", "dato", "middle"))
        partes.append(texto(768, y + 22, f"{final:.3f}", "dato", "middle",
                            f"font-size:21px;fill:{NAVY}"))
        partes.append(texto(768, y + 41, nota, "pie", "middle"))

    partes.append(caja(40, 336, 400, 78, PANEL))
    partes.append(texto(60, 364, "Deduplicación", "dato"))
    partes.append(texto(60, 386, "drop_duplicates sobre (carrera, IES):", "etiqueta"))
    partes.append(texto(60, 404, "una carrera no se repite por sede duplicada.", "pie"))

    partes.append(caja(460, 336, 400, 78, PANEL))
    partes.append(texto(480, 364, "Sin tope", "dato"))
    partes.append(texto(480, 386, "buscar() devuelve las 2464 del pool filtrado;", "etiqueta"))
    partes.append(texto(480, 404, "el frontend decide cuántas mostrar.", "pie"))
    guardar("score-deduplicacion.svg",
            "Score final combinando afinidad RIASEC y cercanía, con deduplicación y ranking sin tope",
            "\n".join(partes), destino)


# ----------------------------------------------------------------- 7. clusters
def diagrama_kmeans(destino):
    # Clústeres reales de explorar_clusters_vocacionales(n_clusters=10);
    # se dibujan 3 de los 10 para que el gráfico siga siendo legible.
    grupos = [
        ("Administración y Derecho", 338, "Administración de Empresas · Gerencia Empresarial",
         BLUE, (300, 170)),
        ("Salud y Bienestar", 197, "Odontología · Terapia de Lenguaje", ORANGE, (398, 300)),
        ("Ingeniería e Industria", 225, "Ingeniería Hidráulica · Mecánica Automotriz",
         AQUA, (160, 300)),
    ]
    aleatorio = random.Random(42)
    partes = [
        texto(40, 46, "KMeans agrupa carreras en familias vocacionales", "titulo"),
        texto(40, 68, "El motor corre con n_clusters = 10 sobre el espacio RIASEC; acá se dibujan 3, "
                      "proyectados a 2D", "pie"),
        caja(48, 92, 464, 300, "#fbfcfd"),
        texto(58, 382, "PC 1", "pie"),
        '<text x="34" y="242" class="pie" text-anchor="middle" transform="rotate(-90 34 242)">PC 2</text>',
    ]

    for nombre, _, _, color, (centro_x, centro_y) in grupos:
        for _ in range(32):
            angulo = aleatorio.uniform(0, 2 * math.pi)
            radio = abs(aleatorio.gauss(0, 1)) * 24
            x = min(max(centro_x + radio * math.cos(angulo), 64), 496)
            y = min(max(centro_y + radio * math.sin(angulo) * 0.78, 128), 372)
            partes.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{color}" '
                          f'fill-opacity="0.5"/>')
        partes.append(f'<path d="M {centro_x - 9} {centro_y - 9} L {centro_x + 9} {centro_y + 9} '
                      f'M {centro_x - 9} {centro_y + 9} L {centro_x + 9} {centro_y - 9}" '
                      f'stroke="{color}" stroke-width="3.5" stroke-linecap="round"/>')
        etiqueta_corta = nombre.split(" y ")[0].split(" e ")[0]
        partes.append(texto(centro_x, centro_y - 44, etiqueta_corta, "dato", "middle",
                            f"font-size:13px;fill:{INK}"))

    for indice, (nombre, cantidad, ejemplos, color, _) in enumerate(grupos):
        y = 126 + indice * 78
        partes.append(f'<circle cx="552" cy="{y - 5}" r="7" fill="{color}"/>')
        partes.append(texto(572, y, nombre, "dato"))
        partes.append(texto(572, y + 19, f"{cantidad} carreras únicas", "etiqueta"))
        partes.append(texto(572, y + 37, ejemplos, "pie"))

    partes.append(caja(532, 348, 328, 58, PANEL))
    partes.append(texto(552, 374, "Para explorar, no para recomendar", "dato"))
    partes.append(texto(552, 394, "KMeans no entra en el score_final.", "pie"))
    guardar("kmeans-pca.svg",
            "Clústeres vocacionales de KMeans proyectados a dos dimensiones, con tres familias reales",
            "\n".join(partes), destino)


if __name__ == "__main__":
    import sys
    carpeta = sys.argv[1] if len(sys.argv) > 1 else "."
    diagrama_riasec(carpeta)
    diagrama_filtro(carpeta)
    diagrama_tfidf(carpeta)
    diagrama_coseno(carpeta)
    diagrama_haversine(carpeta)
    diagrama_score(carpeta)
    diagrama_kmeans(carpeta)
