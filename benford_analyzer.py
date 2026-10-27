#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analizador Forense de Red con Ley de Benford para Detección de Bots
------------------------------------------------------------------
Analiza las métricas de red (número de seguidores y seguidos) de las cuentas
asociadas a un perfil de Instagram mediante la Ley de Benford (First Significant Digit).

Calcula:
  - Distribución del primer dígito significativo (d ∈ {1..9})
  - Prueba de Chi-cuadrado (χ²) y p-value
  - Desviación Absoluta Media (MAD de Nigrini)
  - Distancia de Kolmogorov-Smirnov (D)
  - Score continuo de Comportamiento Humano / Orgánico (0% a 100%)
  - Reporte interactivo HTML con gráficos dinámicos (Chart.js)
"""

import argparse
import json
import math
import os
import sys
import webbrowser
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

try:
    from scipy.stats import chi2 as scipy_chi2
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# ─────────────────────────────────────────────────────────
# Distribución Teórica de Benford (Dígitos 1 al 9)
# P(d) = log10(1 + 1/d)
# ─────────────────────────────────────────────────────────
BENFORD_THEORETICAL: Dict[int, float] = {
    d: math.log10(1.0 + 1.0 / d) for d in range(1, 10)
}

BENFORD_CDF: Dict[int, float] = {}
_cum = 0.0
for _d in range(1, 10):
    _cum += BENFORD_THEORETICAL[_d]
    BENFORD_CDF[_d] = _cum


# ─────────────────────────────────────────────────────────
# Modelos de Datos Tipados
# ─────────────────────────────────────────────────────────
@dataclass
class BenfordStat:
    nombre: str
    n_total: int
    conteos_observados: Dict[int, int]
    porcentajes_observados: Dict[int, float]
    porcentajes_esperados: Dict[int, float]
    chi2: float
    p_value: float
    mad: float
    ks_distance: float
    human_score: float
    nivel_conformidad: str
    veredicto: str


@dataclass
class BenfordReport:
    perfil: str
    foto_perfil_local: str
    total_seguidores_perfil: int
    total_seguidos_perfil: int
    tipo_red: str
    muestra_analizada: int
    score_global_humano: float
    veredicto_global: str
    stat_seguidores: Optional[BenfordStat]
    stat_seguidos: Optional[BenfordStat]
    cuentas: List[Dict]


# ─────────────────────────────────────────────────────────
# Utilidades Matemáticas y Estadísticas
# ─────────────────────────────────────────────────────────
def extraer_primer_digito(n: int) -> Optional[int]:
    """Obtiene el primer dígito significativo (1-9) de un entero positivo."""
    if n <= 0:
        return None
    s = str(abs(n)).lstrip("0")
    if not s:
        return None
    d = int(s[0])
    return d if 1 <= d <= 9 else None


def chi2_survival_fallback(chi2_val: float, df: int = 8) -> float:
    """
    Aproximación de cola superior (survival function) para Chi-cuadrado
    con 8 grados de libertad en caso de que SciPy no esté instalado.
    """
    if chi2_val <= 0:
        return 1.0
    # Fórmula analítica para df=8: P(X > x) = exp(-x/2) * (1 + x/2 + x^2/8 + x^3/48)
    x = chi2_val / 2.0
    poly = 1.0 + x + (x ** 2) / 2.0 + (x ** 3) / 6.0
    p = math.exp(-x) * poly
    return max(0.0, min(1.0, p))


def calcular_p_value_chi2(chi2_val: float, df: int = 8) -> float:
    """Calcula el p-value de Chi-cuadrado."""
    if chi2_val < 0:
        return 1.0
    if HAVE_SCIPY:
        try:
            return float(scipy_chi2.sf(chi2_val, df))
        except Exception:
            pass
    return chi2_survival_fallback(chi2_val, df)


def calcular_score_humano(chi2_val: float, mad: float, n: int) -> Tuple[float, str, str]:
    """
    Calcula un porcentaje continuo calibrado (0% a 100%) de verosimilitud humana /
    comportamiento orgánico y asigna el nivel de conformidad forense.
    
    Criterios:
      - Chi-cuadrado crítico (df=8, alfa=0.05) = 15.507
      - Umbrales MAD de Mark Nigrini:
          MAD <= 0.006: Estricta (Excelente concordancia)
          0.006 < MAD <= 0.012: Aceptable
          0.012 < MAD <= 0.015: Marginal / Dudoso
          MAD > 0.015: No conformidad severa (Anomalía)
    """
    chi2_critico = 15.507
    mad_critico = 0.015

    ratio_chi2 = chi2_val / chi2_critico
    ratio_mad = mad / mad_critico

    # Factor de distancia combinada (ponderando MAD que es invariante al tamaño de muestra)
    distancia = 0.45 * min(3.0, ratio_chi2) + 0.55 * min(3.0, ratio_mad)

    # Función sigmoidal de verosimilitud humana
    human_pct = 100.0 / (1.0 + (distancia / 1.5) ** 2.4)
    human_pct = max(3.0, min(99.0, human_pct))

    # Nivel y veredicto
    if mad <= 0.006 and ratio_chi2 <= 1.0:
        nivel = "Conformidad Estricta (Orgánico)"
        veredicto = "Alta Probabilidad de Red Humana / Orgánica"
    elif mad <= 0.012 and ratio_chi2 <= 1.3:
        nivel = "Conformidad Aceptable"
        veredicto = "Probablemente Humano / Comportamiento Natural"
    elif mad <= 0.018 or ratio_chi2 <= 1.8:
        nivel = "No Conformidad Marginal"
        veredicto = "Actividad Mixta / Red Atípica"
    else:
        nivel = "No Conformidad Severa (Anómalo)"
        veredicto = "Alta Probabilidad de Comportamiento Artificial / Botnet"

    # Si la muestra es reducida, ajustar advertencia de significancia
    if n < 40:
        veredicto += f" (Muestra preliminar N={n})"

    return round(human_pct, 1), nivel, veredicto


def analizar_serie_benford(valores: List[int], nombre: str) -> Optional[BenfordStat]:
    """Calcula las estadísticas completas de Benford para una lista de números."""
    fsd_list = [extraer_primer_digito(v) for v in valores if v is not None]
    fsd_validos = [d for d in fsd_list if d is not None]

    n = len(fsd_validos)
    if n == 0:
        return None

    conteos: Dict[int, int] = {d: 0 for d in range(1, 10)}
    for d in fsd_validos:
        conteos[d] += 1

    pct_obs: Dict[int, float] = {d: (conteos[d] / n) for d in range(1, 10)}
    pct_esp: Dict[int, float] = {d: BENFORD_THEORETICAL[d] for d in range(1, 10)}

    # Chi-cuadrado: sum((O - E)^2 / E)
    chi2_val = 0.0
    for d in range(1, 10):
        esperado_conteos = n * pct_esp[d]
        if esperado_conteos > 0:
            chi2_val += ((conteos[d] - esperado_conteos) ** 2) / esperado_conteos

    p_val = calcular_p_value_chi2(chi2_val, df=8)

    # MAD de Nigrini: sum(|obs - esp|) / 9
    mad_val = sum(abs(pct_obs[d] - pct_esp[d]) for d in range(1, 10)) / 9.0

    # Distancia Kolmogorov-Smirnov
    cum_obs = 0.0
    ks_max = 0.0
    for d in range(1, 10):
        cum_obs += pct_obs[d]
        diff = abs(cum_obs - BENFORD_CDF[d])
        if diff > ks_max:
            ks_max = diff

    human_score, nivel, veredicto = calcular_score_humano(chi2_val, mad_val, n)

    return BenfordStat(
        nombre=nombre,
        n_total=n,
        conteos_observados=conteos,
        porcentajes_observados={d: round(pct_obs[d] * 100, 2) for d in range(1, 10)},
        porcentajes_esperados={d: round(pct_esp[d] * 100, 2) for d in range(1, 10)},
        chi2=round(chi2_val, 3),
        p_value=round(p_val, 4),
        mad=round(mad_val, 5),
        ks_distance=round(ks_max, 4),
        human_score=human_score,
        nivel_conformidad=nivel,
        veredicto=veredicto,
    )


# ─────────────────────────────────────────────────────────
# Carga e Interpretación de Datos del JSON
# ─────────────────────────────────────────────────────────
def cargar_datos_perfil(filepath: str) -> Tuple[Dict, List[Dict]]:
    """Carga el JSON generado por PlayScrap y extrae las cuentas de la red."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    cuentas = []

    # 1. Nuevo formato red_analizada
    if "red_analizada" in data and isinstance(data["red_analizada"], dict):
        cuentas = data["red_analizada"].get("cuentas", [])

    # 2. Formato red_metricas
    elif "red_metricas" in data and isinstance(data["red_metricas"], dict):
        cuentas = data["red_metricas"].get("cuentas", [])

    # 3. Formato seguidores como lista de objetos
    elif "seguidores" in data and isinstance(data["seguidores"], list):
        if data["seguidores"] and isinstance(data["seguidores"][0], dict):
            cuentas = data["seguidores"]

    # Si aún no hay cuentas, buscar en seguidos
    if not cuentas and "seguidos" in data and isinstance(data["seguidos"], list):
        if data["seguidos"] and isinstance(data["seguidos"][0], dict):
            cuentas = data["seguidos"]

    return data, cuentas


