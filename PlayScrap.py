import asyncio
import csv
import json
import os
import random
import re
import time as time_module
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# ─────────────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────────────
load_dotenv()

TARGET_USER = os.getenv("TARGET_USER", "sausage_player")
SESSION_ID = os.getenv("IG_SESSION_ID")
DS_USER_ID = os.getenv("IG_DS_USER_ID")
MAX_POSTS = int(os.getenv("MAX_POSTS", "0"))  # 0 = sin límite

if not SESSION_ID or not DS_USER_ID:
    raise ValueError(
        "Las variables de entorno IG_SESSION_ID o IG_DS_USER_ID no están definidas. "
        "Verifica tu archivo .env local."
    )


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
async def extraer_relaciones(page, tipo="following", meta=0):
    texto_es = "seguidos" if tipo == "following" else "seguidores"
    print(f"\n==========================================")
    print(f" Extrayendo {tipo} ({meta} registrados en cabecera)")
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

        if meta > 0 and total_actual >= meta:
            print(f"[COMPLETADO] Se alcanzó la meta total: {total_actual}/{meta}")
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
    print(f"Fase {tipo} finalizada. Total obtenido: {len(usuarios)}")
    return list(usuarios)


# ─────────────────────────────────────────────────────────
# Recolección de URLs de publicaciones (grid del perfil)
# ─────────────────────────────────────────────────────────
async def recolectar_urls_posts(page, meta_posts=0):
    """Scrollea la página del perfil para cargar y recoger los enlaces de cada post."""
    print("\n==========================================")
    print(" Recolectando URLs de publicaciones...")
    print("==========================================")

    urls = set()
    intentos = 0
    MAX_INTENTOS = 4

    while intentos < MAX_INTENTOS:
        nuevas = set(
            await page.locator("a[href*='/p/'], a[href*='/reel/']").evaluate_all(
                "els => els.map(e => e.getAttribute('href')).filter(Boolean)"
            )
        )

        prev = len(urls)
        urls.update(nuevas)

        limite = MAX_POSTS if MAX_POSTS > 0 else meta_posts
        if limite > 0 and len(urls) >= limite:
            print(f"[GRID] Meta alcanzada: {len(urls)}/{limite}")
            break

        if len(urls) > prev:
            intentos = 0
            print(f"[GRID] {len(urls)} publicaciones encontradas...")
        else:
            intentos += 1
            print(f"  Sin posts nuevos ({intentos}/{MAX_INTENTOS})...")

        await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        await pausa_humana(page, 1.5, 2.5)

    result = sorted(list(urls))
    if MAX_POSTS > 0:
        result = result[:MAX_POSTS]

    print(f"[GRID] Total URLs recolectadas: {len(result)}")
    return result


