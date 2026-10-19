import asyncio
import csv
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
    for _ in range(3):
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
    }""", TARGET_USER)

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
            if (postAuthorIdx !== -1 && currentIdx < lines.length) {
                while (currentIdx < lines.length && (/^\d+[smhdw]$/i.test(lines[currentIdx]) || lines[currentIdx] === '·' || lines[currentIdx] === '•' || lines[currentIdx] === '?')) {
                    currentIdx++;
                }

                const captionLines = [];
                while (currentIdx < lines.length) {
                    const line = lines[currentIdx];
                    if (/^(No comments yet|Aún no hay comentarios|View all \d+ comments|Ver los \d+ comentarios|Start the conversation|Inicia la conversación|Liked by|Les gusta a|\d+\s+likes|\d+\s+Me gusta|Reply|Responder|More posts from|Más publicaciones de)/i.test(line)) {
                        break;
                    }
                    if (timeEl && (line === timeEl.innerText || line === fecha)) {
                        break;
                    }
                    if (profileLinks.includes(line.toLowerCase()) && line.toLowerCase() !== targetUser.toLowerCase()) {
                        break;
                    }
                    captionLines.push(line);
                    currentIdx++;
                }
                caption = captionLines.join('\n');
            }

            return { caption, likes, fecha };
        }""",
            TARGET_USER,
        )

        caption = datos.get("caption", "")
        likes = datos.get("likes", 0)
        fecha = datos.get("fecha", "")

        # ── Comentarios ──
        comentarios = await extraer_comentarios_post(page)

        # ── Hashtags y Menciones ──
        hashtags = extraer_hashtags(caption)
        menciones = extraer_menciones(caption)

        preview = caption[:70].replace("\n", " ") + ("..." if len(caption) > 70 else "")
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