# Recomendador de Carreras Ecuador

Sistema de orientación vocacional del proyecto `RecomendadorCarrerasEcuador`: un test de
intereses (modelo RIASEC de Holland, basado en el O*NET Interest Profiler) que se cruza,
con **scikit-learn**, contra la base de datos abierta de oferta académica de las IES del
Ecuador (SENESCYT) para recomendar carreras y universidades afines al perfil del
estudiante, respetando sus preferencias (cercanía, modalidad, financiamiento, nivel).

Incluye pipeline de datos, motor de recomendación, API (FastAPI) y un frontend web
funcional de punta a punta (test -> preferencias -> resultados).

## Estructura

```
data/
  raw/            Insumos originales (Excel de SENESCYT, coordenadas crudas de cantones)
  processed/      Salidas del pipeline de limpieza (CSV + SQLite), se regeneran con los scripts
src/
  01_limpiar_oferta.py        Normaliza el Excel de SENESCYT (tildes, CAMPO_AMPLIO, nivel)
  02_cantones_coordenadas.py  Cruza los 99 cantones de la base con coordenadas (lat/lon)
  03_mapeo_riasec.py          Tabla curada: campo amplio -> pesos RIASEC (6 dimensiones)
  04_motor_recomendacion.py   Motor de recomendación (filtros + NearestNeighbors + KMeans)
  05_demo.py                  Corre todo el pipeline y prueba el motor con perfiles de ejemplo
backend/
  test_riasec.py              60 ítems del test RIASEC (traducidos del O*NET Interest Profiler)
  main.py                     API FastAPI: expone el test y el motor de recomendación
frontend/
  index.html, app.js, styles.css   App web (vanilla JS) que consume la API:
                                    test -> preferencias -> resultados (lista +
                                    "Mapa de afinidad", diagrama de círculos
                                    concéntricos por tier)
tests/
  test_e2e_frontend.py        Prueba de humo de punta a punta con Playwright
docs/
  screenshot_resultados.png   Captura de la pantalla de resultados
```

## Cómo correrlo

```bash
python -m venv .venv && source .venv/bin/activate   # opcional
pip install -r requirements.txt

# 1. Generar los datos limpios (una sola vez, o cuando cambie el Excel de SENESCYT)
python src/05_demo.py

# 2. Levantar la API (desde la raíz del repo)
uvicorn backend.main:app --reload --port 8000

# 3. Servir el frontend (en otra terminal)
python -m http.server 5500 --directory frontend
# abrir http://127.0.0.1:5500 en el navegador
```

Si sirves el frontend en un puerto distinto al de la API, o vas a desplegarlo en otro
dominio, define `window.API_BASE` antes de cargar `app.js` (por defecto apunta a
`http://127.0.0.1:8000`).

## Endpoints de la API (`backend/main.py`)

- `GET /api/test-riasec` — los 60 ítems del test (sin revelar su dimensión) + info de las 6 dimensiones.
- `POST /api/calcular-perfil` — `{"respuestas": {"R1": true, "I1": false, ...}}` -> puntaje 0-1 por dimensión.
- `GET /api/opciones` — valores disponibles para los filtros (modalidad, financiamiento, provincia/cantón, etc.).
- `POST /api/recomendar` — `{"perfil_riasec": {...}, "preferencias": {...}}` -> **todas**
  las carreras que pasan el filtro duro (sin tope, sin diversificar), ordenadas por
  `score_final` desc. El frontend decide cuánto mostrar y cómo agrupar por afinidad
  (`tier`) en el cliente — ver más abajo.

Documentación interactiva automática en `http://127.0.0.1:8000/docs` mientras la API corre.

## Cómo funciona el motor (`src/04_motor_recomendacion.py`)

1. **Filtro duro** (pandas): descarta ofertas que no cumplen una preferencia obligatoria
   del estudiante (modalidad, financiamiento, tipo de IES, nivel de formación; por
   defecto excluye posgrado).
2. **Búsqueda por similitud** (`sklearn.neighbors.NearestNeighbors`, métrica coseno):
   compara el vector RIASEC del estudiante (6 dimensiones) contra el vector de cada
   oferta, derivado de `mapeo_riasec_campo_amplio.csv`. Se pide el ranking completo del
   pool filtrado (no un top-k chico): el motor no recorta nada, así que necesita el
   score de cada candidato, no solo de los primeros.
3. **Cercanía geográfica** (fórmula de Haversine sobre `cantones_coordenadas.csv`):
   se combina con la similitud RIASEC según el peso que el estudiante le dé a "vivir
   cerca" (0 = indiferente, 1 = solo importa la cercanía).