# ─────────────────────────────────────────────────────────
# Extracción de comentarios dentro de un post
# ─────────────────────────────────────────────────────────
async def extraer_comentarios_post(page):
    """Expande y extrae todos los comentarios del post actual."""

    # 1. Intentar abrir la vista completa de comentarios
    for selector in [
        "span:has-text('Ver todos')",
        "span:has-text('View all')",
        "span:has-text('Ver los')",
        "a:has-text('View all')",
        "a:has-text('Ver todos')",
    ]:
        try:
            el = page.locator(selector).first
            if await el.is_visible(timeout=2000):
                await el.click()
                await pausa_humana(page, 2.0, 3.0)
                break
        except Exception:
            pass

    # 2. Scroll iterativo + expansión de respuestas
    prev_count = 0
    intentos = 0
    MAX_INTENTOS_SCROLL = 3

    for _ in range(40):
        # Botones "Cargar más comentarios"
        for sel in [
            "button:has-text('más comentarios')",
            "button:has-text('more comments')",
        ]:
            try:
                btns = page.locator(sel)
                for i in range(await btns.count()):
                    try:
                        b = btns.nth(i)
                        if await b.is_visible(timeout=500):
                            await b.click()
                            await pausa_humana(page, 1.0, 2.0)
                    except Exception:
                        pass
            except Exception:
                pass

        # Botones "Ver respuestas"
        for sel in [
            "button:has-text('Ver respuestas')",
            "button:has-text('View replies')",
            "button:has-text('Ver más respuestas')",
            "button:has-text('View more replies')",
        ]:
            try:
                btns = page.locator(sel)
                cnt = await btns.count()
                for i in range(min(cnt, 5)):
                    try:
                        b = btns.nth(i)
                        if await b.is_visible(timeout=500):
                            await b.click()
                            await pausa_humana(page, 0.8, 1.5)
                    except Exception:
                        pass
            except Exception:
                pass

        # Scroll del contenedor de comentarios
        await page.evaluate(
            r"""() => {
            const article = document.querySelector('article');
            if (!article) return;
            const scrollables = Array.from(article.querySelectorAll('ul, div')).filter(
                el => el.scrollHeight > el.clientHeight + 50 && el.clientHeight > 80
            );
            for (const el of scrollables) {
                el.scrollTop = el.scrollHeight;
                el.dispatchEvent(new Event('scroll', { bubbles: true }));
            }
        }"""
        )

        await pausa_humana(page, 1.0, 1.8)

        cur = await page.evaluate(
            r"""() => {
            const article = document.querySelector('article');
            return article ? article.querySelectorAll('ul li a[href]').length : 0;
        }"""
        )

        if cur > prev_count:
            prev_count = cur
            intentos = 0
        else:
            intentos += 1
            if intentos >= MAX_INTENTOS_SCROLL:
                break

    # 3. Extracción final de comentarios
    comentarios = await page.evaluate(
        r"""(targetUser) => {
        const results = [];
        const seen = new Set();
        const article = document.querySelector('article');
        if (!article) return results;

        const items = article.querySelectorAll('ul li');
        let isFirstByAuthor = true;

        for (const item of items) {
            // Buscar enlace de usuario
            const links = item.querySelectorAll('a[href]');
            let username = '';
            for (const link of links) {
                const href = link.getAttribute('href');
                if (href && /^\/[\w.]+\/?$/.test(href)) {
                    username = href.replaceAll('/', '');
                    break;
                }
            }
            if (!username) continue;

            // Buscar texto del comentario en spans (omitir botones, timestamps)
            const spans = item.querySelectorAll('span');
            let text = '';
            for (const span of spans) {
                if (span.closest('button, time, nav')) continue;
                const t = span.textContent.trim();
                if (t && t !== username && t.length > 2
                    && !/^\d+[smhdw]?$/.test(t)
                    && !/^(Responder|Reply|Me gusta|Like|Editado|Edited|Ver|View|Ocultar)$/i.test(t)
                    && !t.includes('Ver respuestas')
                    && !t.includes('View replies')) {
                    if (t.length > text.length) text = t;
                }
            }
            if (!text) continue;

            // Omitir el primer bloque del autor (es el caption, no un comentario)
            if (isFirstByAuthor && username.toLowerCase() === targetUser.toLowerCase()) {
                isFirstByAuthor = false;
                continue;
            }

            const key = username + '::' + text.substring(0, 60);
            if (!seen.has(key)) {
                seen.add(key);
                results.push({ usuario: username, texto: text });
            }
        }
        return results;
    }""",
        TARGET_USER,
    )

    return comentarios


# ─────────────────────────────────────────────────────────
# Extracción de detalle de un post individual
# ─────────────────────────────────────────────────────────
async def extraer_detalle_post(page, post_path, indice, total):
    """Navega a un post y extrae caption, likes, fecha y comentarios."""
    url = f"https://www.instagram.com{post_path}"
    print(f"\n  [{indice}/{total}] Extrayendo: {post_path}")

    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)
        await descartar_popups(page)
        await page.wait_for_selector("article", timeout=10000)

        # ── Caption y Likes ──
        datos = await page.evaluate(
            r"""(targetUser) => {
            const article = document.querySelector('article');
            if (!article) return { caption: '', likes: 0 };

            // Caption: buscar en h1 primero
            let caption = '';
            const h1 = article.querySelector('h1');
            if (h1 && h1.textContent.trim()) {
                caption = h1.textContent.trim();
            }

            // Fallback: buscar primer bloque del autor del post
            if (!caption) {
                const items = article.querySelectorAll('ul li, ul > div');
                for (const item of items) {
                    const link = item.querySelector('a[href]');
                    if (!link) continue;
                    const href = link.getAttribute('href');
                    if (!href || !href.startsWith('/')) continue;
                    const uname = href.replaceAll('/', '');
                    if (uname.toLowerCase() === targetUser.toLowerCase()) {
                        const spans = item.querySelectorAll('span');
                        for (const span of spans) {
                            const t = span.textContent.trim();
                            if (t && t !== uname && t.length > caption.length) {
                                caption = t;
                            }
                        }
                        break;
                    }
                }
            }

            // Likes
            let likes = 0;
            const allText = article.innerText;
            let match = allText.match(/([\d.,]+)\s*(?:likes?|Me gusta)/i);
            if (match) {
                likes = parseInt(match[1].replace(/[.,]/g, ''));
            } else {
                match = allText.match(/([\d.,]+)\s*(?:others|personas más)/i);
                if (match) likes = parseInt(match[1].replace(/[.,]/g, ''));
            }

            return { caption, likes };
        }""",
            TARGET_USER,
        )

        caption = datos.get("caption", "")
        likes = datos.get("likes", 0)

        # ── Fecha ──
        fecha = ""
        try:
            time_els = page.locator("time[datetime]")
            if await time_els.count() > 0:
                fecha = await time_els.first.get_attribute("datetime") or ""
        except Exception:
            pass

        # ── Comentarios ──
        comentarios = await extraer_comentarios_post(page)

        # ── Hashtags y Menciones ──
        hashtags = extraer_hashtags(caption)
        menciones = extraer_menciones(caption)

        preview = caption[:70] + ("..." if len(caption) > 70 else "")
        print(f"    Caption: {preview}")
        print(
            f"    ❤️ {likes} | 📅 {fecha[:10] if fecha else 'N/A'} | 💬 {len(comentarios)}"
        )

        return {
            "url": url,
            "caption": caption,
            "hashtags": hashtags,
            "menciones": menciones,
            "likes": likes,
            "fecha": fecha,
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
        writer.writerow(
            ["indice", "url", "fecha", "likes", "hashtags", "menciones", "num_comentarios", "caption"]
        )
        for i, post in enumerate(publicaciones, 1):
            writer.writerow([
                i,
                post["url"],
                post["fecha"],
                post["likes"],
                "; ".join(post["hashtags"]),
                "; ".join(post["menciones"]),
                post["total_comentarios"],
                post["caption"],
            ])
    print(f"[EXPORTACIÓN] CSV publicaciones: {filename}")


def exportar_csv_comentarios(publicaciones, filename):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["post_indice", "post_url", "usuario", "comentario"])
        for i, post in enumerate(publicaciones, 1):
            for com in post["comentarios"]:
                writer.writerow([i, post["url"], com["usuario"], com["texto"]])
    print(f"[EXPORTACIÓN] CSV comentarios: {filename}")


