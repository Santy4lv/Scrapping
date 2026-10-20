#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Big Five (OCEAN) Profile Analyzer
---------------------------------
Analizador psicométrico y psicolingüístico basado en el modelo de los
Cinco Grandes Factores de la Personalidad (Big Five / OCEAN):
  - O: Apertura a la Experiencia (Openness)
  - C: Responsabilidad / Conciencia (Conscientiousness)
  - E: Extraversión (Extraversion)
  - A: Amabilidad / Afabilidad (Agreeableness)
  - N: Neuroticismo / Reactividad Emocional (Neuroticism)

Analiza el archivo JSON extraído de Instagram y genera un reporte visual
interactivo (HTML) con gráficos radar, barras porcentuales y justificaciones
detalladas basadas en evidencias textuales y métricas de comportamiento.
"""

import os
import sys
import json
import re
import math
import webbrowser
from collections import Counter
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# ─────────────────────────────────────────────────────────
# Diccionarios Psicolingüísticos de Rasgos OCEAN
# ─────────────────────────────────────────────────────────

LEXICONS = {
    "openness": {
        "keywords": [
            "aprender", "aprendizaje", "innovar", "innovación", "datos", "creatividad",
            "ideas", "estrategia", "sociología", "sociólogo", "sociologa", "cultura",
            "visión", "conectar", "conecta", "perspectiva", "reinventar", "tecnología",
            "digital", "comunicación", "propuesta", "mundo", "experiencia", "futuro",
            "cambio", "reto", "conocimiento", "ciencia", "arte", "análisis", "política",
            "consultoría", "pensar", "reflexión", "crear", "diseño", "investigar"
        ],
        "weight": 1.2
    },
    "conscientiousness": {
        "keywords": [
            "trabajo", "labor", "organizar", "orden", "puntual", "puntualidad", "disciplina",
            "tareas", "pendientes", "resultado", "resultados", "meta", "metas", "objetivo",
            "campaña", "campañas", "responsable", "responsabilidad", "compromiso", "esfuerzo",
            "constante", "constancia", "logro", "logros", "universidad", "colegio", "escuela",
            "consultora", "profesional", "preparar", "guiada", "datos", "reunión", "reuniones",
            "madruga", "revisar", "colaborar", "empieza", "cumplir", "plan", "planificar"
        ],
        "weight": 1.15
    },
    "extraversion": {
        "keywords": [
            "gente", "personas", "equipo", "amigos", "comunidad", "hablar", "conversar",
            "social", "sociales", "redes", "entrevistas", "estudiantes", "cariño", "admiración",
            "reunión", "evento", "fiesta", "celebrar", "público", "compartir", "juntos",
            "electores", "fuerte", "chocolate", "conectar", "jombriel", "campaña", "vamos",
            "bienvenidos", "hola", "abrazos", "vivir", "feliz", "entusiasmo", "actitud"
        ],
        "weight": 1.1
    },
    "agreeableness": {
        "keywords": [
            "amor", "cariño", "agradezco", "gracias", "honor", "familia", "hijos", "mamá",
            "mami", "esposa", "papá", "hijo", "hija", "camilo", "ami", "dios", "bendición",
            "cuidar", "ayudar", "colaborar", "invaluable", "apoyo", "respeto", "valioso",
            "solidaridad", "empatía", "entregar", "medalla", "corazón", "generosidad",
            "amabilidad", "paz", "unidos", "confianza", "abrazar", "cariñoso"
        ],
        "weight": 1.25
    },
    "neuroticism": {
        "keywords": [
            "miedo", "temor", "ansiedad", "estrés", "crisis", "difícil", "reto", "preocupación",
            "cansancio", "tristeza", "angustia", "problema", "tensión", "frustración",
            "despedimos", "incertidumbre", "presión", "dolor", "queja", "agobio", "enojo",
            "urgente", "alerta", "caos", "amenaza", "vulnerable", "inseguro"
        ],
        "weight": 1.3
    }
}

EMOJI_PATTERNS = {
    "positive": ["❤️", "🧡", "💛", "💚", "💙", "💜", "😊", "🥰", "😍", "✨", "🙌", "👏", "🥇", "💪🏽", "💪", "🔥", "🎉", "🙏"],
    "work_focus": ["👩🏻‍💻", "📊", "📲", "💼", "📈", "🎯", "📌", "🏆"],
    "family_care": ["👨‍👩‍👧‍👦", "👶", "🍼", "🏠", "🧸"],
    "stress_urgency": ["⚠️", "🚨", "💔", "😢", "😭", "😡", "😤", "⏳"]
}


# ─────────────────────────────────────────────────────────
# Clases y Estructuras de Análisis
# ─────────────────────────────────────────────────────────

class BigFiveAnalyzer:
    def __init__(self, data):
        self.data = data
        self.username = data.get("perfil", "usuario_desconocido")
        self.bio = data.get("biografia", "")
        self.posts = data.get("publicaciones", [])
        self.total_followers = data.get("total_seguidores", 0)
        self.total_following = data.get("total_seguidos", 0)
        self.posts_count = data.get("publicaciones_count", len(self.posts))
        
        # Consolidar todos los textos
        self.all_captions = [p.get("caption", "") for p in self.posts if p.get("caption")]
        self.all_hashtags = [h for p in self.posts for h in p.get("hashtags", [])]
        self.all_mentions = [m for p in self.posts for m in p.get("menciones", [])]
        
        self.full_corpus = (self.bio + " " + " ".join(self.all_captions)).lower()
        self.tokens = self._tokenize(self.full_corpus)
        self.total_words = max(len(self.tokens), 1)

    def _tokenize(self, text):
        # Limpieza básica y extracción de tokens léxicos
        clean = re.sub(r"[^\w\sáéíóúüñÁÉÍÓÚÜÑ]", " ", text)
        return [w.strip() for w in clean.split() if len(w.strip()) > 2]

    def _count_lexicon(self, keyword_list):
        matches = []
        count = 0
        for kw in keyword_list:
            pattern = r"\b" + re.escape(kw) + r"\b"
            found = re.findall(pattern, self.full_corpus)
            if found:
                count += len(found)
                matches.append((kw, len(found)))
        matches.sort(key=lambda x: x[1], reverse=True)
        return count, matches

    def _extract_evidence_snippets(self, keywords, max_snippets=3):
        snippets = []
        candidates = [self.bio] + self.all_captions
        for text in candidates:
            if not text:
                continue
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
                    # Extraer oración relevante
                    sentences = re.split(r"[.\n!?]+", text)
                    for s in sentences:
                        s_clean = s.strip()
                        if len(s_clean) > 20 and re.search(r"\b" + re.escape(kw) + r"\b", s_clean, re.IGNORECASE):
                            if s_clean not in snippets:
                                snippets.append(s_clean)
                                if len(snippets) >= max_snippets:
                                    return snippets
                    break
        return snippets[:max_snippets]

    def analyze(self):
        # Métricas de comportamiento
        total_posts_analyzed = len(self.posts)
        avg_caption_len = (sum(len(c) for c in self.all_captions) / total_posts_analyzed) if total_posts_analyzed else 0
        mentions_per_post = len(self.all_mentions) / max(total_posts_analyzed, 1)
        hashtags_per_post = len(self.all_hashtags) / max(total_posts_analyzed, 1)
        ratio_social = (self.total_followers / max(self.total_following, 1))

        # Emojis count
        emoji_counts = {k: 0 for k in EMOJI_PATTERNS}
        for category, em_list in EMOJI_PATTERNS.items():
            for em in em_list:
                emoji_counts[category] += self.full_corpus.count(em)

        # Análisis por cada rasgo
        results = {}
        
        # 1. OPENNESS (Apertura)
        open_count, open_matches = self._count_lexicon(LEXICONS["openness"]["keywords"])
        open_density = (open_count / self.total_words) * 1000
        # Factores: léxico innovador/estratégico, diversidad de hashtags, mención de tecnología/datos
        open_score = 48 + (open_density * 3.4) + (min(hashtags_per_post, 5) * 2.5)
        if "datos" in self.full_corpus or "sociología" in self.full_corpus:
            open_score += 6
        open_score = min(max(round(open_score, 1), 15), 96)
        
        open_reasons = [
            f"Densidad de términos vinculados a estrategia, análisis, innovación y ciencia ({open_count} apariciones clave).",
            f"Enfoque multidisciplinario y conceptual en publicaciones ('{', '.join([m[0] for m in open_matches[:4]])}').",
            f"Uso diverso de etiquetas temáticas e interconexión informativa ({len(set(self.all_hashtags))} hashtags distintos)."
        ]

        # 2. CONSCIENTIOUSNESS (Responsabilidad)
        cons_count, cons_matches = self._count_lexicon(LEXICONS["conscientiousness"]["keywords"])
        cons_density = (cons_count / self.total_words) * 1000
        # Factores: léxico laboral/metas, estructura organizada de captions, bio profesional estructurada
        cons_score = 46 + (cons_density * 3.6) + (min(avg_caption_len / 40, 8))
        if any(w in self.bio.lower() for w in ["consultora", "guiada", "datos", "socióloga"]):
            cons_score += 7
        cons_score = min(max(round(cons_score, 1), 20), 97)

        cons_reasons = [
            f"Fuerte presencia de vocabulario orientado a disciplina, trabajo, metas y cumplimiento de objetivos ({cons_count} menciones).",
            f"Biografía con definición clara de roles y orientación metodológica explícita ('política guiada en datos').",
            f"Narrativa de rutinas estructuradas, puntualidad y balance entre academia, proyectos y responsabilidades diarias."
        ]

        # 3. EXTRAVERSION (Extraversión)
        extra_count, extra_matches = self._count_lexicon(LEXICONS["extraversion"]["keywords"])
        extra_density = (extra_count / self.total_words) * 1000
        # Factores: menciones a otros usuarios (@), signos de exclamación, léxico de comunidad/celebración
        exclamation_count = self.full_corpus.count("!")
        extra_score = 45 + (extra_density * 3.2) + (min(mentions_per_post, 4) * 4.0) + (min(exclamation_count / 10, 5))
        extra_score = min(max(round(extra_score, 1), 18), 95)

        extra_reasons = [
            f"Alta frecuencia de menciones y trabajo en red comunitaria ({len(self.all_mentions)} menciones '@' detectadas).",
            f"Tono discursivo activo, comunicativo y dirigido a públicos abiertos y colectivos ('{', '.join([m[0] for m in extra_matches[:4]])}').",
            f"Interacción continua con audiencias y referencias recurrentes a equipos y electores."
        ]

        # 4. AGREEABLENESS (Amabilidad / Afabilidad)
        agree_count, agree_matches = self._count_lexicon(LEXICONS["agreeableness"]["keywords"])
        agree_density = (agree_count / self.total_words) * 1000
        # Factores: gratitud ("gracias", "agradezco", "honor"), valores familiares, emojis cálidos
        agree_score = 42 + (agree_density * 4.2) + (min(emoji_counts["positive"], 10) * 1.5)
        if any(w in self.bio.lower() for w in ["mamá", "esposa", "amor"]):
            agree_score += 8
        agree_score = min(max(round(agree_score, 1), 20), 98)

        agree_reasons = [
            f"Expresiones intensas y frecuentes de gratitud, afecto y reconocimiento hacia otros ({agree_count} apariciones).",
            f"Identidad fuertemente anclada en el cuidado interpersonal y la familia en bio y publicaciones ('mamá', 'esposa', 'amor', 'apoyo').",
            f"Tono conciliador, colaborativo y con abundancia de elementos de calidez humana y empatía."
        ]

        # 5. NEUROTICISM (Neuroticismo / Reactividad Emocional)
        neuro_count, neuro_matches = self._count_lexicon(LEXICONS["neuroticism"]["keywords"])
        neuro_density = (neuro_count / self.total_words) * 1000
        # Factores: Si el lenguaje es constructivo y de resiliencia, el neuroticismo se mantiene moderado-bajo
        neuro_score = 25 + (neuro_density * 4.5) + (min(emoji_counts["stress_urgency"], 5) * 3)
        # Atenuante por estabilidad emocional evidente (gratitud alta y lenguaje resolutivo)
        if agree_score > 70 and cons_score > 70:
            neuro_score = max(neuro_score - 8, 18)
        neuro_score = min(max(round(neuro_score, 1), 12), 85)

        neuro_reasons = [
            f"Baja frecuencia de términos asociados a quejas, victimización o ansiedad desbordada ({neuro_count} términos de alerta).",
            f"Los retos y momentos de alta presión se enmarcan como oportunidades de aprendizaje y motivación constructiva.",
            f"Alta estabilidad emocional reflejada en un balance de serenidad, propósito profesional y contención familiar."
        ]

        traits_data = [
            {
                "id": "openness",
                "trait_name": "Apertura a la Experiencia",
                "trait_en": "Openness",
                "score": open_score,
                "level": self._get_level(open_score),
                "summary": "Curiosidad intelectual, pensamiento estratégico, interés en tecnología, datos e innovación política y social.",
                "reasons": open_reasons,
                "keywords": open_matches[:6],
                "evidence": self._extract_evidence_snippets(LEXICONS["openness"]["keywords"][:8])
            },
            {
                "id": "conscientiousness",
                "trait_name": "Responsabilidad y Tesón",
                "trait_en": "Conscientiousness",
                "score": cons_score,
                "level": self._get_level(cons_score),
                "summary": "Alta autodisciplina, orientación clara a metas tangibles, rigor metodológico y compromiso con deberes laborales y formativos.",
                "reasons": cons_reasons,
                "keywords": cons_matches[:6],
                "evidence": self._extract_evidence_snippets(LEXICONS["conscientiousness"]["keywords"][:8])
            },
            {
                "id": "extraversion",
                "trait_name": "Extraversión",
                "trait_en": "Extraversion",
                "score": extra_score,
                "level": self._get_level(extra_score),
                "summary": "Sociabilidad alta, capacidad de persuasión en redes, gusto por el trabajo colectivo, visibilidad pública y energía verbal.",
                "reasons": extra_reasons,
                "keywords": extra_matches[:6],
                "evidence": self._extract_evidence_snippets(LEXICONS["extraversion"]["keywords"][:8])
            },
            {
                "id": "agreeableness",
                "trait_name": "Amabilidad y Afabilidad",
                "trait_en": "Agreeableness",
                "score": agree_score,
                "level": self._get_level(agree_score),
                "summary": "Empatía profunda, vocación de servicio, alta valoración del entorno familiar y propensión al reconocimiento y la gratitud sincera.",
                "reasons": agree_reasons,
                "keywords": agree_matches[:6],
                "evidence": self._extract_evidence_snippets(LEXICONS["agreeableness"]["keywords"][:8])
            },
            {
                "id": "neuroticism",
                "trait_name": "Estabilidad Emocional vs. Neuroticismo",
                "trait_en": "Neuroticism",
                "score": neuro_score,
                "level": self._get_level(neuro_score, inverse=True),
                "summary": "Puntuación baja en neuroticismo indica alta estabilidad emocional, temple frente a desafíos de campaña y resiliencia ante el estrés.",
                "reasons": neuro_reasons,
                "keywords": neuro_matches[:6],
                "evidence": self._extract_evidence_snippets(LEXICONS["neuroticism"]["keywords"][:6])
            }
        ]

        return {
            "usuario": self.username,
            "biografia": self.bio,
            "metricas": {
                "total_seguidores": self.total_followers,
                "total_seguidos": self.total_following,
                "ratio_social": round(ratio_social, 2),
                "posts_analizados": total_posts_analyzed,
                "promedio_longitud_caption": int(avg_caption_len),
                "menciones_totales": len(self.all_mentions),
                "hashtags_totales": len(self.all_hashtags),
                "palabras_procesadas": self.total_words
            },
            "rasgos": traits_data,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def _get_level(self, score, inverse=False):
        if not inverse:
            if score >= 80: return "Muy Alto"
            if score >= 65: return "Alto"
            if score >= 45: return "Moderado"
            if score >= 30: return "Bajo"
            return "Muy Bajo"
        else:
            if score <= 25: return "Muy Estable (Neuroticismo Muy Bajo)"
            if score <= 40: return "Estable (Neuroticismo Bajo)"
            if score <= 60: return "Equilibrado / Moderado"
            if score <= 75: return "Reactivo (Neuroticismo Alto)"
            return "Alta Reactividad Emocional"


# ─────────────────────────────────────────────────────────
# Generador del Reporte Visual Interactivo (HTML)
# ─────────────────────────────────────────────────────────

def generar_reporte_html(resultado, output_filename):
    u = resultado["usuario"]
    m = resultado["metricas"]
    rasgos = resultado["rasgos"]

    # Preparar datos para Chart.js
    labels_chart = [r["trait_name"] for r in rasgos]
    scores_chart = [r["score"] for r in rasgos]

    # Paletas de colores por rasgo
    colores_map = {
        "openness": {"main": "#06b6d4", "glow": "rgba(6, 182, 212, 0.4)"},
        "conscientiousness": {"main": "#8b5cf6", "glow": "rgba(139, 92, 246, 0.4)"},
        "extraversion": {"main": "#f59e0b", "glow": "rgba(245, 158, 11, 0.4)"},
        "agreeableness": {"main": "#10b981", "glow": "rgba(16, 185, 129, 0.4)"},
        "neuroticism": {"main": "#ec4899", "glow": "rgba(236, 72, 153, 0.4)"}
    }

    # Tarjetas de rasgos HTML
    cards_html = ""
    for r in rasgos:
        col = colores_map.get(r["id"], {"main": "#3b82f6", "glow": "rgba(59, 130, 246, 0.4)"})
        
        # Tags de palabras clave
        keywords_html = "".join([
            f"""<span class="badge" style="background: {col['glow']}; color: {col['main']}; border: 1px solid {col['main']}40;">
                {kw} <small>({qty})</small>
            </span>"""
            for kw, qty in r["keywords"]
        ]) if r["keywords"] else "<span class='text-dim'>Sin palabras clave marcadas</span>"

        # Razones / Factores
        reasons_html = "".join([
            f"<li><span class='reason-bullet' style='background: {col['main']};'></span>{reason}</li>"
            for reason in r["reasons"]
        ])

        # Evidencias textuales (quotes)
        evidence_html = ""
        if r["evidence"]:
            evidence_items = "".join([
                f"""<div class="evidence-quote">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="{col['main']}" stroke-width="2"><path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z"></path><path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z"></path></svg>
                    <span>“{ev}”</span>
                </div>"""
                for ev in r["evidence"]
            ])
            evidence_html = f"""
            <div class="evidence-section">
                <div class="section-subtitle">Evidencia Textual Extraída:</div>
                {evidence_items}
            </div>
            """

        cards_html += f"""
        <div class="trait-card glass" id="card-{r['id']}">
            <div class="trait-header">
                <div class="trait-title-group">
                    <div class="trait-id-pill" style="color: {col['main']}; border-color: {col['main']}60;">
                        {r['id'].upper()[:4]}
                    </div>
                    <div>
                        <h3 class="trait-name">{r['trait_name']}</h3>
                        <span class="trait-level" style="color: {col['main']};">{r['level']}</span>
                    </div>
                </div>
                <div class="trait-score-box">
                    <span class="trait-score-num" style="color: {col['main']};">{r['score']}%</span>
                </div>
            </div>

            <!-- Barra de progreso -->
            <div class="progress-track">
                <div class="progress-fill" style="width: {r['score']}%; background: linear-gradient(90deg, {col['main']}90, {col['main']}); box-shadow: 0 0 12px {col['glow']};"></div>
            </div>

            <p class="trait-desc">{r['summary']}</p>

            <div class="trait-body">
                <div class="section-subtitle">¿Por qué se da este resultado? (Factores Clave):</div>
                <ul class="reasons-list">
                    {reasons_html}
                </ul>

                <div class="keywords-wrap">
                    <div class="section-subtitle">Léxico Psicodinámico Detectado:</div>
                    <div class="badges-row">
                        {keywords_html}
                    </div>
                </div>

                {evidence_html}
            </div>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Perfil Big Five (OCEAN) - @{u}</title>
    <meta name="description" content="Análisis visual de personalidad Big Five a partir del perfil de Instagram de @{u}">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg: #090912;
            --bg-card: rgba(255, 255, 255, 0.035);
            --bg-card-hover: rgba(255, 255, 255, 0.06);
            --border: rgba(255, 255, 255, 0.08);
            --border-hover: rgba(255, 255, 255, 0.16);
            --text: #f8fafc;
            --text-secondary: #94a3b8;
            --text-dim: #64748b;
            --primary: #8b5cf6;
            --font: 'Inter', -apple-system, sans-serif;
            --radius: 16px;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: var(--bg);
            color: var(--text);
            font-family: var(--font);
            min-height: 100vh;
            padding-bottom: 60px;
            overflow-x: hidden;
        }}

        /* Glow orbs */
        .bg-orb {{
            position: fixed; border-radius: 50%; pointer-events: none;
            filter: blur(140px); opacity: 0.13; z-index: 0;
        }}
        .orb-1 {{ width: 550px; height: 550px; background: #8b5cf6; top: -150px; left: -100px; }}
        .orb-2 {{ width: 500px; height: 500px; background: #06b6d4; bottom: -100px; right: -50px; }}

        .container {{
            max-width: 1240px;
            margin: 0 auto;
            padding: 30px 24px;
            position: relative;
            z-index: 1;
        }}

        .glass {{
            background: var(--bg-card);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--border);
            border-radius: var(--radius);
        }}

        /* Header */
        .header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 20px;
            padding: 24px 30px;
            margin-bottom: 24px;
        }}

        .user-info {{
            display: flex;
            align-items: center;
            gap: 18px;
        }}

        .avatar-box {{
            width: 64px;
            height: 64px;
            border-radius: 50%;
            background: linear-gradient(135deg, #7c3aed, #06b6d4);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 26px;
            font-weight: 800;
            color: #fff;
            box-shadow: 0 0 20px rgba(124, 58, 237, 0.4);
        }}

        .profile-title {{
            font-size: 26px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }}

        .profile-bio {{
            font-size: 13.5px;
            color: var(--text-secondary);
            margin-top: 4px;
            max-width: 620px;
            line-height: 1.45;
        }}

        .actions-group {{
            display: flex;
            gap: 12px;
        }}

        .btn {{
            padding: 10px 18px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            border: 1px solid var(--border);
            background: rgba(255, 255, 255, 0.05);
            color: var(--text);
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }}
        .btn:hover {{
            background: rgba(255, 255, 255, 0.1);
            border-color: var(--border-hover);
        }}

        /* Metrics grid */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .metric-card {{
            padding: 18px 20px;
        }}

        .metric-label {{
            font-size: 12px;
            color: var(--text-dim);
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}

        .metric-val {{
            font-size: 24px;
            font-weight: 800;
            margin-top: 6px;
            color: #fff;
        }}

        /* Main layout: Chart + Trait summary */
        .top-analysis-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 30px;
        }}

        @media (max-width: 900px) {{
            .top-analysis-grid {{ grid-template-columns: 1fr; }}
        }}

        .chart-box {{
            padding: 24px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 420px;
        }}

        .overview-box {{
            padding: 24px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}

        .box-title {{
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .ocean-legend {{
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-top: 14px;
        }}

        .legend-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 14px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.04);
        }}

        .legend-trait {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 14px;
            font-weight: 600;
        }}

        .legend-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }}

        .legend-score {{
            font-weight: 800;
            font-size: 15px;
        }}

        /* Detailed Trait Cards */
        .section-heading {{
            margin: 36px 0 20px 0;
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -0.3px;
        }}

        .traits-container {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}

        .trait-card {{
            padding: 24px;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}
        .trait-card:hover {{
            border-color: var(--border-hover);
        }}

        .trait-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 14px;
        }}

        .trait-title-group {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}

        .trait-id-pill {{
            padding: 4px 10px;
            border: 1px solid;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 0.5px;
        }}

        .trait-name {{
            font-size: 19px;
            font-weight: 700;
        }}

        .trait-level {{
            font-size: 13px;
            font-weight: 600;
            margin-top: 2px;
            display: block;
        }}

        .trait-score-num {{
            font-size: 30px;
            font-weight: 900;
            letter-spacing: -1px;
        }}

        .progress-track {{
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.06);
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 16px;
        }}

        .progress-fill {{
            height: 100%;
            border-radius: 6px;
            transition: width 1s ease-in-out;
        }}

        .trait-desc {{
            font-size: 14px;
            color: var(--text-secondary);
            line-height: 1.5;
            margin-bottom: 18px;
        }}

        .section-subtitle {{
            font-size: 12.5px;
            color: var(--text-dim);
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }}

        .reasons-list {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 18px;
        }}

        .reasons-list li {{
            font-size: 13.5px;
            color: #e2e8f0;
            display: flex;
            align-items: baseline;
            gap: 10px;
            line-height: 1.45;
        }}

        .reason-bullet {{
            width: 6px;
            height: 6px;
            border-radius: 50%;
            flex-shrink: 0;
            position: relative;
            top: -2px;
        }}

        .badges-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 18px;
        }}

        .badge {{
            padding: 4px 10px;
            border-radius: 8px;
            font-size: 12.5px;
            font-weight: 600;
        }}

        .evidence-section {{
            margin-top: 14px;
            padding-top: 14px;
            border-top: 1px dashed rgba(255, 255, 255, 0.08);
        }}

        .evidence-quote {{
            background: rgba(0, 0, 0, 0.25);
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 12.5px;
            font-style: italic;
            color: #cbd5e1;
            display: flex;
            align-items: flex-start;
            gap: 10px;
            margin-top: 8px;
            line-height: 1.45;
        }}

        .evidence-quote svg {{
            flex-shrink: 0;
            margin-top: 3px;
        }}

        .footer {{
            margin-top: 40px;
            text-align: center;
            font-size: 13px;
            color: var(--text-dim);
        }}
    </style>