def procesar_analisis_benford(filepath: str) -> BenfordReport:
    """Ejecuta el análisis completo de Benford sobre el archivo JSON indicado."""
    data, cuentas = cargar_datos_perfil(filepath)

    target_user = data.get("perfil", "desconocido")
    avatar = data.get("foto_perfil_local", "")
    total_fol = data.get("total_seguidores", 0)
    total_flw = data.get("total_seguidos", 0)

    tipo_red = "seguidores"
    if "red_analizada" in data and isinstance(data["red_analizada"], dict):
        tipo_red = data["red_analizada"].get("tipo_red", "seguidores")
    elif "red_metricas" in data and isinstance(data["red_metricas"], dict):
        tipo_red = data["red_metricas"].get("origen", "seguidores")

    # Extraer series numéricas
    valores_seguidores = []
    valores_seguidos = []

    for c in cuentas:
        if isinstance(c, dict):
            s = c.get("seguidores")
            f = c.get("seguidos")
            if s is not None and s > 0:
                valores_seguidores.append(int(s))
            if f is not None and f > 0:
                valores_seguidos.append(int(f))

    stat_fol = analizar_serie_benford(valores_seguidores, "Seguidores de la Red")
    stat_flw = analizar_serie_benford(valores_seguidos, "Seguidos de la Red")

    # Score Global Ponderado (60% seguidores de la red, 40% seguidos)
    scores = []
    pesos = []
    if stat_fol:
        scores.append(stat_fol.human_score)
        pesos.append(0.6)
    if stat_flw:
        scores.append(stat_flw.human_score)
        pesos.append(0.4)

    if scores:
        sum_pesos = sum(pesos)
        score_global = round(sum(s * p for s, p in zip(scores, pesos)) / sum_pesos, 1)
    else:
        score_global = 50.0

    if score_global >= 85.0:
        veredicto_global = "Alta Probabilidad de Audiencia Orgánica / Humana"
    elif score_global >= 65.0:
        veredicto_global = "Audiencia Predominantemente Humana con Interacción Natural"
    elif score_global >= 45.0:
        veredicto_global = "Perfil con Anomalías Moderadas / Actividad Atípica"
    else:
        veredicto_global = "Alta Probabilidad de Cuentas Artificiales / Granjas de Bots"

    return BenfordReport(
        perfil=target_user,
        foto_perfil_local=avatar,
        total_seguidores_perfil=total_fol,
        total_seguidos_perfil=total_flw,
        tipo_red=tipo_red,
        muestra_analizada=len(cuentas),
        score_global_humano=score_global,
        veredicto_global=veredicto_global,
        stat_seguidores=stat_fol,
        stat_seguidos=stat_flw,
        cuentas=cuentas,
    )


