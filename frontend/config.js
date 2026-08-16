// URL pública del backend en Render. window.API_BASE || aquí para no pisar un valor que
// ya haya sido fijado antes de cargar este script (p. ej. tests/test_e2e_frontend.py,
// que apunta a una API local vía page.add_init_script).
window.API_BASE = window.API_BASE || "https://tucarreraecuador.onrender.com";
