import argparse
import asyncio
import csv
from dataclasses import dataclass, asdict
import json
import os
import random
import re
import sys
import time as time_module
from dotenv import load_dotenv
from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ─────────────────────────────────────────────────────────
# Utilidades de Configuración y Tipos
# ─────────────────────────────────────────────────────────
def str_to_bool(val, default=True):
    """Convierte cadenas comunes o booleanos a bool de Python."""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("true", "1", "yes", "si", "s", "t", "y"):
        return True
    if s in ("false", "0", "no", "n", "f"):
        return False
    return default


@dataclass
class ScraperConfig:
    """Configuración centralizada y tipada para la ejecución del scraper."""
    target_user: str
    session_id: str
    ds_user_id: str
    scrape_followers: bool = True
    scrape_following: bool = True
    scrape_posts: bool = True
    scrape_comments: bool = True
    max_posts: int = 0
    max_comments_per_post: int = 0
    max_followers: int = 0
    max_following: int = 0
    headless: bool = False

    @classmethod
    def from_env_and_cli(cls, args=None):
        load_dotenv()

        # 1. Valores por defecto desde variables de entorno
        env_target = os.getenv("TARGET_USER", "sausage_player")
        env_session = os.getenv("IG_SESSION_ID")
        env_ds = os.getenv("IG_DS_USER_ID")
        env_max_posts = int(os.getenv("MAX_POSTS", "0"))
        env_followers = str_to_bool(os.getenv("SCRAPE_FOLLOWERS"), default=True)
        env_following = str_to_bool(os.getenv("SCRAPE_FOLLOWING"), default=True)
        env_posts = str_to_bool(os.getenv("SCRAPE_POSTS"), default=True)
        env_comments = str_to_bool(os.getenv("SCRAPE_COMMENTS"), default=True)
        env_max_comments = int(os.getenv("MAX_COMMENTS_PER_POST", "0"))
        env_max_followers = int(os.getenv("MAX_FOLLOWERS", "0"))
        env_max_following = int(os.getenv("MAX_FOLLOWING", "0"))
        env_headless = str_to_bool(os.getenv("HEADLESS"), default=False)

        # 2. Argumentos CLI para sobreescritura rápida
        parser = argparse.ArgumentParser(
            description="Scraper modular de Instagram con Playwright",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        parser.add_argument("--user", type=str, default=None, help="Usuario objetivo (anula TARGET_USER de .env)")
        parser.add_argument("--max-posts", type=int, default=None, help="Límite de publicaciones (0 = sin límite)")
        parser.add_argument("--max-comments", type=int, default=None, help="Límite de comentarios por post (0 = sin límite)")
        parser.add_argument("--max-followers", type=int, default=None, help="Límite de seguidores a extraer (0 = sin límite)")
        parser.add_argument("--max-following", type=int, default=None, help="Límite de seguidos a extraer (0 = sin límite)")
        parser.add_argument("--headless", action="store_true", default=None, help="Ejecutar en modo headless (sin ventana gráfica)")

        # Presets rápidos
        parser.add_argument("--posts-only", action="store_true", help="Atajo: solo posts y comentarios (omite seguidores y seguidos)")
        parser.add_argument("--network-only", action="store_true", help="Atajo: solo seguidores y seguidos (omite posts y comentarios)")

        # Toggles individuales de módulos
        parser.add_argument("--followers", dest="scrape_followers", action="store_true", default=None, help="Activar extracción de seguidores")
        parser.add_argument("--no-followers", dest="scrape_followers", action="store_false", help="Desactivar extracción de seguidores")

        parser.add_argument("--following", dest="scrape_following", action="store_true", default=None, help="Activar extracción de seguidos")
        parser.add_argument("--no-following", dest="scrape_following", action="store_false", help="Desactivar extracción de seguidos")

        parser.add_argument("--posts", dest="scrape_posts", action="store_true", default=None, help="Activar extracción de publicaciones")
        parser.add_argument("--no-posts", dest="scrape_posts", action="store_false", help="Desactivar extracción de publicaciones")

        parser.add_argument("--comments", dest="scrape_comments", action="store_true", default=None, help="Activar extracción de comentarios")
        parser.add_argument("--no-comments", dest="scrape_comments", action="store_false", help="Desactivar extracción de comentarios")

        parsed = parser.parse_args(args)

        # Resolución de configuraciones finales
        target_user = parsed.user or env_target
        session_id = env_session
        ds_user_id = env_ds
        max_posts = parsed.max_posts if parsed.max_posts is not None else env_max_posts
        max_comments = parsed.max_comments if parsed.max_comments is not None else env_max_comments
        max_followers = parsed.max_followers if parsed.max_followers is not None else env_max_followers
        max_following = parsed.max_following if parsed.max_following is not None else env_max_following
        headless = parsed.headless if parsed.headless is not None else env_headless

        # Aplicación de toggles base
        followers = env_followers
        following = env_following
        posts = env_posts
        comments = env_comments

        # Presets rápidos
        if parsed.posts_only:
            followers = False
            following = False
            posts = True
        elif parsed.network_only:
            followers = True
            following = True
            posts = False
            comments = False

        # Sobreescritura individual de flags
        if parsed.scrape_followers is not None:
            followers = parsed.scrape_followers
        if parsed.scrape_following is not None:
            following = parsed.scrape_following
        if parsed.scrape_posts is not None:
            posts = parsed.scrape_posts
        if parsed.scrape_comments is not None:
            comments = parsed.scrape_comments

        if not session_id or not ds_user_id:
            raise ValueError(
                "Las variables de entorno IG_SESSION_ID o IG_DS_USER_ID no están definidas. "
                "Verifica tu archivo .env local."
            )

        return cls(
            target_user=target_user,
            session_id=session_id,
            ds_user_id=ds_user_id,
            scrape_followers=followers,
            scrape_following=following,
            scrape_posts=posts,
            scrape_comments=comments,
            max_posts=max_posts,
            max_comments_per_post=max_comments,
            max_followers=max_followers,
            max_following=max_following,
            headless=headless,
        )

    def print_banner(self):
        """Muestra en terminal la configuración con la que iniciará el scraper."""
        f_fol = (
            f"[✓ Activo] (Límite: {self.max_followers if self.max_followers > 0 else 'Sin límite'})"
            if self.scrape_followers
            else "[✗ Omitido]"
        )
        f_flw = (
            f"[✓ Activo] (Límite: {self.max_following if self.max_following > 0 else 'Sin límite'})"
            if self.scrape_following
            else "[✗ Omitido]"
        )
        f_pst = (
            f"[✓ Activo] (Límite: {self.max_posts if self.max_posts > 0 else 'Sin límite'})"
            if self.scrape_posts
            else "[✗ Omitido]"
        )
        f_cmt = (
            f"[✓ Activo] (Límite por post: {self.max_comments_per_post if self.max_comments_per_post > 0 else 'Sin límite'})"
            if (self.scrape_posts and self.scrape_comments)
            else "[✗ Omitido]"
        )

        print("\n" + "=" * 62)
        print(" ⚙️   CONFIGURACIÓN MODULAR DE EXTRACCIÓN")
        print("=" * 62)
        print(f"  🎯 Usuario objetivo:       {self.target_user}")
        print(f"  👥 Seguidores (followers): {f_fol}")
        print(f"  🫂 Seguidos (following):   {f_flw}")
        print(f"  📸 Publicaciones (posts):  {f_pst}")
        print(f"  💬 Comentarios (comments): {f_cmt}")
        print(f"  🖥️  Navegador:              {'Headless (oculto)' if self.headless else 'Visible'}")
        print("=" * 62 + "\n")


# ─────────────────────────────────────────────────────────
# Utilidades generales
# ─────────────────────────────────────────────────────────
def parsear_numero(texto):
    """Extrae el primer número entero de una cadena."""
    if not texto:
        return 0
    limpio = texto.replace(".", "").replace(",", "")
    match = re.search(r"\d+", limpio)
    return int(match.group(0)) if match else 0


def extraer_hashtags(texto):
    """Extrae todos los #hashtags de un texto."""
    return re.findall(r"#[\w\u00C0-\u024F]+", texto) if texto else []


def extraer_menciones(texto):
    """Extrae todas las @menciones de un texto."""
    return re.findall(r"@[\w.]+", texto) if texto else []


async def descartar_popups(page):
    """Cierra diálogos emergentes que interfieren con la interfaz."""
    for texto in [
        "Ahora no",
        "Not Now",
        "Cancelar",
        "Aceptar todo",
        "Decline optional cookies",
    ]:
        try:
            btn = page.locator(f"button:has-text('{texto}')").first
            if await btn.is_visible(timeout=1000):
                await btn.click()
                await page.wait_for_timeout(600)
        except Exception:
            pass


async def pausa_humana(page, min_s=1.5, max_s=3.0):
    """Espera un tiempo aleatorio para simular comportamiento humano."""
    await page.wait_for_timeout(int(random.uniform(min_s, max_s) * 1000))


# ─────────────────────────────────────────────────────────
# Scroll con rebote (modales de seguidores/seguidos)
# ─────────────────────────────────────────────────────────
async def scroll_con_rebote(page):
    """Aplica desplazamiento interno y rebote para forzar el evento scroll del DOM."""
    return await page.evaluate(
        r"""() => {
        const dialog = document.querySelector("div[role='dialog']");
        if (!dialog) return { found: false, hasSpinner: false };

        const container = Array.from(dialog.querySelectorAll("div")).find(
            el => el.scrollHeight > el.clientHeight && el.clientHeight > 150
        );
        if (!container) return { found: false, hasSpinner: false };

        const hasSpinner = dialog.querySelector(
            "svg circle, div[role='progressbar'], svg[aria-label*='Cargando'], svg[aria-label*='Loading']"
        ) !== null;

        const dist = container.scrollHeight - container.clientHeight - container.scrollTop;
        if (dist < 25) {
            container.scrollTop = container.scrollTop - 160;
            container.dispatchEvent(new Event('scroll', { bubbles: true }));
            setTimeout(() => {
                container.scrollTop = container.scrollHeight;
                container.dispatchEvent(new Event('scroll', { bubbles: true }));
            }, 80);
        } else {
            container.scrollTop = container.scrollHeight;
            container.dispatchEvent(new Event('scroll', { bubbles: true }));
        }

        return { found: true, hasSpinner: hasSpinner };
    }"""
    )


# ─────────────────────────────────────────────────────────
# Extracción de seguidores / seguidos
# ─────────────────────────────────────────────────────────
async def extraer_relaciones(page, tipo="following", meta=0, limit=0):
    texto_es = "seguidos" if tipo == "following" else "seguidores"
    target_limit = limit if limit > 0 else meta
    limite_txt = f"{target_limit}" if target_limit > 0 else "todos disponibles"

    print(f"\n==========================================")
    print(f" Extrayendo {tipo} (Objetivo: {limite_txt})")
    print(f"==========================================")

    selector_btn = (
        f"a[href*='/{tipo}/'], a:has-text('{texto_es}'), span:has-text('{texto_es}')"
    )
    try:
        boton = page.locator(selector_btn).first
        await boton.wait_for(state="visible", timeout=8000)
        await boton.click()
    except Exception as e:
        print(f"Error al abrir la modal de {tipo}: {e}")
        return []

    dialog = page.locator("div[role='dialog']")
    await dialog.wait_for(state="visible", timeout=10000)
    await page.wait_for_timeout(1800)

    usuarios = set()
    intentos_sin_cambio = 0
    MAX_INTENTOS = 3

    while intentos_sin_cambio < MAX_INTENTOS:
        nuevos = await dialog.locator("a[role='link']").evaluate_all(
            r"""elements => {
            const list = [];
            for (const el of elements) {
                const href = el.getAttribute('href');
                if (href && href.startsWith('/') && !href.startsWith('/explore/')
                    && !href.startsWith('/direct/')) {
                    const u = href.replaceAll('/', '').trim();
                    if (u && !list.includes(u)) list.push(u);
                }
            }
            return list;
        }"""
        )

        prev_count = len(usuarios)
        usuarios.update(nuevos)
        total_actual = len(usuarios)

        if target_limit > 0 and total_actual >= target_limit:
            print(f"[COMPLETADO] Se alcanzó la meta establecida: {total_actual}/{target_limit}")
            break

        estado_scroll = await scroll_con_rebote(page)

        if total_actual > prev_count:
            intentos_sin_cambio = 0
            print(f"Progreso {tipo}: {total_actual} recolectados...")
        else:
            if estado_scroll.get("hasSpinner"):
                print("  [Instagram procesando solicitud...]")
                await page.wait_for_timeout(2000)
                continue
            intentos_sin_cambio += 1
            print(
                f"  Sin elementos nuevos ({intentos_sin_cambio}/{MAX_INTENTOS})..."
            )

        await page.wait_for_timeout(int(random.uniform(1.8, 2.5) * 1000))

    await page.keyboard.press("Escape")
    await page.wait_for_timeout(1200)

    result = list(usuarios)
    if limit > 0:
        result = result[:limit]

    print(f"Fase {tipo} finalizada. Total obtenido: {len(result)}")
    return result


# ─────────────────────────────────────────────────────────
# Recolección de URLs de publicaciones (grid del perfil)
# ─────────────────────────────────────────────────────────
async def recolectar_urls_posts(page, meta_posts=0, max_posts=0):
    """Scrollea la página del perfil para cargar y recoger los enlaces de cada post en orden cronológico real."""
    print("\n==========================================")
    print(" Recolectando URLs de publicaciones...")
    print("==========================================")

    ordered_urls = []
    intentos = 0
    MAX_INTENTOS = 4
    limite = max_posts if max_posts > 0 else meta_posts

    while intentos < MAX_INTENTOS:
        nuevas = await page.locator("a[href*='/p/'], a[href*='/reel/']").evaluate_all(
            "els => els.map(e => e.getAttribute('href')).filter(Boolean)"
        )

        prev_count = len(ordered_urls)
        for u in nuevas:
            clean_u = u.split("?")[0].rstrip("/") + "/"
            if clean_u not in ordered_urls:
                ordered_urls.append(clean_u)

        if limite > 0 and len(ordered_urls) >= limite:
            print(f"[GRID] Meta alcanzada: {len(ordered_urls)}/{limite}")
            break

        if len(ordered_urls) > prev_count:
            intentos = 0
            print(f"[GRID] {len(ordered_urls)} publicaciones encontradas...")
        else:
            intentos += 1
            print(f"  Sin posts nuevos ({intentos}/{MAX_INTENTOS})...")

        await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        await pausa_humana(page, 1.5, 2.5)

    if max_posts > 0:
        ordered_urls = ordered_urls[:max_posts]

    print(f"[GRID] Total URLs recolectadas en orden de perfil: {len(ordered_urls)}")
    return ordered_urls


# ─────────────────────────────────────────────────────────
# Extracción de comentarios dentro de un post
# ─────────────────────────────────────────────────────────
async def extraer_comentarios_post(page, max_comments=0, target_user=""):
    """Expande y extrae los comentarios del post actual."""
    # 1. Intentar abrir la vista completa de comentarios
    for selector in [
        "span:has-text('Ver todos')",
        "span:has-text('View all')",
        "span:has-text('Ver los')",
        "a:has-text('View all')",
        "a:has-text('Ver los')",
        "a:has-text('Ver todos')",
    ]:
        try:
            el = page.locator(selector).first
            if await el.is_visible(timeout=1500):
                await el.click()
                await pausa_humana(page, 1.5, 2.5)
                break
        except Exception:
            pass

    # 2. Desplazar e intentar expandir respuestas
    scroll_cycles = 1 if (0 < max_comments <= 5) else 3
    for _ in range(scroll_cycles):
        for sel in [
            "button:has-text('más comentarios')",
            "button:has-text('more comments')",
            "button:has-text('Ver respuestas')",
            "button:has-text('View replies')",
        ]:
            try:
                btns = page.locator(sel)
                cnt = await btns.count()
                for i in range(min(cnt, 3)):
                    try:
                        b = btns.nth(i)
                        if await b.is_visible(timeout=500):
                            await b.click()
                            await page.wait_for_timeout(800)
                    except Exception:
                        pass
            except Exception:
                pass

        await page.evaluate(r"""() => {
            const container = document.querySelector('article') || document.querySelector('main') || document.body;
            const scrollables = Array.from(container.querySelectorAll('ul, div')).filter(
                el => el.scrollHeight > el.clientHeight + 50 && el.clientHeight > 80
            );
            for (const el of scrollables) {
                el.scrollTop = el.scrollHeight;
                el.dispatchEvent(new Event('scroll', { bubbles: true }));
            }
        }""")
        await page.wait_for_timeout(1000)

    # 3. Extracción de comentarios
    comentarios = await page.evaluate(r"""(targetUser) => {
        const results = [];
        const container = document.querySelector('article') || document.querySelector('main') || document.body;
        if (!container) return results;

        // Estrategia A: Filas con botones de Reply / Responder
        const replyButtons = Array.from(container.querySelectorAll('button, span')).filter(
            b => /^(Reply|Responder)$/i.test((b.innerText || '').trim())
        );

        for (const rBtn of replyButtons) {
            let parent = rBtn.parentElement;
            let row = null;
            for (let step = 0; step < 6; step++) {
                if (!parent) break;
                const links = parent.querySelectorAll('a[href]');
                if (links.length >= 1) {
                    row = parent;
                    break;
                }
                parent = parent.parentElement;
            }

            if (row) {
                const link = row.querySelector('a[href]');
                const u = link ? link.getAttribute('href').replaceAll('/', '').trim() : '';
                const spans = Array.from(row.querySelectorAll('span')).map(s => (s.innerText || '').trim()).filter(Boolean);
                let commentText = '';
                for (const s of spans) {
                    if (s !== u && !/^(Reply|Responder|\d+[smhdw]|See translation|Ver traducción|Editado|Edited)$/i.test(s) && s.length > commentText.length) {
                        commentText = s;
                    }
                }
                if (u && commentText && u.toLowerCase() !== targetUser.toLowerCase()) {
                    if (!results.some(c => c.usuario === u && c.texto === commentText)) {
                        results.push({ usuario: u, texto: commentText });
                    }
                }
            }
        }

        // Estrategia B: Buscar en items <ul> <li>
        if (results.length === 0) {
            const items = container.querySelectorAll('ul li');
            for (const item of items) {
                const link = item.querySelector('a[href]');
                if (!link) continue;
                const href = link.getAttribute('href') || '';
                const uname = href.replaceAll('/', '').trim();
                if (!uname || uname.toLowerCase() === targetUser.toLowerCase()) continue;

                const spans = item.querySelectorAll('span');
                let text = '';
                for (const span of spans) {
                    if (span.closest('button, time, nav')) continue;
                    const t = span.textContent.trim();
                    if (t && t !== uname && t.length > 2 && !/^\d+[smhdw]?$/.test(t) && !/^(Responder|Reply|Me gusta|Like|Editado|Edited)$/i.test(t)) {
                        if (t.length > text.length) text = t;
                    }
                }
                if (text && !results.some(c => c.usuario === uname && c.texto === text)) {
                    results.push({ usuario: uname, texto: text });
                }
            }
        }

        return results;
    }""", target_user)

    if max_comments > 0 and len(comentarios) > max_comments:
        comentarios = comentarios[:max_comments]

    return comentarios


# ─────────────────────────────────────────────────────────
# Extracción de detalle de un post individual
# ─────────────────────────────────────────────────────────
async def extraer_detalle_post(
    page,
    post_path,
    indice,
    total,
    scrape_comments=True,
    max_comments=0,
    target_user="",
):
    """Navega a un post y extrae caption, likes, fecha y opcionalmente comentarios."""
    url = f"https://www.instagram.com{post_path}"
    print(f"\n  [{indice}/{total}] Extrayendo: {post_path}")

    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        await descartar_popups(page)

        # Esperar a que el contenido del post cargue (main, article o time)
        try:
            await page.wait_for_selector("main, article, time", timeout=8000)
        except Exception:
            pass

        # ── Caption y Likes ──
        datos = await page.evaluate(
            r"""(targetUser) => {
            const container = document.querySelector('article') || document.querySelector('main') || document.body;
            const text = container.innerText || '';

            // 1. Likes
            let likes = 0;
            const likedByMatch = text.match(/(?:Liked by|Les gusta a)\s+([^\n]+)/i);
            if (likedByMatch) {
                const othersMatch = likedByMatch[1].match(/(\d+[\d.,]*)\s+(?:others|m[aá]s|personas)/i);
                if (othersMatch) {
                    likes = parseInt(othersMatch[1].replace(/[.,]/g, '')) + 1;
                } else {
                    likes = 1;
                }
            }
            if (!likes) {
                const directLikes = text.match(/(\d+[\d.,]*)\s+(?:likes|Me gusta)/i);
                if (directLikes) {
                    likes = parseInt(directLikes[1].replace(/[.,]/g, ''));
                }
            }
            if (!likes) {
                const numMatch = text.match(/\n(\d+)\n(?:[A-Z][a-z]+ \d{1,2}, \d{4}|\d{1,2} de [a-z]+ de \d{4})/i);
                if (numMatch) {
                    likes = parseInt(numMatch[1]);
                }
            }

            // 2. Fecha
            let fecha = '';
            const timeEl = container.querySelector('time[datetime]');
            if (timeEl) {
                fecha = timeEl.getAttribute('datetime') || timeEl.innerText;
            }
            if (!fecha) {
                const dateMatch = text.match(/(?:[A-Z][a-z]+ \d{1,2}, \d{4}|\d{1,2} de [a-z]+ de \d{4})/i);
                if (dateMatch) fecha = dateMatch[0];
            }

            // 3. Caption
            const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
            const profileLinks = Array.from(container.querySelectorAll('a[href]'))
                .map(a => a.getAttribute('href'))
                .filter(h => h && /^\/[a-zA-Z0-9_.]+\/?$/.test(h) && !h.startsWith('/p/') && !h.startsWith('/explore/'))
                .map(h => h.replaceAll('/', '').trim().toLowerCase());

            let caption = '';
            let postAuthorIdx = -1;
            for (let i = 0; i < lines.length; i++) {
                if (lines[i].toLowerCase() === targetUser.toLowerCase()) {
                    for (let j = i + 1; j < lines.length; j++) {
                        if (lines[j].toLowerCase() === targetUser.toLowerCase()) {
                            postAuthorIdx = j;
                            break;
                        }
                    }
                    if (postAuthorIdx === -1) postAuthorIdx = i;
                    break;
                }
            }

            let currentIdx = postAuthorIdx + 1;
            const isRelativeTime = (str) => /^\d+\s*(?:sem|semanas?|d|d[ií]as?|h|horas?|min|m|s|seg|w|weeks?|y|a[ñn]os?)$/i.test(str);
            const isSeparator = (str) => /^[·•?•\s]+$/.test(str);

            while (currentIdx < lines.length && (isRelativeTime(lines[currentIdx]) || isSeparator(lines[currentIdx]))) {
                currentIdx++;
            }

            if (currentIdx < lines.length) {
                const candidate = lines[currentIdx];
                const isUI = /^(Ver traducci[oó]n|See translation|Original audio|Audio original|\d+ (?:likes|Me gusta)|Liked by|Les gusta a|Responder|Reply)$/i.test(candidate);
                const isUser = profileLinks.includes(candidate.toLowerCase());
                if (!isUI && (!isUser || candidate.toLowerCase() === targetUser.toLowerCase())) {
                    caption = candidate;
                }
            }

            // Fallback para caption multilínea
            if (!caption && postAuthorIdx !== -1) {
                let parts = [];
                for (let k = postAuthorIdx + 1; k < lines.length; k++) {
                    const l = lines[k];
                    if (isRelativeTime(l) || isSeparator(l)) continue;
                    if (/^(Ver traducci[oó]n|See translation|Original audio|Audio original|\d+ (?:likes|Me gusta)|Liked by|Les gusta a|Responder|Reply|Add a comment|Añade un comentario)/i.test(l)) break;
                    if (profileLinks.includes(l.toLowerCase()) && l.toLowerCase() !== targetUser.toLowerCase()) break;
                    parts.push(l);
                }
                caption = parts.join('\n').trim();
            }

            return { likes, fecha, caption };
        }""", target_user
        )

        likes = datos.get("likes", 0)
        fecha = datos.get("fecha", "")
        caption = datos.get("caption", "")

        # ── Imágenes y multimedia ──
        media_info = await page.evaluate(
            r"""(targetUser) => {
            const container = document.querySelector('article') || document.querySelector('main') || document.body;
            if (!container) return { tipo: 'image', imagen_url: '', imagenes: [], video_url: '', alt_texto: '', expected_slides: 0, has_next: false };

            // 1. Video o Reel (verificar que no sea de la sección de recomendaciones)
            const video = container.querySelector('video');
            if (video && !video.closest('a[href*="/p/"], a[href*="/reel/"]')) {
                const poster = video.getAttribute('poster') || '';
                const src = video.getAttribute('src') || video.querySelector('source')?.getAttribute('src') || '';
                return {
                    tipo: 'video',
                    imagen_url: poster,
                    imagenes: poster ? [poster] : [],
                    video_url: src,
                    alt_texto: 'Video / Reel de publicación',
                    expected_slides: 1,
                    has_next: false,
                };
            }

            // 2. Extraer imágenes del post actual EXCLUYENDO 'Más publicaciones' y avatares
            const imgs = Array.from(container.querySelectorAll('img')).filter(img => {
                // Descartar imágenes de 'Más publicaciones de...' (vienen dentro de links a otros posts)
                if (img.closest('a[href*="/p/"], a[href*="/reel/"]')) return false;

                // Descartar cabecera y avatares
                if (img.closest('header')) return false;
                const rect = img.getBoundingClientRect();
                if (rect.width > 0 && (rect.width < 120 || rect.height < 120)) return false;

                const alt = (img.getAttribute('alt') || '').toLowerCase();
                if (alt.includes('avatar') || alt.includes('profile picture') || alt.includes('foto del perfil')) return false;

                const src = img.getAttribute('src') || img.src || '';
                if (!src || !src.startsWith('http') || src.includes('data:image')) return false;
                return true;
            });

            // 3. Indicador nativo de carrusel (dots) y contenedor de diapositivas
            const dotContainer = Array.from(container.querySelectorAll('div')).find(d => {
                const ch = Array.from(d.children);
                return ch.length >= 2 && ch.length <= 10 && ch.every(c => c.tagName === 'DIV' && c.clientWidth < 15 && c.clientHeight < 15);
            });
            const expected_slides = dotContainer ? dotContainer.children.length : 0;

            const carouselUl = Array.from(container.querySelectorAll('ul')).find(ul => 
                !ul.closest('a[href*="/p/"]') && ul.querySelectorAll('li img').length > 0
            );

            const nextBtn = Array.from(container.querySelectorAll('button')).find(btn => {
                const label = (btn.getAttribute('aria-label') || '').trim();
                return /^(Siguiente|Next)$/i.test(label) && !btn.closest('a[href*="/p/"]');
            });

            const isCarousel = expected_slides > 1 || !!carouselUl || !!nextBtn;

            const urls = [];
            let mainAlt = '';
            for (const img of imgs) {
                const src = img.getAttribute('src') || img.src || '';
                if (src && !urls.includes(src)) {
                    urls.push(src);
                    if (!mainAlt && img.getAttribute('alt')) {
                        mainAlt = img.getAttribute('alt');
                    }
                }
            }

            return {
                tipo: isCarousel ? 'carousel' : 'image',
                imagen_url: urls[0] || '',
                imagenes: urls,
                video_url: '',
                alt_texto: mainAlt,
                expected_slides: expected_slides,
                has_next: !!nextBtn,
            };
        }""", target_user
        )

        # Si es carrusel real y tiene botón siguiente, avanzar hasta el conteo exacto de fotos
        if media_info.get("tipo") == "carousel" and media_info.get("has_next"):
            imgs_set = list(media_info.get("imagenes", []))
            exp_slides = media_info.get("expected_slides", 0)
            base_url = url.split("?")[0]
            max_clicks = exp_slides if exp_slides > 0 else 10

            for _ in range(max_clicks):
                if exp_slides > 0 and len(imgs_set) >= exp_slides:
                    break
                btn_next = page.locator("button[aria-label='Siguiente'], button[aria-label='Next']").first
                if await btn_next.is_visible(timeout=800):
                    # Salvaguarda: si la URL base cambió, no interactuar más
                    if page.url.split("?")[0] != base_url:
                        break
                    try:
                        await btn_next.click()
                        await page.wait_for_timeout(600)
                        nuevas_urls = await page.evaluate(r"""() => {
                            const container = document.querySelector('article') || document.querySelector('main') || document.body;
                            return Array.from(container.querySelectorAll('img'))
                                .filter(img => {
                                    if (img.closest('a[href*="/p/"], a[href*="/reel/"]')) return false;
                                    if (img.closest('header')) return false;
                                    const rect = img.getBoundingClientRect();
                                    if (rect.width > 0 && (rect.width < 120 || rect.height < 120)) return false;
                                    const src = img.getAttribute('src') || img.src || '';
                                    return src.startsWith('http') && !src.includes('data:image');
                                })
                                .map(i => i.getAttribute('src') || i.src || '')
                                .filter(Boolean);
                        }""")
                        for u in nuevas_urls:
                            if u not in imgs_set:
                                imgs_set.append(u)
                                if exp_slides > 0 and len(imgs_set) >= exp_slides:
                                    break
                    except Exception:
                        break
                else:
                    break

            if exp_slides > 0 and len(imgs_set) > exp_slides:
                imgs_set = imgs_set[:exp_slides]
            media_info["imagenes"] = imgs_set

        # ── Comentarios condicionales ──
        if scrape_comments:
            comentarios = await extraer_comentarios_post(
                page, max_comments=max_comments, target_user=target_user
            )
        else:
            comentarios = []

        # ── Hashtags y Menciones ──
        hashtags = extraer_hashtags(caption)
        menciones = extraer_menciones(caption)

        preview = caption[:70].replace("\n", " ") + ("..." if len(caption) > 70 else "")
        tipo_lbl = media_info.get("tipo", "image")
        num_imgs = len(media_info.get("imagenes", []))
        media_txt = f"🖼️ {tipo_lbl} ({num_imgs} img)" if media_info.get("imagen_url") else "🖼️ Sin imagen"
        info_cmts = f"💬 {len(comentarios)}" if scrape_comments else "💬 Omitidos"
        print(f"    Caption: {preview}")
        print(f"    ❤️ {likes} | 📅 {fecha[:10] if fecha else 'N/A'} | {info_cmts} | {media_txt}")

        return {
            "url": url,
            "caption": caption,
            "hashtags": hashtags,
            "menciones": menciones,
            "likes": likes,
            "fecha": fecha,
            "tipo_media": media_info.get("tipo", "image"),
            "imagen_url": media_info.get("imagen_url", ""),
            "imagenes": media_info.get("imagenes", []),
            "video_url": media_info.get("video_url", ""),
            "alt_texto": media_info.get("alt_texto", ""),
            "total_comentarios": len(comentarios),
            "comentarios": comentarios,
        }

    except Exception as e:
        print(f"    [ERROR] {e}")
        return None


# ─────────────────────────────────────────────────────────
# Funciones de exportación
# ─────────────────────────────────────────────────────────
def exportar_json(resultado, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=4, ensure_ascii=False)
    print(f"[EXPORTACIÓN] JSON generado: {filename}")


def exportar_csv_relaciones(seguidos, seguidores, filename):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["tipo", "username"])
        for u in seguidos:
            writer.writerow(["seguido", u])
        for u in seguidores:
            writer.writerow(["seguidor", u])
    print(f"[EXPORTACIÓN] CSV relaciones: {filename}")


