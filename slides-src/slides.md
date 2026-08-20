---
theme: default
title: Recomendador de Carreras Ecuador
info: |
  ## Recomendador de Carreras Universitarias del Ecuador
  Test RIASEC (Holland) + scikit-learn sobre la oferta académica de las IES del Ecuador (SENESCYT).

  Programación para Inteligencia Artificial.
class: text-center
highlighter: shiki
drawings:
  persist: false
transition: slide-left
mdc: true
---

# Recomendador de Carreras Universitarias del Ecuador

Orientación vocacional con Machine Learning sobre datos abiertos de Ecuador

<br>

**Arturo Rodríguez, PhD** · ULEAM
Programación para Inteligencia Artificial

<div class="pt-8 text-sm opacity-60">
tucarrera-ecuador.vercel.app
</div>

---

# El problema

- Cada año, miles de bachilleres ecuatorianos eligen carrera **sin un mapa claro** de qué
  oferta académica existe y dónde.
- La oferta de las IES del Ecuador (universidades + institutos) está publicada por
  SENESCYT como **datos abiertos**, pero como una tabla plana — no hay forma de cruzarla
  con los intereses reales del estudiante.
- La orientación vocacional formal (RIASEC / modelo de Holland) existe hace décadas, pero
  rara vez se conecta con datos reales de oferta académica local.

<br>

## La propuesta

Cruzar un **test de intereses vocacionales (RIASEC)** con la oferta académica real del
Ecuador, usando **scikit-learn**, para recomendar carreras y universidades afines.

---
layout: two-cols
---

# Arquitectura del sistema

<div class="pr-4">

**[1] Pipeline de datos** (offline)
Excel SENESCYT → limpieza → mapeo RIASEC → coordenadas

**[2] Motor de recomendación**
`src/04_motor_recomendacion.py`
filtro + TF-IDF + `NearestNeighbors` + Haversine + `KMeans`

**[3] API REST**
FastAPI (`backend/main.py`), 6 endpoints

**[4] Frontend**
Vanilla JS: test → perfil → resultados

</div>

::right::

```mermaid
flowchart TD
    A[Excel SENESCYT] --> B[Limpieza / pandas]
    B --> C[(oferta_limpia.csv)]
    C --> D[Motor de recomendación]
    E[Test RIASEC] --> D
    D --> F[API FastAPI]
    F --> G[Frontend web]
```

---

# Los datos

Fuente: **SENESCYT**, Portal Único de Datos Abiertos del Ecuador (5 de febrero de 2025).

<div grid="~ cols-3 gap-4" class="pt-4">
<div class="p-4 rounded bg-blue-500/10">

### 8014
carreras vigentes (oferta académica)

</div>
<div class="p-4 rounded bg-blue-500/10">

### 99
cantones con coordenadas geográficas

</div>
<div class="p-4 rounded bg-blue-500/10">

### 10
campos amplios, con pesos RIASEC curados a mano

</div>
</div>

<br>

Coordenadas de cantones: gist comunitario, con 2 correcciones manuales verificadas
(pendiente migrar a fuente oficial INEC/IGM).

---

# El test vocacional: RIASEC (Holland)

Instrumento: **O*NET Interest Profiler Short Form** (National Center for O*NET
Development, 2010, US Dept. of Labor) — licencia abierta, traducido al español.

**60 actividades**, 10 por cada una de las 6 dimensiones, presentadas intercaladas para no
revelar la categoría de cada una:

| | Dimensión | Le gusta... |
|---|---|---|
| **R** | Realista | trabajar con las manos, herramientas, máquinas |
| **I** | Investigativo | observar, investigar, analizar, resolver problemas |
| **A** | Artístico | crear, expresarse, trabajar sin reglas fijas |
| **S** | Social | ayudar, enseñar, cuidar, trabajar con personas |
| **E** | Emprendedor | liderar, persuadir, emprender, negociar |
| **C** | Convencional | organizar datos, seguir procedimientos, precisión |

$$\text{puntaje}_d = \frac{\text{respuestas "sí" en los 10 ítems de la dimensión } d}{10}$$

---

# Motor — paso 1: filtro duro

`MotorRecomendacion._filtrar_duro()` — `src/04_motor_recomendacion.py`

Antes de calcular ninguna similitud, se descartan con **filtros booleanos de pandas** las
ofertas que no cumplen una preferencia obligatoria del estudiante:

- Modalidad (presencial / a distancia / en línea / híbrida)
- Tipo de financiamiento (pública / particular)
- Tipo de IES (universidad / instituto)
- Nivel de formación (por defecto excluye posgrado)

No es machine learning — es álgebra de conjuntos sobre un `DataFrame`. Pero reduce el
espacio de búsqueda **antes** de que el resto de los algoritmos trabajen.

---

# Motor — paso 2: vector RIASEC por carrera

`_vector_texto_por_carrera()` — mezcla **85% campo amplio + 15% TF-IDF**

<v-clicks>

- Cada carrera hereda el vector RIASEC de su `CAMPO_AMPLIO_NORMALIZADO` (10 categorías)
  — pero eso da solo **10 vectores posibles para 8014 carreras**.
- Antes: las **338 carreras** de "Administración de Empresas y Derecho" empataban todas
  en **99.5% de afinidad**, sin diferenciarse entre sí.
- Solución: **TF-IDF** sobre `NOMBRE_CARRERA` + similitud coseno contra palabras clave
  curadas por dimensión (`PALABRAS_CLAVE_DIMENSION`, teoría de Holland).
- Mezcla final: **85% campo amplio (manda) + 15% señal de texto (desempata)**.

</v-clicks>

<div class="pt-4 text-sm opacity-70" v-click>