# ─────────────────────────────────────────────────────────
# Flujo principal
# ─────────────────────────────────────────────────────────
async def run():
    t_start = time_module.time()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
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
                "value": SESSION_ID,
                "domain": ".instagram.com",
                "path": "/",
            },
            {
                "name": "ds_user_id",
                "value": DS_USER_ID,
                "domain": ".instagram.com",
                "path": "/",
            },
        ])

        page = await context.new_page()
        profile_url = f"https://www.instagram.com/{TARGET_USER}/"
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

        # ── 2. Seguidores y Seguidos ──
        seguidos = await extraer_relaciones(page, tipo="following", meta=following_num)
        await page.wait_for_timeout(2500)
        seguidores = await extraer_relaciones(page, tipo="followers", meta=followers_num)

        # ── 3. Publicaciones ──
        # Volver al perfil para escanear el grid de posts
        await page.goto(profile_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        await descartar_popups(page)

        post_urls = await recolectar_urls_posts(page, meta_posts=posts_num)

        publicaciones = []
        for i, post_path in enumerate(post_urls, 1):
            post_data = await extraer_detalle_post(page, post_path, i, len(post_urls))
            if post_data:
                publicaciones.append(post_data)

            # Estimación de tiempo tras el primer post
            if i == 1:
                elapsed = time_module.time() - t_start
                est_min = (elapsed * len(post_urls)) / 60
                print(f"\n    ⏱️  Estimación total: ~{est_min:.1f} min para {len(post_urls)} posts")

            await pausa_humana(page, 2.0, 4.0)

        # ── 4. Exportaciones ──
        print("\n==========================================")
        print(" Exportando datos...")
        print("==========================================")

        resultado = {
            "perfil": TARGET_USER,
            "biografia": "\n".join(bio_lines),
            "publicaciones_count": posts_num,
            "total_seguidores": followers_num,
            "total_seguidos": following_num,
            "seguidores_recolectados": len(seguidores),
            "seguidos_recolectados": len(seguidos),
            "posts_recolectados": len(publicaciones),
            "seguidores": seguidores,
            "seguidos": seguidos,
            "publicaciones": publicaciones,
        }

        exportar_json(resultado, f"{TARGET_USER}_datos.json")
        exportar_csv_relaciones(seguidos, seguidores, f"{TARGET_USER}_relaciones.csv")
        exportar_csv_publicaciones(publicaciones, f"{TARGET_USER}_publicaciones.csv")
        exportar_csv_comentarios(publicaciones, f"{TARGET_USER}_comentarios.csv")

        await browser.close()

    t_total = time_module.time() - t_start
    print(f"\n✅ Scraping completado en {t_total / 60:.1f} minutos.")
    print(f"   Abre dashboard.html y carga {TARGET_USER}_datos.json para visualizar.")


if __name__ == "__main__":
    asyncio.run(run())