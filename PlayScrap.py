import asyncio
import csv
import json
import os
import random
import re
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Cargar variables de entorno desde el archivo .env
load_dotenv()

TARGET_USER = os.getenv("TARGET_USER", "sausage_player")
SESSION_ID = os.getenv("IG_SESSION_ID")
DS_USER_ID = os.getenv("IG_DS_USER_ID")

if not SESSION_ID or not DS_USER_ID:
    raise ValueError(
        "Las variables de entorno IG_SESSION_ID o IG_DS_USER_ID no están definidas. "
        "Verifica tu archivo .env local."
    )


def parsear_numero(texto):
    """Extrae el primer número entero de una cadena."""
    if not texto:
        return 0
    limpio = texto.replace(".", "").replace(",", "")
    match = re.search(r"\d+", limpio)
    return int(match.group(0)) if match else 0


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


async def scroll_con_rebote(page):
    """Aplica desplazamiento interno y rebote para forzar el evento scroll del DOM."""
    return await page.evaluate(
        """() => {
        const dialog = document.querySelector("div[role='dialog']");
        if (!dialog) return { found: false, hasSpinner: false };

        const container = Array.from(dialog.querySelectorAll("div")).find(
            el => el.scrollHeight > el.clientHeight && el.clientHeight > 150
        );
        if (!container) return { found: false, hasSpinner: false };

        const hasSpinner = dialog.querySelector("svg circle, div[role='progressbar'], svg[aria-label*='Cargando'], svg[aria-label*='Loading']") !== null;

        const distanciaAlFondo = container.scrollHeight - container.clientHeight - container.scrollTop;
        if (distanciaAlFondo < 25) {
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


async def extraer_relaciones(page, tipo="following", meta=0):
    texto_es = "seguidos" if tipo == "following" else "seguidores"
    print(f"\n==========================================")
    print(f"Extrayendo {tipo} ({meta} registrados en cabecera)")
    print(f"==========================================")

    selector_btn = f"a[href*='/{tipo}/'], a:has-text('{texto_es}'), span:has-text('{texto_es}')"
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
    MAX_INTENTOS = 3  # Se frena tras 3 intentos fallidos para pasar a la siguiente fase

    while intentos_sin_cambio < MAX_INTENTOS:
        nuevos = await dialog.locator("a[role='link']").evaluate_all(
            """elements => {
            const list = [];
            for (const el of elements) {
                const href = el.getAttribute('href');
                if (href && href.startsWith('/') && !href.startsWith('/explore/') && !href.startsWith('/direct/')) {
                    const u = href.replace(/\\//g, '').trim();
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


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )

        # Inyección de credenciales mediante variables seguras
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
        print(f"Conectando al perfil: https://www.instagram.com/{TARGET_USER}/")
        await page.goto(
            f"https://www.instagram.com/{TARGET_USER}/",
            wait_until="domcontentloaded",
        )
        await page.wait_for_timeout(3000)
        await descartar_popups(page)
        await page.wait_for_selector("header", timeout=15000)

        # 1. Extracción de métricas de cabecera
        header_text = await page.locator("header").inner_text()
        lines = [
            line.strip() for line in header_text.splitlines() if line.strip()
        ]

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
        followers_num = (
            parsear_numero(m_followers.group(0)) if m_followers else 0
        )
        following_num = (
            parsear_numero(m_following.group(0)) if m_following else 0
        )

        # Extracción de la Biografía
        bio_lines = []
        capture = False
        for line in lines:
            if re.search(r"seguidos", line, re.IGNORECASE):
                capture = True
                continue
            if capture and line in [
                "Seguir",
                "Siguiendo",
                "Enviar mensaje",
                "Editar perfil",
                "Contactar",
                "Mensaje",
            ]:
                break
            if capture:
                bio_lines.append(line)

        print("\n--- Metadatos del Perfil ---")
        print(f"Publicaciones: {posts_num}")
        print(f"Seguidores:    {followers_num}")
        print(f"Seguidos:      {following_num}")

        # 2. Extracción secuencial
        seguidos = await extraer_relaciones(
            page, tipo="following", meta=following_num
        )
        await page.wait_for_timeout(2500)
        seguidores = await extraer_relaciones(
            page, tipo="followers", meta=followers_num
        )

        # 3. Exportación a JSON
        resultado = {
            "perfil": TARGET_USER,
            "biografia": "\n".join(bio_lines),
            "publicaciones": posts_num,
            "total_seguidores": followers_num,
            "total_seguidos": following_num,
            "seguidores_recolectados": len(seguidores),
            "seguidos_recolectados": len(seguidos),
            "seguidores": seguidores,
            "seguidos": seguidos,
        }

        json_file = f"{TARGET_USER}_datos.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(resultado, f, indent=4, ensure_ascii=False)
        print(f"\n[EXPORTACIÓN] JSON generado: {json_file}")

        # 4. Exportación a CSV
        csv_file = f"{TARGET_USER}_relaciones.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["tipo", "username"])
            for u in seguidos:
                writer.writerow(["seguido", u])
            for u in seguidores:
                writer.writerow(["seguidor", u])
        print(f"[EXPORTACIÓN] CSV generado: {csv_file}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())