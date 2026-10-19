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

Crea un archivo `.env` en la raíz del proyecto con tus credenciales de sesión de Instagram:

```env
TARGET_USER=sausage_player
IG_SESSION_ID=tu_sessionid_aqui
IG_DS_USER_ID=tu_ds_user_id_aqui
MAX_POSTS=0
```

> **Nota:** 
> - Puedes obtener `sessionid` y `ds_user_id` desde las cookies del navegador (F12 -> Application -> Cookies -> instagram.com).
> - `MAX_POSTS=0` procesa todas las publicaciones. Si deseas probar con un número reducido, ajusta el valor (por ejemplo, `MAX_POSTS=5`).

---

## 🏃‍♂️ Ejecución

Para iniciar el proceso de scraping:

```bash
python PlayScrap.py
```

Al terminar, se generarán automáticamente los archivos JSON y CSV correspondientes al usuario objetivo.

---

## 🖥️ Visualización en el Dashboard

1. Abre el archivo `dashboard.html` en cualquier navegador web (Chrome, Edge, Firefox).
2. Arrastra o selecciona el archivo JSON generado (ej. `sausage_player_datos.json`).
3. Explora las estadísticas generales, publicaciones, comentarios y listas de relaciones.