4. **Sin diversificación ni tope**: se deduplican filas repetidas de la misma pareja
   (carrera, IES) y se devuelve **todo** el pool ordenado por `score_final` desc — nada
   de round-robin por campo amplio ni límite de filas. La razón: el vector RIASEC de
   cada oferta se deriva de su `CAMPO_AMPLIO_NORMALIZADO` (10 categorías), así que
   diversificar por campo o cortar a un top-N arbitrario terminaba escondiendo carreras
   con afinidad real alta (ej. 85%) solo porque su campo quedaba 7mo en el ranking.
   El frontend (`app.js`) arma el "Mapa de afinidad" (diagrama de círculos concéntricos)
   calculando el `tier` directo sobre `similitud_riasec` (`nucleo` ≥80%, `intermedio`
   ≥50%, `alejada` el resto), y deja que un slider de "afinidad mínima" (por
   defecto 80%, ajustable a 0%) decida cuánto de ese pool completo se muestra — tanto en
   la lista de tarjetas como en el diagrama.
5. **Exploración por clústeres** (`sklearn.cluster.KMeans`, método aparte
   `explorar_clusters_vocacionales`): agrupa todas las carreras únicas en clústeres
   vocacionales, pensado para una vista de "explora por familia de interés" en el
   frontend, no para una búsqueda puntual.

## El test vocacional (`backend/test_riasec.py`)

60 actividades (10 por cada dimensión RIASEC), traducidas al español a partir del
**O*NET Interest Profiler Short Form** (National Center for O*NET Development, US Dept.
of Labor) — instrumento con licencia abierta que permite explícitamente redistribuirlo y
construir nuevas evaluaciones a partir de él. El orden de presentación intercala las 6
dimensiones para no revelar la categoría de cada actividad mientras el estudiante
responde.

## Datos generados que requieren revisión de un experto

- `data/processed/mapeo_riasec_campo_amplio.csv`: los pesos RIASEC por campo amplio
  están curados a mano según literatura general de orientación vocacional. Conviene que
  un orientador vocacional o psicólogo educativo los revise y ajuste antes de producción.
- `data/processed/cantones_coordenadas.csv`: coordenadas de 92 cantones vienen de un
  gist comunitario (no oficial); 2 cantones (Puyo y General Plaza/Méndez) se corrigieron
  a mano tras detectar coordenadas erróneas en esa fuente, cruzando con otras referencias.
  Antes de usar esto para cálculos de distancia finos, conviene migrar a las coordenadas
  oficiales del INEC/IGM (ver Referencias en el plan del proyecto).

## Cómo correr la prueba de punta a punta

```bash
pip install -r requirements-dev.txt
uvicorn backend.main:app --port 8123 &
python -m http.server 8765 --directory frontend &
python tests/test_e2e_frontend.py
```

Completa el test con respuestas simuladas, navega las 3 pantallas, verifica que la API
responda y guarda una captura en `docs/screenshot_resultados.png`.

> `test_e2e_frontend.py` usa el Chromium que Playwright tiene cacheado (`playwright
> install chromium` si no lo corriste todavía); solo si necesitás forzar otro binario,
> seteá la variable de entorno `PLAYWRIGHT_CHROMIUM_PATH`.

## Deploy

- **Frontend**: Vercel, proyecto `tucarrera-ecuador` (ver `frontend/.vercel/project.json`).
- **Backend**: Render, expuesto en `https://tucarreraecuador.onrender.com` (ver
  `frontend/config.js`, que fija `window.API_BASE` a esa URL en producción). Para
  desarrollo local hay que sobreescribir `config.js` o cargar `window.API_BASE` antes de
  `app.js` apuntando a tu API local.

## Próximos pasos

1. Añadir una fase de aprendizaje supervisado (`DecisionTreeClassifier` /
   `RandomForestClassifier`) que reentrene el re-ranking con retroalimentación real de
   usuarios ("me interesó" / "no me interesó").
2. Enriquecer el vector RIASEC por carrera individual (hoy es por campo amplio) usando,
   por ejemplo, similitud de texto sobre `NOMBRE_CARRERA` — hoy todas las carreras de un
   mismo campo amplio comparten posición en el "Mapa de afinidad", una señal más fina
   permitiría separarlas dentro del mismo anillo.
3. Validar el mapeo RIASEC↔campo amplio con un orientador vocacional.
4. Migrar las coordenadas de cantones a la fuente oficial del INEC/IGM.

## Fuente de los datos

- Base de oferta académica: Secretaría de Educación Superior, Ciencia, Tecnología e
  Innovación (SENESCYT), Portal Único de Datos Abiertos del Ecuador (27 de febrero de
  2025).
- Coordenadas de cantones: gist público "Coordenadas de todos los cantones de Ecuador"
  (c4rlosviteri), con 2 correcciones manuales verificadas contra Wikipedia /
  geodatos.net / world-airport-codes.
- Test vocacional: O*NET Interest Profiler Short Form, National Center for O*NET
  Development (onetcenter.org), traducido al español para este proyecto.
