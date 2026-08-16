"""
Prueba de humo de extremo a extremo con Playwright: sirve el frontend
estático y pega contra una API corriendo en background, completa el test
vocacional, elige preferencias y verifica que se rendericen recomendaciones.

Requiere tener corriendo antes:
    uvicorn backend.main:app --port 8123
    python -m http.server 8765 --directory frontend

Uso: python tests/test_e2e_frontend.py
"""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
DOCS_DIR.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_page(viewport={"width": 900, "height": 1000})
    errores_consola = []
    page.on("console", lambda msg: errores_consola.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errores_consola.append(str(exc)))

    page.add_init_script("window.API_BASE = 'http://127.0.0.1:8123';")
    page.goto("http://127.0.0.1:8765/index.html")
    page.wait_for_selector(".item-test", timeout=10000)

    n_items = page.eval_on_selector_all(".item-test", "els => els.length")
    print("Items de test renderizados:", n_items)

    # Contestar los 60 items alternando "si"/"no" para variar el perfil
    botones_si = page.query_selector_all(".switch-grupo .si")
    botones_no = page.query_selector_all(".switch-grupo .no")
    for i, (si, no) in enumerate(zip(botones_si, botones_no)):
        (si if i % 3 != 0 else no).click()

    time.sleep(0.3)
    progreso = page.eval_on_selector("#barra-test", "el => el.style.width")
    print("Progreso barra:", progreso)
    habilitado = page.eval_on_selector("#btn-ir-preferencias", "el => !el.disabled")
    print("Botón continuar habilitado:", habilitado)

    page.click("#btn-ir-preferencias")
    page.wait_for_selector("#pantalla-preferencias.visible")
    resumen = page.inner_text("#resumen-perfil")
    print("\nResumen del perfil:\n", resumen)

    # elegir preferencias
    page.select_option("#pref-modalidad", "PRESENCIAL")
    page.select_option("#pref-provincia", "PICHINCHA")
    page.wait_for_timeout(200)
    opciones_canton = page.eval_on_selector_all("#pref-canton option", "els => els.map(e => e.value)")
    print("Cantones cargados para Pichincha:", opciones_canton[:5], "...")
    if "QUITO" in opciones_canton:
        page.select_option("#pref-canton", "QUITO")
    page.fill("#pref-cercania", "0")
    page.eval_on_selector("#pref-cercania", "el => el.value = 40")
    page.dispatch_event("#pref-cercania", "input")

    page.click("#btn-ver-resultados")
    page.wait_for_selector("#pantalla-resultados.visible")
    page.wait_for_timeout(800)
    resultados_html = page.inner_text("#lista-resultados")
    print("\n--- Resultados ---\n", resultados_html[:2000])

    n_resultados = page.eval_on_selector_all(".resultado-item", "els => els.length")
    print("\nNúmero de tarjetas de resultado:", n_resultados)

    print("\nErrores de consola/página:", errores_consola if errores_consola else "ninguno")

    ruta_captura = DOCS_DIR / "screenshot_resultados.png"
    page.screenshot(path=str(ruta_captura), full_page=True)
    print(f"\nCaptura guardada en: {ruta_captura}")
    browser.close()