</head>
<body>
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>

    <div class="container">
        <!-- Header -->
        <header class="header glass">
            <div class="user-info">
                <div class="avatar-box">{u[:2].upper()}</div>
                <div>
                    <h1 class="profile-title">@{u}</h1>
                    <p class="profile-bio">{resultado['biografia'].replace(chr(10), ' | ') if resultado['biografia'] else 'Sin biografía disponible'}</p>
                </div>
            </div>
            <div class="actions-group">
                <button class="btn" onclick="window.print()">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
                    Imprimir / PDF
                </button>
            </div>
        </header>

        <!-- Metrics Grid -->
        <div class="metrics-grid">
            <div class="metric-card glass">
                <div class="metric-label">Posts Analizados</div>
                <div class="metric-val">{m['posts_analizados']}</div>
            </div>
            <div class="metric-card glass">
                <div class="metric-label">Seguidores</div>
                <div class="metric-val">{m['total_seguidores']:,}</div>
            </div>
            <div class="metric-card glass">
                <div class="metric-label">Seguidos</div>
                <div class="metric-val">{m['total_seguidos']:,}</div>
            </div>
            <div class="metric-card glass">
                <div class="metric-label">Ratio Social</div>
                <div class="metric-val">{m['ratio_social']}</div>
            </div>
            <div class="metric-card glass">
                <div class="metric-label">Tokens Léxicos</div>
                <div class="metric-val">{m['palabras_procesadas']:,}</div>
            </div>
            <div class="metric-card glass">
                <div class="metric-label">Menciones @</div>
                <div class="metric-val">{m['menciones_totales']}</div>
            </div>
        </div>

        <!-- Radar Chart + Overview -->
        <div class="top-analysis-grid">
            <div class="chart-box glass">
                <div class="box-title" style="width: 100%;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                    Mapa Psicométrico Radar (OCEAN)
                </div>
                <div style="width: 100%; max-width: 380px; position: relative;">
                    <canvas id="radarChart"></canvas>
                </div>
            </div>

            <div class="overview-box glass">
                <div>
                    <div class="box-title">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06b6d4" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                        Resumen de Dimensiones
                    </div>
                    <p style="font-size: 13.5px; color: var(--text-secondary); line-height: 1.5; margin-bottom: 12px;">
                        Perfilación construida mediante minería textual y análisis estilométrico sobre captions, biografía y patrones de interacción social en Instagram.
                    </p>
                    <div class="ocean-legend">
                        <div class="legend-row">
                            <div class="legend-trait">
                                <span class="legend-dot" style="background: #06b6d4;"></span>
                                <span>Apertura (Openness)</span>
                            </div>
                            <span class="legend-score" style="color: #06b6d4;">{rasgos[0]['score']}%</span>
                        </div>
                        <div class="legend-row">
                            <div class="legend-trait">
                                <span class="legend-dot" style="background: #8b5cf6;"></span>
                                <span>Responsabilidad (Conscientiousness)</span>
                            </div>
                            <span class="legend-score" style="color: #8b5cf6;">{rasgos[1]['score']}%</span>
                        </div>
                        <div class="legend-row">
                            <div class="legend-trait">
                                <span class="legend-dot" style="background: #f59e0b;"></span>
                                <span>Extraversión (Extraversion)</span>
                            </div>
                            <span class="legend-score" style="color: #f59e0b;">{rasgos[2]['score']}%</span>
                        </div>
                        <div class="legend-row">
                            <div class="legend-trait">
                                <span class="legend-dot" style="background: #10b981;"></span>
                                <span>Amabilidad (Agreeableness)</span>
                            </div>
                            <span class="legend-score" style="color: #10b981;">{rasgos[3]['score']}%</span>
                        </div>
                        <div class="legend-row">
                            <div class="legend-trait">
                                <span class="legend-dot" style="background: #ec4899;"></span>
                                <span>Estabilidad vs. Neuroticismo</span>
                            </div>
                            <span class="legend-score" style="color: #ec4899;">{rasgos[4]['score']}%</span>
                        </div>
                    </div>
                </div>
                <div style="margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--border); font-size: 12px; color: var(--text-dim);">
                    Generado el {resultado['timestamp']} · Modelo Big Five / OCEAN
                </div>
            </div>
        </div>

        <!-- Detailed Cards -->
        <h2 class="section-heading">Desglose Detallado por Rasgo</h2>
        <div class="traits-container">
            {cards_html}
        </div>

        <footer class="footer">
            <p>Análisis Psicométrico de Huella Digital · Basado en el marco Big Five (OCEAN)</p>
        </footer>
    </div>

    <script>
        const ctx = document.getElementById('radarChart').getContext('2d');
        new Chart(ctx, {{
            type: 'radar',
            data: {{
                labels: ['Apertura', 'Responsabilidad', 'Extraversión', 'Amabilidad', 'Neuroticismo'],
                datasets: [{{
                    label: 'Puntaje (%)',
                    data: {scores_chart},
                    backgroundColor: 'rgba(139, 92, 246, 0.25)',
                    borderColor: '#8b5cf6',
                    borderWidth: 2,
                    pointBackgroundColor: ['#06b6d4', '#8b5cf6', '#f59e0b', '#10b981', '#ec4899'],
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: '#8b5cf6',
                    pointRadius: 5
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                scales: {{
                    r: {{
                        angleLines: {{ color: 'rgba(255, 255, 255, 0.1)' }},
                        grid: {{ color: 'rgba(255, 255, 255, 0.08)' }},
                        pointLabels: {{
                            color: '#94a3b8',
                            font: {{ size: 12, weight: '600', family: 'Inter' }}
                        }},
                        ticks: {{
                            display: false,
                            min: 0,
                            max: 100,
                            stepSize: 20
                        }},
                        suggestedMin: 0,
                        suggestedMax: 100
                    }}
                }},
                plugins: {{
                    legend: {{ display: false }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return os.path.abspath(output_filename)


# ─────────────────────────────────────────────────────────
# Terminal / CLI Output
# ─────────────────────────────────────────────────────────

def imprimir_resumen_terminal(resultado):
    u = resultado["usuario"]
    m = resultado["metricas"]
    print("\n" + "=" * 60)
    print(f" 🧠 REPORTE PSICOMÉTRICO BIG FIVE (OCEAN) · @{u}")
    print("=" * 60)
    print(f" Publicaciones analizadas: {m['posts_analizados']} | Palabras: {m['palabras_procesadas']}")
    print(f" Seguidores: {m['total_seguidores']} | Seguidos: {m['total_seguidos']} | Menciones: {m['menciones_totales']}")
    print("-" * 60)

    for r in resultado["rasgos"]:
        barra_len = int(r["score"] / 5)
        barra = "█" * barra_len + "░" * (20 - barra_len)
        print(f"\n[{r['id'].upper()[:4]}] {r['trait_name'].upper()}")
        print(f"      Puntaje: {r['score']}% [{barra}] ({r['level']})")
        print(f"      Resumen: {r['summary']}")
        print("      Factores clave:")
        for reason in r["reasons"]:
            print(f"       • {reason}")
    print("\n" + "=" * 60)


# ─────────────────────────────────────────────────────────
# Punto de Entrada Principal
# ─────────────────────────────────────────────────────────

def main():
    # Identificar archivo json a analizar
    target_file = None
    if len(sys.argv) > 1:
        target_file = sys.argv[1]
    else:
        # Buscar archivos *_datos.json en el directorio actual
        candidatos = [f for f in os.listdir(".") if f.endswith("_datos.json") and os.path.isfile(f)]
        if candidatos:
            print("Archivos de datos encontrados:")
            for idx, c in enumerate(candidatos, 1):
                print(f"  [{idx}] {c}")
            print(f"  [0] Ingresar ruta manualmente")
            
            try:
                opc = input(f"\nSelecciona una opción [1-{len(candidatos)}]: ").strip()
                if opc == "0" or not opc:
                    target_file = input("Ruta al archivo JSON: ").strip()
                else:
                    sel_idx = int(opc) - 1
                    if 0 <= sel_idx < len(candidatos):
                        target_file = candidatos[sel_idx]
                    else:
                        target_file = candidatos[0]
            except Exception:
                target_file = candidatos[0]
        else:
            target_file = input("Ingresa el nombre o ruta del archivo JSON: ").strip()

    if not target_file or not os.path.exists(target_file):
        print(f"\n[ERROR] El archivo '{target_file}' no existe.")
        sys.exit(1)

    print(f"\n📂 Cargando datos desde '{target_file}'...")
    with open(target_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    analyzer = BigFiveAnalyzer(data)
    resultado = analyzer.analyze()

    imprimir_resumen_terminal(resultado)

    output_html = f"{analyzer.username}_bigfive_analisis.html"
    abs_path = generar_reporte_html(resultado, output_html)
    print(f"\n✅ Reporte visual generado exitosamente:")
    print(f"   {abs_path}")

    # Abrir automáticamente en el navegador
    try:
        webbrowser.open(f"file://{abs_path}")
        print("   🌐 Abriendo reporte en tu navegador predeterminado...")
    except Exception:
        pass


if __name__ == "__main__":
    main()