`"MARKETING"` → señal alta en **E** (Emprendedor) · `"CONTABILIDAD Y AUDITORIA"` → señal
alta en **C** (Convencional) — aunque comparten el mismo campo amplio.

</div>

---

# Motor — paso 3: búsqueda por similitud

`sklearn.neighbors.NearestNeighbors`, métrica coseno

Con cada carrera representada como un punto en un espacio de 6 dimensiones (R,I,A,S,E,C),
"¿qué carreras se parecen a mi perfil?" es un problema de **vecinos más cercanos**.

$$\text{distancia\_coseno}(u, v) = 1 - \frac{u \cdot v}{\|u\| \, \|v\|}$$

**Detalle clave:** se pide el ranking **completo** (`n_neighbors = todos los candidatos`),
no un top-k chico — porque el vector RIASEC viene mayormente del campo amplio (10
categorías), y truncar temprano puede dejar todo el resultado ocupado por un solo campo.
El pool completo ordenado es lo que necesita el frontend para su slider de "afinidad
mínima".

---

# Motor — paso 4: cercanía geográfica

Función `haversine_km()` — distancia entre dos puntos sobre una esfera

$$a = \sin^2\!\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\!\left(\frac{\Delta\lambda}{2}\right)$$
$$d = 2r \cdot \arcsin(\sqrt{a}) \qquad (r = 6371 \text{ km})$$

- Compara el cantón del estudiante contra el cantón de cada oferta.
- La distancia se invierte y escala 0-1 (`MinMaxScaler`) → score de cercanía.
- Se combina con la similitud RIASEC según el peso que el estudiante le dé a "vivir cerca"
  (0 = indiferente, 1 = solo importa la cercanía):

```
score_final = (1 - peso_cercania) * similitud_riasec + peso_cercania * score_cercania
```

---

# Motor — paso 5: exploración por clústeres

`MotorRecomendacion.explorar_clusters_vocacionales()` — `sklearn.cluster.KMeans`

- **No** es una búsqueda puntual — agrupa **todas** las carreras únicas en clústeres
  vocacionales, sobre el mismo espacio de 6 dimensiones (R,I,A,S,E,C).
- Pensado para una futura vista de "explorá por familia de interés" en el frontend.
- Queda **separado** del flujo de `buscar()`: no participa del `score_final`.

<div class="pt-6 text-sm opacity-70">

Sin diversificación ni tope de resultados: <code>buscar()</code> devuelve <b>todo</b> el
pool filtrado, ordenado por <code>score_final</code> — el frontend decide cuánto mostrar.

</div>

---

# La API (FastAPI)

`backend/main.py` — envuelve el motor en 6 endpoints REST

| Método | Endpoint | Qué hace |
|---|---|---|
| GET | `/api/salud` | healthcheck |
| GET | `/api/test-riasec` | los 60 ítems del test + info de dimensiones |
| POST | `/api/calcular-perfil` | respuestas → puntaje RIASEC 0-1 por dimensión |
| GET | `/api/opciones` | valores disponibles para los filtros |
| POST | `/api/recomendar` | perfil + preferencias → **todas** las carreras filtradas, ordenadas |
| POST | `/api/comentario-perfil` | comentario opcional generado por IA (Groq) sobre el perfil |

---

# El frontend

Vanilla JS — 3 pantallas: test → perfil/preferencias → resultados

<img src="./assets/screenshot_resultados.png" class="rounded shadow mx-auto max-h-100" />

<div class="text-center text-sm opacity-70 pt-2">
Lista de carreras + "Mapa de afinidad" (círculos concéntricos por tier: núcleo / intermedio / alejada)
</div>

---

# Demo en vivo: notebook Colab

Este backend completo — cada algoritmo, aislado y explicado — corre en un notebook Colab
autocontenido (sin subir ningún archivo, con una muestra de datos embebida):

**`notebooks/demo_backend_colab.ipynb`**

- Filtro duro, TF-IDF, `NearestNeighbors`, Haversine y `KMeans`: cada uno en su propia
  celda-demo, antes de integrarse al motor completo.
- Perfil vocacional editable: cambiás los 6 valores RIASEC y volvés a correr para ver
  cómo cambian las recomendaciones.

<div class="pt-8 text-center text-xl">
👉 vamos al notebook
</div>

---

# Implementación real desplegada

Este sistema **no es solo un ejercicio académico** — está en producción, de punta a punta:

<div class="text-2xl text-center pt-4 pb-8">

🔗 **tucarrera-ecuador.vercel.app**

</div>

| Capa | Dónde |
|---|---|
| Frontend | Vercel (HTML/CSS/JS vanilla) |
| Backend | Render — API FastAPI (`tucarreraecuador.onrender.com`) |
| Motor | mismo código explicado en este deck, sobre las **8014 carreras** reales |

---

# Pendientes y referencias

**Próximos pasos:**

1. Aprendizaje supervisado (`RandomForestClassifier`) sobre feedback real de usuarios.
2. Ampliar `PALABRAS_CLAVE_DIMENSION` con más vocabulario/sinónimos.
3. Validar el mapeo RIASEC↔campo amplio con un orientador vocacional.
4. Migrar coordenadas de cantones a la fuente oficial INEC/IGM.

<br>

**Fuentes:**

- Oferta académica: SENESCYT, Portal Único de Datos Abiertos del Ecuador (5-feb-2025).
- Test vocacional: National Center for O*NET Development (2010), *O*NET Interest Profiler
  Short Form*, U.S. Department of Labor.

---
class: text-center
---

# Gracias

**Arturo Rodríguez, PhD** ([ORCID 0000-0002-7017-9443](https://orcid.org/0000-0002-7017-9443)) — ULEAM

tucarrera-ecuador.vercel.app
