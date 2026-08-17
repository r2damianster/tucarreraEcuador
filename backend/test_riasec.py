"""
Ítems del test vocacional RIASEC, traducidos al español a partir del
O*NET Interest Profiler Short Form (paper-and-pencil version, 2010), publicado
por el National Center for O*NET Development (US Dept. of Labor) bajo una
licencia que permite explícitamente redistribuir el instrumento y construir
nuevas evaluaciones a partir de él. Fuente original (inglés):
https://www.onetcenter.org/dl_files/IPSF_PP.pdf

60 actividades, 10 por cada una de las 6 dimensiones de Holland (RIASEC):
Realista, Investigativo, Artístico, Social, Emprendedor, Convencional.
El orden de presentación se intercala entre dimensiones (round robin) para
no revelar la categoría de cada actividad al estudiante mientras responde.
"""
from typing import Literal

Dimension = Literal["R", "I", "A", "S", "E", "C"]

NOMBRE_DIMENSION = {
    "R": "Realista",
    "I": "Investigativo",
    "A": "Artístico",
    "S": "Social",
    "E": "Emprendedor",
    "C": "Convencional",
}

DESCRIPCION_DIMENSION = {
    "R": "Te gusta trabajar con las manos, herramientas, máquinas o al aire libre.",
    "I": "Te gusta observar, investigar, analizar y resolver problemas complejos.",
    "A": "Te gusta crear, expresarte artísticamente y trabajar sin reglas fijas.",
    "S": "Te gusta ayudar, enseñar, cuidar o trabajar directamente con personas.",
    "E": "Te gusta liderar, persuadir, emprender y tomar decisiones de negocio.",
    "C": "Te gusta organizar datos, seguir procedimientos claros y trabajar con precisión.",
}

# (texto en español, dimensión)
_ITEMS_POR_DIMENSION: dict[Dimension, list[str]] = {
    "R": [
        "Construir gabinetes de cocina",
        "Colocar ladrillos o baldosas (cerámica)",
        "Reparar electrodomésticos",
        "Criar peces en una piscícola",
        "Ensamblar partes electrónicas",
        "Conducir un camión para entregar paquetes a oficinas y casas",
        "Revisar la calidad de piezas antes de enviarlas",
        "Reparar e instalar cerraduras",
        "Operar máquinas para fabricar productos",
        "Apagar incendios forestales",
    ],
    "I": [
        "Desarrollar un nuevo medicamento",
        "Estudiar formas de reducir la contaminación del agua",
        "Realizar experimentos químicos",
        "Estudiar el movimiento de los planetas",
        "Examinar muestras de sangre con un microscopio",
        "Investigar la causa de un incendio",
        "Desarrollar una forma de predecir mejor el clima",
        "Trabajar en un laboratorio de biología",
        "Inventar un sustituto del azúcar",
        "Hacer pruebas de laboratorio para identificar enfermedades",
    ],
    "A": [
        "Escribir libros u obras de teatro",
        "Tocar un instrumento musical",
        "Componer o arreglar música",
        "Dibujar",
        "Crear efectos especiales para películas",
        "Pintar escenografías para obras de teatro",
        "Escribir guiones para películas o programas de televisión",
        "Bailar jazz o tap",
        "Cantar en una banda",
        "Editar películas o videos",
    ],
    "S": [
        "Enseñarle una rutina de ejercicios a una persona",
        "Ayudar a personas con problemas personales o emocionales",
        "Dar orientación vocacional o de carrera a otras personas",
        "Realizar terapia de rehabilitación",
        "Hacer trabajo voluntario en una organización sin fines de lucro",
        "Enseñar deportes a niños",
        "Enseñar lengua de señas a personas sordas",
        "Ayudar a dirigir una sesión de terapia grupal",
        "Cuidar niños en una guardería",
        "Dar clases en un colegio",
    ],
    "E": [
        "Comprar y vender acciones en la bolsa de valores",
        "Administrar una tienda al por menor",
        "Manejar un salón de belleza o una barbería",
        "Dirigir un departamento dentro de una empresa grande",
        "Iniciar tu propio negocio",
        "Negociar contratos comerciales",
        "Representar a un cliente en un juicio",
        "Lanzar al mercado una nueva línea de ropa",
        "Vender mercadería en una tienda por departamentos",
        "Administrar una tienda de ropa",
    ],
    "C": [
        "Desarrollar una hoja de cálculo con un programa de computadora",
        "Corregir y revisar registros o formularios",
        "Instalar software en las computadoras de una red grande",
        "Operar una calculadora",
        "Llevar los registros de envíos y recepciones de mercadería",
        "Calcular el sueldo de los empleados",
        "Llevar el inventario de suministros con una computadora portátil",
        "Registrar pagos de arriendo",
        "Llevar el registro del inventario",
        "Sellar, clasificar y distribuir la correspondencia de una organización",
    ],
}


def generar_items() -> list[dict]:
    """Intercala las 6 dimensiones (round robin) y arma la lista final de
    60 ítems con id estable, texto y dimensión (la dimensión no se le
    muestra al estudiante en el frontend, solo se usa para calificar)."""
    orden_dimensiones: list[Dimension] = ["R", "I", "A", "S", "E", "C"]
    items = []
    for ronda in range(10):
        for dim in orden_dimensiones:
            texto = _ITEMS_POR_DIMENSION[dim][ronda]
            items.append({
                "id": f"{dim}{ronda + 1}",
                "texto": texto,
                "dimension": dim,
            })
    return items


ITEMS_RIASEC = generar_items()
