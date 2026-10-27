# Instagram Profile Scraper & Unified Dashboard 📊

Proyecto de extracción automatizada, análisis forense de bots y evaluación psicométrica de perfiles de Instagram para la materia de **Arquitectura de Software**.

Combina un scraper automatizado con **Playwright** (autenticado por cookies de sesión) con un **Dashboard Web interactivo desacoplado** (`dashboard.html` + arquitectura modular en `js/`) que integra análisis de engagement, detección forense de bots mediante la **Ley de Benford** y análisis de personalidad con **Google Gemini AI (Big Five OCEAN)** y motor léxico de contingencia.

---

## 🚀 Arquitectura y Características

### 1. Extractor Automatizado (`PlayScrap.py`)
- **Extracción de perfil y métricas:** Cantidad de publicaciones, seguidores, seguidos, biografía y foto de perfil (`{usuario}_avatar.jpg`).
- **Relaciones con Métricas Forenses:** Extrae seguidores y seguidos capturando sus métricas individuales (`seguidores`, `seguidos`, `publicaciones`) mediante tarjetas hover para análisis estadístico.
- **Publicaciones y Multimedia:** URLs de imágenes, carruseles multi-foto completos, textos alternativos (`alt_texto`), conteo de likes, hashtags (#) y menciones (@).
- **Comentarios:** Extracción jerárquica de comentarios por publicación (usuario y texto).
- **Configuración centralizada en `.env`:** Control granular de límites (`MAX_FOLLOWERS`, `MAX_FOLLOWING`, `MAX_POSTS`, `MAX_COMMENTS_PER_POST`; donde `0` = sin límite / todos disponibles).
- **Exportación limpia:** Genera `{usuario}_datos.json` estructurado y normalizado.

### 2. Dashboard Web Modular (`dashboard.html`)
Diseñado bajo el principio de **separación estricta de responsabilidades**:
- **`dashboard.html`**: Estructura semántica pura y estilos visuales Glassmorphism en modo oscuro (sin lógica de negocio embebida).
- **`js/storage.js`**: Persistencia de estado en `localStorage` (`DATA`, pestaña activa, análisis de personalidad y API Key). Conserva los resultados tras recargar con F5 y ofrece un botón *"🔄 Cambiar perfil"* para resetear.
- **`js/benford.js`**: Motor forense de la Ley de Benford en JavaScript puro. Calcula primer dígito significativo (FSD), $\chi^2$ con cálculo analítico de $p$-valor ($df=8$), MAD de Mark Nigrini, distancia Kolmogorov-Smirnov $D$ y *Human Likeness Score* ($0\% - 100\%$). Procesa seguidores, seguidos o ambos de forma agnóstica.
- **`js/benford_ui.js`**: Renderizado de la pestaña de detección de bots, tarjetas estadísticas, selectores de serie (`Seguidores`, `Seguidos`, `Red Consolidada`), gráfico comparativo Chart.js y tabla de dígitos del 1 al 9.
- **`js/bigfive.js`**: Motor psicométrico de los Cinco Grandes Factores (OCEAN). Soporta evaluación avanzada mediante **Google Gemini REST API** (`gemini-2.5-flash`) y un **motor léxico local de contingencia** transparente y offline.
- **`js/bigfive_ui.js`**: Pestaña interactiva bajo demanda: campo de API key opcional, botón de análisis con spinner de procesamiento, insignia de motor activo (`[✨ Google Gemini]` vs `[⚡ Motor Léxico]`), Radar Chart psicométrico y tarjetas detalladas de los 5 rasgos.
- **`js/app.js`**: Controlador de interfaz: drag-and-drop, lectura JSON, contadores numéricos animados, gráficos de resumen (engagement, hashtags, comentaristas, menciones), carruseles de posts, modal de comentarios y búsqueda reactiva.

---

## 📋 Requisitos Previos

1. **Python 3.9+**
2. Instalar dependencias requeridas:
   ```bash
   pip install playwright python-dotenv
   playwright install chromium
   ```

---

## ⚙️ Configuración (`.env`)

Copia la plantilla y configura tus credenciales de sesión en `.env`:

```bash
cp .env.example .env
```

Ejemplo de contenido:
```env
TARGET_USER=sausage_player
IG_SESSION_ID=tu_sessionid_aqui
IG_DS_USER_ID=tu_ds_user_id_aqui

# Módulos activos (true/false)
SCRAPE_FOLLOWERS=true
SCRAPE_FOLLOWING=true
SCRAPE_POSTS=true
SCRAPE_COMMENTS=true

# Límites de extracción (0 = sin límite / todos los disponibles)
MAX_POSTS=10
MAX_COMMENTS_PER_POST=10
MAX_FOLLOWERS=200
MAX_FOLLOWING=100

# Navegador
HEADLESS=false

# Opcional: Gemini API Key para análisis de personalidad
GEMINI_API_KEY=tu_gemini_api_key_aqui
```

> **Nota:** Las cookies `sessionid` y `ds_user_id` se obtienen desde las herramientas de desarrollo del navegador (F12 -> Application -> Cookies -> instagram.com).

---

## 🏃‍♂️ Extracción de Datos (CLI)

Ejecuta el scraper con los parámetros de `.env`:
```bash
python PlayScrap.py
```

O sobrescribe opciones desde la línea de comandos:
```bash
# Solo publicaciones y comentarios (ignora seguidores y seguidos)
python PlayScrap.py --posts-only --max-posts 5

# Extraer seguidores y seguidos con límites específicos
python PlayScrap.py --max-followers 50 --max-following 50

# Modo sin ventana gráfica (headless)
python PlayScrap.py --headless

# Ver todas las opciones disponibles
python PlayScrap.py --help
```

Al finalizar, se generará el archivo `{usuario}_datos.json`.

---

## 🖥️ Uso del Dashboard Unificado

1. Abre [`dashboard.html`](dashboard.html) en tu navegador preferido (Chrome, Edge, Firefox, Safari).
2. Arrastra y suelta el archivo JSON generado (o haz clic en *Seleccionar archivo JSON*).
3. Navega por las secciones disponibles:
   - **Resumen:** Métricas globales, avatar, biografía y gráficos de engagement, hashtags y comentaristas.
   - **Publicaciones:** Grid de publicaciones con visor de carruseles multimedia y comentarios.
   - **Seguidores / Seguidos:** Fichas de usuarios con métricas de audiencia y buscador reactivo.
   - **🤖 Detección de Bots:** Evaluación forense de Benford, nivel de conformidad, probabilidad de autenticidad humana, tarjetas $\chi^2$/MAD y gráfico comparativo.
   - **🧠 Personalidad (Big Five):** Ejecución bajo demanda con Gemini AI o motor local, visualización en Radar Chart y desglose de rasgos OCEAN.
4. **Persistencia:** Puedes recargar la página (F5) en cualquier momento; tus datos y análisis se mantendrán en pantalla. Para cargar otro perfil, haz clic en **"🔄 Cambiar perfil"**.
