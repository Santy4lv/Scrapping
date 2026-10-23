# Instagram Profile Scraper & Dashboard 📊

Proyecto de extracción y análisis de datos de perfiles de Instagram para la materia de **Arquitectura de Software** (Tarea 1).

Incluye un scraper automatizado con **Playwright** que utiliza autenticación mediante cookies de sesión, junto con un **Dashboard Web interactivo** para visualizar seguidores, seguidos, publicaciones, descripciones, hashtags y comentarios.

---

## 🚀 Características

- **Extracción de perfil y métricas:**
  - Cantidad de publicaciones, seguidores, seguidos y biografía.
- **Lista de Seguidores y Seguidos:**
  - Desplazamiento automático con rebote en modales para sortear lazy-loading dinámico.
- **Detalle de Publicaciones:**
  - URLs de posts, descripciones completas, conteo de likes, hashtags (#) y menciones (@).
- **Extracción de Comentarios:**
  - Recolección de comentarios asociados a cada publicación (usuario + texto).
- **Múltiples formatos de exportación:**
  - `{usuario}_datos.json` (Estructura jerárquica completa para el dashboard).
  - `{usuario}_relaciones.csv` (Seguidores y seguidos).
  - `{usuario}_publicaciones.csv` (Publicaciones y métricas).
  - `{usuario}_comentarios.csv` (Comentarios por publicación).
- **Visualizador Web Interactivo (`dashboard.html`):**
  - Interfaz moderna con modo oscuro y diseño Glassmorphism.
  - Carga arrastrando y soltando (drag-and-drop) del archivo JSON.
  - Métricas clave en tarjetas dinámicas (Follower/Following ratio, engagement, etc.).
  - Pestaña de publicaciones con acordeón expandible de comentarios.
  - Pestaña de seguidores y seguidos con buscador y filtros en tiempo real.

---

## 📋 Requisitos Previos

1. **Python 3.9+**
2. Instalar dependencias requeridas:
   ```bash
   pip install playwright python-dotenv
   playwright install chromium
   ```

---

## ⚙️ Configuración (.env)

Crea un archivo `.env` en la raíz del proyecto con tus credenciales de sesión y preferencias de extracción:

```env
TARGET_USER=sausage_player
IG_SESSION_ID=tu_sessionid_aqui
IG_DS_USER_ID=tu_ds_user_id_aqui

# Control modular de módulos (true/false)
SCRAPE_FOLLOWERS=false
SCRAPE_FOLLOWING=false
SCRAPE_POSTS=true
SCRAPE_COMMENTS=true

# Límites de extracción (0 = sin límite)
MAX_POSTS=5
MAX_COMMENTS_PER_POST=10
MAX_FOLLOWERS=0
MAX_FOLLOWING=0

# Modo de navegador
HEADLESS=false
```

> **Nota:** 
> - Puedes obtener `sessionid` y `ds_user_id` desde las cookies del navegador (F12 -> Application -> Cookies -> instagram.com).
> - Desactivar `SCRAPE_FOLLOWERS` y `SCRAPE_FOLLOWING` acelera considerablemente el tiempo de scraping si solo te interesan las publicaciones y el texto.

---

## 🏃‍♂️ Ejecución y Comandos CLI

Puedes ejecutar el scraper con la configuración de `.env`:

```bash
python PlayScrap.py
```

O sobreescribir cualquier módulo y límite directamente desde la terminal:

```bash
# Atajo rápido: solo publicaciones y comentarios (ignora seguidores/seguidos)
python PlayScrap.py --posts-only --max-posts 5

# Atajo rápido: solo red de contactos (seguidores y seguidos)
python PlayScrap.py --network-only --max-followers 50 --max-following 50

# Desactivar comentarios de publicaciones para agilizar la extracción
python PlayScrap.py --no-comments

# Cambiar de usuario y ejecutar sin ventana gráfica (headless)
python PlayScrap.py --user otro_usuario --headless --posts-only

# Ver todas las opciones disponibles
python PlayScrap.py --help
```

Al terminar, se generarán automáticamente los archivos JSON y CSV correspondientes a los módulos activos.

---

## 🖥️ Visualización en el Dashboard

1. Abre el archivo `dashboard.html` en cualquier navegador web (Chrome, Edge, Firefox).
2. Arrastra o selecciona el archivo JSON generado (ej. `sausage_player_datos.json`).
3. Explora las estadísticas generales, publicaciones, comentarios y listas de relaciones.