def exportar_csv_publicaciones(publicaciones, filename):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "indice",
            "url",
            "fecha",
            "tipo_media",
            "imagen_url",
            "likes",
            "hashtags",
            "menciones",
            "total_comentarios",
            "alt_texto",
            "caption",
        ])
        for i, post in enumerate(publicaciones, 1):
            writer.writerow([
                i,
                post.get("url", ""),
                post.get("fecha", ""),
                post.get("tipo_media", "image"),
                post.get("imagen_url", ""),
                post.get("likes", 0),
                "; ".join(post.get("hashtags", [])),
                "; ".join(post.get("menciones", [])),
                post.get("total_comentarios", 0),
                post.get("alt_texto", ""),
                post.get("caption", ""),
            ])
    print(f"[EXPORTACIÓN] CSV publicaciones: {filename}")


def exportar_csv_comentarios(publicaciones, filename):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["post_indice", "post_url", "usuario", "comentario"])
        for i, post in enumerate(publicaciones, 1):
            for com in post.get("comentarios", []):
                writer.writerow([i, post["url"], com["usuario"], com["texto"]])
    print(f"[EXPORTACIÓN] CSV comentarios: {filename}")


# ─────────────────────────────────────────────────────────
# Flujo principal
# ─────────────────────────────────────────────────────────
async def run(config=None):
    if config is None:
        config = ScraperConfig.from_env_and_cli()

    config.print_banner()
    t_start = time_module.time()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=config.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )

        # Inyección de credenciales mediante cookies
        await context.add_cookies([
            {
                "name": "sessionid",
                "value": config.session_id,
                "domain": ".instagram.com",
                "path": "/",
            },
            {
                "name": "ds_user_id",
                "value": config.ds_user_id,
                "domain": ".instagram.com",
                "path": "/",
            },
        ])

        page = await context.new_page()
        profile_url = f"https://www.instagram.com/{config.target_user}/"
        print(f"\n🔗 Conectando al perfil: {profile_url}")
        await page.goto(profile_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        await descartar_popups(page)
        await page.wait_for_selector("header", timeout=15000)

        # ── 1. Metadatos de cabecera ──
        header_text = await page.locator("header").inner_text()
        lines = [line.strip() for line in header_text.splitlines() if line.strip()]

        m_posts = re.search(
            r"([\d.,kKmM]+)\s+publicaci\w*", header_text, re.IGNORECASE
        )
        m_followers = re.search(
            r"([\d.,kKmM]+)\s+seguidores", header_text, re.IGNORECASE
        )
        m_following = re.search(
            r"([\d.,kKmM]+)\s+seguidos", header_text, re.IGNORECASE
        )

        posts_num = parsear_numero(m_posts.group(0)) if m_posts else 0
        followers_num = parsear_numero(m_followers.group(0)) if m_followers else 0
        following_num = parsear_numero(m_following.group(0)) if m_following else 0

        # Biografía
        bio_lines = []
        capture = False
        for line in lines:
            if re.search(r"seguidos", line, re.IGNORECASE):
                capture = True
                continue
            if capture and line in [
                "Seguir", "Siguiendo", "Enviar mensaje",
                "Editar perfil", "Contactar", "Mensaje",
            ]:
                break
            if capture:
                bio_lines.append(line)

        print("\n--- Metadatos del Perfil ---")
        print(f"  Publicaciones: {posts_num}")
        print(f"  Seguidores:    {followers_num}")
        print(f"  Seguidos:      {following_num}")
        print(f"  Biografía:     {' | '.join(bio_lines)}")

        # ── 1.1 Foto de perfil (URL y descarga local) ──
        foto_perfil_url = ""
        try:
            foto_perfil_url = await page.evaluate(r"""() => {
                const header = document.querySelector('header');
                if (!header) return '';
                const img = header.querySelector("img[alt*='perfil'], img[alt*='profile'], img");
                return img ? (img.getAttribute('src') || img.src || '') : '';
            }""")
        except Exception:
            pass

        foto_perfil_local = ""
        if foto_perfil_url:
            print(f"\n🖼️  Foto de perfil detectada.")
            try:
                avatar_resp = await context.request.get(foto_perfil_url)
                if avatar_resp.status == 200:
                    avatar_filename = f"{config.target_user}_avatar.jpg"
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    avatar_path = os.path.join(script_dir, avatar_filename)
                    with open(avatar_path, "wb") as f:
                        f.write(await avatar_resp.body())
                    foto_perfil_local = avatar_filename
                    print(f"    ✅ Avatar descargado localmente: {avatar_filename}")
                else:
                    print(f"    [AVISO] No se pudo descargar avatar (HTTP {avatar_resp.status})")
            except Exception as err:
                print(f"    [AVISO] Error al descargar foto de perfil: {err}")

        # ── 2. Seguidores y Seguidos (Módulos opcionales) ──
        seguidos = []
        if config.scrape_following:
            seguidos = await extraer_relaciones(
                page,
                tipo="following",
                meta=following_num,
                limit=config.max_following,
            )
            await page.wait_for_timeout(2500)
        else:
            print("\n[MÓDULO] Extracción de seguidos omitida por configuración.")

        seguidores = []
        if config.scrape_followers:
            seguidores = await extraer_relaciones(
                page,
                tipo="followers",
                meta=followers_num,
                limit=config.max_followers,
            )
        else:
            print("\n[MÓDULO] Extracción de seguidores omitida por configuración.")

        # ── 3. Publicaciones (Módulo opcional) ──
        publicaciones = []
        if config.scrape_posts:
            # Si se interactuó con modales de relaciones, volver a la vista del perfil
            if config.scrape_following or config.scrape_followers:
                await page.goto(profile_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                await descartar_popups(page)

            post_urls = await recolectar_urls_posts(
                page, meta_posts=posts_num, max_posts=config.max_posts
            )

            for i, post_path in enumerate(post_urls, 1):
                post_data = await extraer_detalle_post(
                    page,
                    post_path,
                    i,
                    len(post_urls),
                    scrape_comments=config.scrape_comments,
                    max_comments=config.max_comments_per_post,
                    target_user=config.target_user,
                )
                if post_data:
                    publicaciones.append(post_data)

                # Estimación de tiempo tras el primer post
                if i == 1:
                    elapsed = time_module.time() - t_start
                    est_min = (elapsed * len(post_urls)) / 60
                    print(f"\n    ⏱️  Estimación restante: ~{est_min:.1f} min para {len(post_urls)} posts")

                await pausa_humana(page, 2.0, 4.0)
        else:
            print("\n[MÓDULO] Extracción de publicaciones omitida por configuración.")

        # ── 4. Exportaciones ──
        print("\n==========================================")
        print(" Exportando datos...")
        print("==========================================")

        # Ocultar credenciales de la configuración guardada
        safe_config = asdict(config)
        safe_config.pop("session_id", None)
        safe_config.pop("ds_user_id", None)

        resultado = {
            "perfil": config.target_user,
            "foto_perfil_url": foto_perfil_url,
            "foto_perfil_local": foto_perfil_local,
            "biografia": "\n".join(bio_lines),
            "publicaciones_count": posts_num,
            "total_seguidores": followers_num,
            "total_seguidos": following_num,
            "seguidores_recolectados": len(seguidores),
            "seguidos_recolectados": len(seguidos),
            "posts_recolectados": len(publicaciones),
            "configuracion": safe_config,
            "seguidores": seguidores,
            "seguidos": seguidos,
            "publicaciones": publicaciones,
        }

        exportar_json(resultado, f"{config.target_user}_datos.json")

        if config.scrape_following or config.scrape_followers:
            exportar_csv_relaciones(seguidos, seguidores, f"{config.target_user}_relaciones.csv")

        if config.scrape_posts and len(publicaciones) > 0:
            exportar_csv_publicaciones(publicaciones, f"{config.target_user}_publicaciones.csv")
            if config.scrape_comments and any(p.get("comentarios") for p in publicaciones):
                exportar_csv_comentarios(publicaciones, f"{config.target_user}_comentarios.csv")

        await browser.close()

    t_total = time_module.time() - t_start
    print(f"\n✅ Scraping completado en {t_total / 60:.1f} minutos.")
    print(f"   Abre dashboard.html y carga {config.target_user}_datos.json para visualizar.")


if __name__ == "__main__":
    try:
        cfg = ScraperConfig.from_env_and_cli()
        asyncio.run(run(cfg))
    except KeyboardInterrupt:
        print("\n\n[AVISO] Ejecución interrumpida por el usuario.")
    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")