# ─────────────────────────────────────────────────────────
# Generador del Reporte Visual HTML (Chart.js + Glassmorphism)
# ─────────────────────────────────────────────────────────
def generar_reporte_html(reporte: BenfordReport, output_file: str) -> str:
    """Genera un archivo HTML interactivo y estilizado con la gráfica Benford."""
    u = reporte.perfil
    score = reporte.score_global_humano
    avatar_src = reporte.foto_perfil_local if (reporte.foto_perfil_local and os.path.exists(reporte.foto_perfil_local)) else ""

    # Determinar color según score
    if score >= 80:
        score_color = "#10b981"  # Esmeralda
        score_label = "Humano / Orgánico"
    elif score >= 55:
        score_color = "#f59e0b"  # Ámbar
        score_label = "Atípico / Mixto"
    else:
        score_color = "#ef4444"  # Rojo
        score_label = "Anomalía / Bot"

    # Preparar datos JSON para Chart.js
    chart_data = {
        "digits": list(range(1, 10)),
        "theoretical": [BENFORD_THEORETICAL[d] * 100 for d in range(1, 10)],
        "followers": [reporte.stat_seguidores.porcentajes_observados.get(d, 0) for d in range(1, 10)] if reporte.stat_seguidores else [],
        "following": [reporte.stat_seguidos.porcentajes_observados.get(d, 0) for d in range(1, 10)] if reporte.stat_seguidos else [],
    }
    chart_json = json.dumps(chart_data)

    # Filas de la tabla para Seguidores
    tabla_fol_rows = ""
    if reporte.stat_seguidores:
        stat = reporte.stat_seguidores
        for d in range(1, 10):
            obs = stat.conteos_observados.get(d, 0)
            obs_pct = stat.porcentajes_observados.get(d, 0.0)
            esp_pct = stat.porcentajes_esperados.get(d, 0.0)
            diff = obs_pct - esp_pct
            diff_sign = "+" if diff > 0 else ""
            diff_color = "#10b981" if abs(diff) <= 3.0 else ("#f59e0b" if abs(diff) <= 7.0 else "#ef4444")
            tabla_fol_rows += f"""
            <tr>
                <td class="digit-cell"><strong>{d}</strong></td>
                <td>{obs:,}</td>
                <td><strong>{obs_pct:.1f}%</strong></td>
                <td style="color: #cbd5e1;">{esp_pct:.1f}%</td>
                <td style="color: {diff_color}; font-weight:600;">{diff_sign}{diff:.1f}%</td>
            </tr>
            """

    # Filas de la tabla para Seguidos
    tabla_flw_rows = ""
    if reporte.stat_seguidos:
        stat = reporte.stat_seguidos
        for d in range(1, 10):
            obs = stat.conteos_observados.get(d, 0)
            obs_pct = stat.porcentajes_observados.get(d, 0.0)
            esp_pct = stat.porcentajes_esperados.get(d, 0.0)
            diff = obs_pct - esp_pct
            diff_sign = "+" if diff > 0 else ""
            diff_color = "#10b981" if abs(diff) <= 3.0 else ("#f59e0b" if abs(diff) <= 7.0 else "#ef4444")
            tabla_flw_rows += f"""
            <tr>
                <td class="digit-cell"><strong>{d}</strong></td>
                <td>{obs:,}</td>
                <td><strong>{obs_pct:.1f}%</strong></td>
                <td style="color: #cbd5e1;">{esp_pct:.1f}%</td>
                <td style="color: {diff_color}; font-weight:600;">{diff_sign}{diff:.1f}%</td>
            </tr>
            """

    stat_fol = reporte.stat_seguidores
    stat_flw = reporte.stat_seguidos

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análisis de Benford · @{u}</title>
    <meta name="description" content="Detección de bots y evaluación de autenticidad de red mediante la Ley de Benford">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg: #070913;
            --bg-card: rgba(255, 255, 255, 0.035);
            --bg-card-hover: rgba(255, 255, 255, 0.055);
            --border: rgba(255, 255, 255, 0.08);
            --border-hover: rgba(255, 255, 255, 0.16);
            --text: #f8fafc;
            --text-secondary: #94a3b8;
            --text-dim: #64748b;
            --accent: #6366f1;
            --accent-glow: rgba(99, 102, 241, 0.25);
            --score-color: {score_color};
            --font: 'Inter', -apple-system, sans-serif;
            --radius: 18px;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: var(--bg);
            color: var(--text);
            font-family: var(--font);
            min-height: 100vh;
            padding-bottom: 70px;
            overflow-x: hidden;
        }}

        /* Glow orbs de fondo */
        .bg-orb {{
            position: fixed; border-radius: 50%; pointer-events: none;
            filter: blur(140px); opacity: 0.15; z-index: 0;
        }}
        .orb-1 {{ width: 500px; height: 500px; background: #6366f1; top: -100px; left: -100px; }}
        .orb-2 {{ width: 450px; height: 450px; background: {score_color}; top: 40%; right: -100px; }}

        .container {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 40px 24px;
            position: relative;
            z-index: 1;
        }}

        /* Header del Perfil */
        .profile-header {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 32px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 24px;
            margin-bottom: 30px;
            backdrop-filter: blur(12px);
        }}

        .profile-left {{
            display: flex;
            align-items: center;
            gap: 22px;
        }}

        .avatar-img {{
            width: 84px; height: 84px;
            border-radius: 50%;
            object-fit: cover;
            border: 3px solid var(--border-hover);
            box-shadow: 0 0 25px rgba(99, 102, 241, 0.25);
        }}
        .avatar-fallback {{
            width: 84px; height: 84px;
            border-radius: 50%;
            background: linear-gradient(135deg, #6366f1, #a855f7);
            display: flex; align-items: center; justify-content: center;
            font-size: 32px; font-weight: 800;
        }}

        .user-title {{
            font-size: 1.8rem;
            font-weight: 800;
            letter-spacing: -0.5px;
        }}
        .user-subtitle {{
            color: var(--text-secondary);
            font-size: 0.95rem;
            margin-top: 4px;
        }}

        .score-box {{
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 16px 28px;
            text-align: right;
            display: flex;
            align-items: center;
            gap: 20px;
        }}
        .score-val {{
            font-size: 2.8rem;
            font-weight: 900;
            color: var(--score-color);
            line-height: 1;
        }}
        .score-meta {{
            text-align: left;
        }}
        .score-lbl {{
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-dim);
            font-weight: 700;
        }}
        .score-badge {{
            display: inline-block;
            margin-top: 4px;
            padding: 4px 10px;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid var(--score-color);
            border-radius: 20px;
            color: var(--score-color);
            font-size: 0.8rem;
            font-weight: 700;
        }}

        /* Métricas Rápidas */
        .grid-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 18px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 22px;
            backdrop-filter: blur(10px);
            transition: transform 0.2s, border-color 0.2s;
        }}
        .stat-card:hover {{
            transform: translateY(-2px);
            border-color: var(--border-hover);
        }}
        .stat-name {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: 600;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .stat-number {{
            font-size: 1.6rem;
            font-weight: 800;
            color: #fff;
        }}
        .stat-sub {{
            font-size: 0.8rem;
            color: var(--text-dim);
            margin-top: 6px;
        }}

        /* Contenedor del Gráfico */
        .chart-section {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 32px;
            margin-bottom: 30px;
            backdrop-filter: blur(12px);
        }}

        .chart-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .chart-title {{
            font-size: 1.25rem;
            font-weight: 700;
        }}

        .chart-toggle-group {{
            display: flex;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 4px;
            gap: 4px;
        }}
        .toggle-btn {{
            background: transparent;
            border: none;
            color: var(--text-secondary);
            padding: 8px 16px;
            border-radius: 8px;
            font-family: inherit;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .toggle-btn.active {{
            background: var(--accent);
            color: #fff;
            box-shadow: 0 0 15px var(--accent-glow);
        }}

        .chart-canvas-container {{
            position: relative;
            height: 380px;
            width: 100%;
        }}

        /* Tablas de Frecuencias */
        .tables-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 24px;
            margin-bottom: 30px;
        }}
        .table-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 24px;
            backdrop-filter: blur(10px);
        }}
        .table-card h3 {{
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
        }}
        th {{
            text-align: left;
            padding: 10px 8px;
            color: var(--text-dim);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            border-bottom: 1px solid var(--border);
        }}
        td {{
            padding: 10px 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            color: var(--text-secondary);
        }}
        .digit-cell {{
            font-size: 1.05rem;
            color: #fff;
        }}

        /* Diagnóstico Forense y Explicación */
        .forensic-box {{
            background: rgba(99, 102, 241, 0.05);
            border: 1px solid rgba(99, 102, 241, 0.2);
            border-radius: var(--radius);
            padding: 28px;
            line-height: 1.65;
            font-size: 0.95rem;
            color: #cbd5e1;
        }}
        .forensic-box h4 {{
            color: #fff;
            font-size: 1.1rem;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
    </style>
</head>
<body>
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>

    <div class="container">
        <!-- 1. Header Perfil -->
        <header class="profile-header">
            <div class="profile-left">
                {f'<img src="{avatar_src}" alt="avatar" class="avatar-img">' if avatar_src else f'<div class="avatar-fallback">{u[:1].upper()}</div>'}
                <div>
                    <h1 class="user-title">@{u}</h1>
                    <p class="user-subtitle">Diagnóstico Forense de Audiencia · Ley de Benford</p>
                </div>
            </div>
            <div class="score-box">
                <div class="score-val">{score}%</div>
                <div class="score-meta">
                    <div class="score-lbl">Score Humano</div>
                    <div class="score-badge">{score_label}</div>
                </div>
            </div>
        </header>

        <!-- 2. Tarjetas de Resumen -->
        <div class="grid-stats">
            <div class="stat-card">
                <div class="stat-name">🌐 Muestra de Red Analizada</div>
                <div class="stat-number">{reporte.muestra_analizada} cuentas</div>
                <div class="stat-sub">Origen: {reporte.tipo_red.upper()} (de {reporte.total_seguidores_perfil:,} totales)</div>
            </div>
            <div class="stat-card">
                <div class="stat-name">⚖️ Chi-cuadrado (χ²) Seguidores</div>
                <div class="stat-number">{stat_fol.chi2 if stat_fol else 'N/A'}</div>
                <div class="stat-sub">p-valor: {stat_fol.p_value if stat_fol else 'N/A'} (Crítico: 15.51)</div>
            </div>
            <div class="stat-card">
                <div class="stat-name">📐 MAD Nigrini (Desv. Media)</div>
                <div class="stat-number">{stat_fol.mad if stat_fol else 'N/A'}</div>
                <div class="stat-sub">{stat_fol.nivel_conformidad if stat_fol else 'Sin datos'}</div>
            </div>
            <div class="stat-card">
                <div class="stat-name">🔍 Veredicto Global</div>
                <div class="stat-number" style="font-size: 1.15rem; color: var(--score-color);">{reporte.veredicto_global}</div>
                <div class="stat-sub">Basado en primer dígito significativo (FSD)</div>
            </div>
        </div>

        <!-- 3. Gráfico Interactivo de Barras -->
        <section class="chart-section">
            <div class="chart-header">
                <div>
                    <h2 class="chart-title">Distribución del Primer Dígito: Observado vs. Benford</h2>
                    <p style="color: var(--text-dim); font-size: 0.85rem; margin-top: 4px;">
                        Compara las frecuencias observadas en la red frente a la curva logarítmica esperada P(d) = log10(1 + 1/d)
                    </p>
                </div>
                <div class="chart-toggle-group">
                    <button class="toggle-btn active" id="btn-fol" onclick="switchSeries('followers')">Seguidores de la Red</button>
                    <button class="toggle-btn" id="btn-flw" onclick="switchSeries('following')">Seguidos de la Red</button>
                </div>
            </div>

            <div class="chart-canvas-container">
                <canvas id="benfordChart"></canvas>
            </div>
        </section>

        <!-- 4. Tablas Detalladas Dígito por Dígito -->
        <div class="tables-grid">
            <div class="table-card">
                <h3>
                    <span>👥 Seguidores de la Red</span>
                    <span style="font-size: 0.8rem; color: #10b981; font-weight:600;">{stat_fol.human_score if stat_fol else 0}% Humano</span>
                </h3>
                <table>
                    <thead>
                        <tr>
                            <th>Dígito</th>
                            <th>Cuentas</th>
                            <th>Real (%)</th>
                            <th>Benford (%)</th>
                            <th>Diferencia</th>
                        </tr>
                    </thead>
                    <tbody>
                        {tabla_fol_rows if tabla_fol_rows else '<tr><td colspan="5">Sin datos disponibles</td></tr>'}
                    </tbody>
                </table>
            </div>

            <div class="table-card">
                <h3>
                    <span>🫂 Seguidos de la Red</span>
                    <span style="font-size: 0.8rem; color: #10b981; font-weight:600;">{stat_flw.human_score if stat_flw else 0}% Humano</span>
                </h3>
                <table>
                    <thead>
                        <tr>
                            <th>Dígito</th>
                            <th>Cuentas</th>
                            <th>Real (%)</th>
                            <th>Benford (%)</th>
                            <th>Diferencia</th>
                        </tr>
                    </thead>
                    <tbody>
                        {tabla_flw_rows if tabla_flw_rows else '<tr><td colspan="5">Sin datos disponibles</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 5. Caja Explicativa Forense -->
        <div class="forensic-box">
            <h4>💡 ¿Cómo interpreta la ciencia este resultado?</h4>
            <p>
                En redes sociales, los perfiles humanos reales interactúan con cuentas de todas las magnitudes (amigos con 50 seguidores, perfiles medianos con 3,000 y celebridades con 500,000+).
                Ese proceso de crecimiento multiplicativo libre produce de forma matemática que el dígito <strong>1</strong> sea el más frecuente (~30.1%) y el <strong>9</strong> el más infrecuente (~4.6%).
            </p>
            <p style="margin-top: 10px;">
                Las <strong>granjas de bots</strong> y redes infladas artificialmente suelen tener conteos uniformes o concentrados en un rango estrecho (ej. entre 100 y 150 seguidores), lo que dispara el estadístico <strong>Chi-cuadrado (χ²)</strong> y el <strong>MAD</strong>, reduciendo el score de verosimilitud humana.
            </p>
        </div>
    </div>

    <script>
        const RAW_DATA = {chart_json};
        let activeSeries = 'followers';
        let chartInstance = null;

        function buildChart(seriesKey) {{
            const ctx = document.getElementById('benfordChart').getContext('2d');
            const observedData = seriesKey === 'followers' ? RAW_DATA.followers : RAW_DATA.following;

            if (chartInstance) {{
                chartInstance.destroy();
            }}

            chartInstance = new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: ['1', '2', '3', '4', '5', '6', '7', '8', '9'],
                    datasets: [
                        {{
                            label: 'Real Observado (%)',
                            data: observedData,
                            backgroundColor: 'rgba(99, 102, 241, 0.75)',
                            borderColor: '#818cf8',
                            borderWidth: 1.5,
                            borderRadius: 6,
                            barPercentage: 0.65,
                            order: 2
                        }},
                        {{
                            label: 'Ley de Benford Teórica (%)',
                            data: RAW_DATA.theoretical,
                            type: 'line',
                            borderColor: '#fbbf24',
                            borderWidth: 3,
                            borderDash: [5, 5],
                            pointBackgroundColor: '#fbbf24',
                            pointRadius: 5,
                            pointHoverRadius: 7,
                            fill: false,
                            tension: 0.3,
                            order: 1
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{
                        mode: 'index',
                        intersect: false
                    }},
                    plugins: {{
                        legend: {{
                            labels: {{
                                color: '#cbd5e1',
                                font: {{ family: 'Inter', size: 12, weight: 600 }}
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: 'rgba(15, 23, 42, 0.95)',
                            titleColor: '#fff',
                            bodyColor: '#cbd5e1',
                            borderColor: 'rgba(255, 255, 255, 0.15)',
                            borderWidth: 1,
                            padding: 12,
                            callbacks: {{
                                label: function(context) {{
                                    return context.dataset.label + ': ' + context.parsed.y.toFixed(1) + '%';
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                            ticks: {{ color: '#94a3b8', font: {{ family: 'Inter', weight: 600 }} }},
                            title: {{
                                display: true,
                                text: 'Primer Dígito Significativo (FSD)',
                                color: '#64748b',
                                font: {{ family: 'Inter', size: 12 }}
                            }}
                        }},
                        y: {{
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                            ticks: {{
                                color: '#94a3b8',
                                font: {{ family: 'Inter' }},
                                callback: val => val + '%'
                            }},
                            suggestedMax: 35,
                            beginAtZero: true
                        }}
                    }}
                }}
            }});
        }}

        function switchSeries(seriesKey) {{
            activeSeries = seriesKey;
            document.getElementById('btn-fol').classList.toggle('active', seriesKey === 'followers');
            document.getElementById('btn-flw').classList.toggle('active', seriesKey === 'following');
            buildChart(seriesKey);
        }}

        // Inicializar
        buildChart('followers');
    </script>
</body>
</html>
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    return os.path.abspath(output_file)


# ─────────────────────────────────────────────────────────
# Salida en Consola / Terminal
# ─────────────────────────────────────────────────────────
def imprimir_reporte_consola(reporte: BenfordReport):
    """Imprime un resumen visual y ordenado en la terminal."""
    u = reporte.perfil
    score = reporte.score_global_humano

    barra_len = int(score / 5)
    barra = "█" * barra_len + "░" * (20 - barra_len)

    print("\n" + "=" * 68)
    print(f" 📐 ANÁLISIS FORENSE LEY DE BENFORD (DETECCIÓN DE BOTS) · @{u}")
    print("=" * 68)
    print(f" 🎯 Verosimilitud Humana:  [{barra}] {score}%")
    print(f" 🏷️  Diagnóstico:          {reporte.veredicto_global}")
    print(f" 👥 Muestra Analizada:     {reporte.muestra_analizada} cuentas ({reporte.tipo_red.upper()})")
    print(f" 📊 Perfil Objetivo:       {reporte.total_seguidores_perfil:,} seguidores | {reporte.total_seguidos_perfil:,} seguidos")
    print("-" * 68)

    stat = reporte.stat_seguidores
    if stat:
        print(f"\n[ESTADÍSTICAS: {stat.nombre.upper()}] (N={stat.n_total})")
        print(f"  • Chi-cuadrado (χ²):    {stat.chi2} (Crítico: 15.51 | df=8)")
        print(f"  • p-valor:              {stat.p_value} ({'No se rechaza Benford (Orgánico)' if stat.p_value >= 0.05 else 'Desviación estadísticamente significativa'})")
        print(f"  • MAD Nigrini:          {stat.mad} ({stat.nivel_conformidad})")
        print(f"  • Distancia KS (D):     {stat.ks_distance}")
        print(f"  • Score Parcial:        {stat.human_score}%")
        print("\n  Dígito | Observado (N) | Real (%) | Benford (%) | Desviación")
        print("  " + "─" * 58)
        for d in range(1, 10):
            cnt = stat.conteos_observados.get(d, 0)
            obs_p = stat.porcentajes_observados.get(d, 0.0)
            esp_p = stat.porcentajes_esperados.get(d, 0.0)
            diff = obs_p - esp_p
            diff_str = f"{'+' if diff > 0 else ''}{diff:.1f}%"
            print(f"    {d}    |     {cnt:<8} |  {obs_p:>5.1f}%  |   {esp_p:>5.1f}%   |   {diff_str:>6}")
        print("  " + "─" * 58)

    stat_flw = reporte.stat_seguidos
    if stat_flw:
        print(f"\n[ESTADÍSTICAS: {stat_flw.nombre.upper()}] (N={stat_flw.n_total})")
        print(f"  • Chi-cuadrado (χ²):    {stat_flw.chi2} | p-valor: {stat_flw.p_value} | MAD: {stat_flw.mad}")
        print(f"  • Score Parcial:        {stat_flw.human_score}% ({stat_flw.nivel_conformidad})")

    print("\n" + "=" * 68)


# ─────────────────────────────────────────────────────────
# Punto de Entrada
# ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Analizador forense de bots en Instagram mediante la Ley de Benford",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("archivo", nargs="?", default=None, help="Ruta al archivo JSON de datos extraídos")
    parser.add_argument("--no-browser", action="store_true", help="No abrir automáticamente el reporte HTML en el navegador")
    parser.add_argument("--out", default=None, help="Ruta o nombre personalizado para el archivo HTML generado")
    args = parser.parse_args()

    target_file = args.archivo
    if not target_file:
        candidatos = [f for f in os.listdir(".") if f.endswith("_datos.json") and os.path.isfile(f)]
        if candidatos:
            print("\nArchivos de datos de Instagram encontrados:")
            for idx, c in enumerate(candidatos, 1):
                print(f"  [{idx}] {c}")
            print(f"  [0] Ingresar ruta manualmente")
            try:
                opc = input(f"\nSelecciona una opción [1-{len(candidatos)}]: ").strip()
                if opc == "0" or not opc:
                    target_file = input("Ruta al archivo JSON: ").strip()
                else:
                    sel_idx = int(opc) - 1
                    target_file = candidatos[sel_idx] if 0 <= sel_idx < len(candidatos) else candidatos[0]
            except Exception:
                target_file = candidatos[0]
        else:
            target_file = input("Ingresa la ruta del archivo JSON: ").strip()

    if not target_file or not os.path.exists(target_file):
        print(f"\n[ERROR] El archivo '{target_file}' no existe.")
        sys.exit(1)

    print(f"\nProcesando análisis de Benford sobre: {target_file} ...")
    reporte = procesar_analisis_benford(target_file)

    imprimir_reporte_consola(reporte)

    output_html = args.out or f"{reporte.perfil}_benford_analisis.html"
    html_path = generar_reporte_html(reporte, output_html)

    print(f"\n[HTML] Reporte interactivo generado con éxito:")
    print(f"       file:///{html_path.replace(os.sep, '/')}")

    if not args.no_browser:
        webbrowser.open(f"file:///{html_path.replace(os.sep, '/')}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[AVISO] Proceso cancelado por el usuario.")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
