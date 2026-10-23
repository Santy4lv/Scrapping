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

import argparse
import os
import sys
import json
import re
import math
import webbrowser
from collections import Counter
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
    from google.genai import types
    HAVE_GEMINI_SDK = True
except ImportError:
    HAVE_GEMINI_SDK = False

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
    def __init__(self, data, api_key=None, model_name="gemini-3.5-flash"):
        self.data = data
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or "gemini-3.5-flash"
        self.username = data.get("perfil", "usuario_desconocido")
        self.bio = data.get("biografia", "")
        self.avatar_url = data.get("foto_perfil_url", "")
        self.avatar_local = data.get("foto_perfil_local", "")
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

    def analyze(self, force_offline=False):
        """Ejecuta el análisis. Si hay API key disponible y no se fuerza offline, usa Gemini AI."""
        if not force_offline and self.api_key:
            try:
                return self._analyze_gemini(self.api_key)
            except Exception as e:
                print(f"\n[AVISO IA] No se pudo completar el análisis con Gemini API ({e}).")
                print("           Activando motor heurístico léxico de contingencia...\n")
        elif not self.api_key and not force_offline:
            print("\n[INFO] No se detectó GEMINI_API_KEY. Usando motor psicométrico léxico offline.\n")

        return self._analyze_heuristic()

    def _analyze_gemini(self, api_key: str):
        if not HAVE_GEMINI_SDK:
            raise RuntimeError("El SDK 'google-genai' no está instalado en este entorno de Python.")

        client = genai.Client(api_key=api_key)

        # Preparar contexto enriquecido de las publicaciones
        posts_context = []
        for i, p in enumerate(self.posts[:20], 1):
            comms_sample = [c.get("texto", "") for c in p.get("comentarios", [])[:3] if c.get("texto")]
            posts_context.append({
                "post_num": i,
                "caption": p.get("caption", ""),
                "hashtags": p.get("hashtags", []),
                "menciones": p.get("menciones", []),
                "likes": p.get("likes", 0),
                "tipo_media": p.get("tipo_media", "image"),
                "alt_texto": p.get("alt_texto", ""),
                "comentarios_muestra": comms_sample
            })

        user_context = {
            "usuario": self.username,
            "biografia": self.bio,
            "total_seguidores": self.total_followers,
            "total_seguidos": self.total_following,
            "total_posts_perfil": self.posts_count,
            "publicaciones": posts_context
        }

        prompt = f"""
Actúa como un psicólogo computacional senior y evaluador psicométrico experto en el modelo de los Cinco Grandes Factores de la Personalidad (Big Five / OCEAN):
1. Apertura a la Experiencia (Openness)
2. Responsabilidad / Conciencia (Conscientiousness)
3. Extraversión (Extraversion)
4. Amabilidad / Afabilidad (Agreeableness)
5. Estabilidad Emocional vs. Neuroticismo (Neuroticism) - Importante: en neuroticismo un puntaje bajo (ej: 15-35%) indica alta estabilidad emocional y serenidad, mientras que un puntaje alto (ej: 70-95%) denota alta reactividad o vulnerabilidad al estrés.

Analiza minuciosamente los siguientes datos reales extraídos de la cuenta de Instagram de @{self.username}:
{json.dumps(user_context, ensure_ascii=False, indent=2)}

Directrices de análisis:
- Basa tu evaluación estricta y genuinamente en el contenido real observado en las publicaciones, tono de captions, temas de interés, bio, humor, léxico y dinámica de interacción social.
- Para cada uno de los 5 rasgos (openness, conscientiousness, extraversion, agreeableness, neuroticism) debes proporcionar:
  * "score": un número entero o decimal entre 10 y 98 que represente el porcentaje de presencia de dicho rasgo.
  * "level": nivel cualitativo ("Muy Alto", "Alto", "Moderado", "Bajo", "Muy Bajo", o en neuroticismo "Muy Estable (Neuroticismo Muy Bajo)", "Estable", "Equilibrado", "Reactivo").
  * "summary": síntesis ejecutiva clara y concisa (1 o 2 oraciones) específica para este usuario.
  * "reasons": lista de exactamente 3 razones bien argumentadas con factores conductuales y evidencias contextuales específicas del perfil.
  * "evidence": lista de 2 a 3 citas textuales reales del usuario (de sus captions o biografía) que ilustren este rasgo. Si el usuario no escribe textos largos, cita frases, emojis o palabras exactas.
  * "keywords": lista de pares [palabra_clave, frecuencia_estimada] representativas detectadas en su perfil para este rasgo.

Además, proporciona un perfil global:
- "arquetipo": Título evocador y profesional del arquetipo de personalidad (ej: 'El Estratega Analítico & Conector Social', 'El Creador Lúdico & Afectuoso', 'El Explorador Autónomo & Comunicativo').
- "sintesis_psicologica": Análisis narrativo psicológico profundo (2 a 3 párrafos de alta calidad) sobre su cosmovisión, estilo de vida, relación interpersonal, manejo emocional y motivación primaria.
- "estilo_comunicacion": Descripción concisa del tono de comunicación (ej: 'Cálido, espontáneo y lúdico con fuerte apego afectivo').
- "fortalezas": Lista de 3 o 4 fortalezas conductuales clave.
- "areas_observacion": Lista de 2 tendencias o áreas de observación conductual.

Responde ÚNICAMENTE en formato JSON con la siguiente estructura exacta:
{{
  "arquetipo": string,
  "sintesis_psicologica": string,
  "estilo_comunicacion": string,
  "fortalezas": [string, string, string],
  "areas_observacion": [string, string],
  "rasgos": {{
    "openness": {{
      "score": number,
      "level": string,
      "summary": string,
      "reasons": [string, string, string],
      "evidence": [string, string],
      "keywords": [[string, number]]
    }},
    "conscientiousness": {{
      "score": number,
      "level": string,
      "summary": string,
      "reasons": [string, string, string],
      "evidence": [string, string],
      "keywords": [[string, number]]
    }},
    "extraversion": {{
      "score": number,
      "level": string,
      "summary": string,
      "reasons": [string, string, string],
      "evidence": [string, string],
      "keywords": [[string, number]]
    }},
    "agreeableness": {{
      "score": number,
      "level": string,
      "summary": string,
      "reasons": [string, string, string],
      "evidence": [string, string],
      "keywords": [[string, number]]
    }},
    "neuroticism": {{
      "score": number,
      "level": string,
      "summary": string,
      "reasons": [string, string, string],
      "evidence": [string, string],
      "keywords": [[string, number]]
    }}
  }}
}}
"""

        models_to_try = [
            self.model_name,
            "gemini-3.5-flash",
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-flash-latest",
            "gemini-2.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash",
        ]
        unique_models = []
        for m in models_to_try:
            if m and m not in unique_models:
                unique_models.append(m)

        last_error = None
        for model in unique_models:
            try:
                print(f"🤖 Solicitando análisis psicométrico a Google Gemini ({model})...")
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                    )
                )
                raw_text = response.text.strip()
                if raw_text.startswith("```"):
                    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
                    raw_text = re.sub(r"\s*```$", "", raw_text)
                parsed = json.loads(raw_text)
                return self._build_gemini_result(parsed, model)
            except Exception as e:
                last_error = e
                print(f"   [AVISO] Intento con {model} no completado: {e}")

        raise last_error or RuntimeError("Todos los intentos con Gemini fallaron.")

    def _build_gemini_result(self, parsed: dict, model_used: str):
        total_posts_analyzed = len(self.posts)
        avg_caption_len = (sum(len(c) for c in self.all_captions) / total_posts_analyzed) if total_posts_analyzed else 0
        ratio_social = (self.total_followers / max(self.total_following, 1))

        trait_names_map = {
            "openness": ("Apertura a la Experiencia", "Openness"),
            "conscientiousness": ("Responsabilidad y Tesón", "Conscientiousness"),
            "extraversion": ("Extraversión", "Extraversion"),
            "agreeableness": ("Amabilidad y Afabilidad", "Agreeableness"),
            "neuroticism": ("Estabilidad Emocional vs. Neuroticismo", "Neuroticism"),
        }

        traits_data = []
        raw_traits = parsed.get("rasgos", {})

        for t_id, (t_es, t_en) in trait_names_map.items():
            t_obj = raw_traits.get(t_id, {})
            score = float(t_obj.get("score", 50.0))
            score = round(min(max(score, 10.0), 98.0), 1)

            traits_data.append({
                "id": t_id,
                "trait_name": t_es,
                "trait_en": t_en,
                "score": score,
                "level": t_obj.get("level", self._get_level(score, inverse=(t_id == "neuroticism"))),
                "summary": t_obj.get("summary", ""),
                "reasons": t_obj.get("reasons", []),
                "keywords": t_obj.get("keywords", []),
                "evidence": t_obj.get("evidence", []),
            })

        return {
            "usuario": self.username,
            "biografia": self.bio,
            "foto_perfil_url": self.avatar_url,
            "foto_perfil_local": self.avatar_local,
            "motor_analisis": f"Google Gemini ({model_used})",
            "es_ia": True,
            "arquetipo": parsed.get("arquetipo", "Perfil Multidimensional"),
            "sintesis_psicologica": parsed.get("sintesis_psicologica", ""),
            "estilo_comunicacion": parsed.get("estilo_comunicacion", ""),
            "fortalezas": parsed.get("fortalezas", []),
            "areas_observacion": parsed.get("areas_observacion", []),
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

    def _analyze_heuristic(self):
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

        # 1. OPENNESS (Apertura)
        open_count, open_matches = self._count_lexicon(LEXICONS["openness"]["keywords"])
        open_density = (open_count / self.total_words) * 1000
        open_score = 48 + (open_density * 3.4) + (min(hashtags_per_post, 5) * 2.5)
        if any(w in self.full_corpus for w in ["datos", "innovación", "creatividad", "arte", "tecnología"]):
            open_score += 6
        open_score = min(max(round(open_score, 1), 15), 96)
        
        open_reasons = [
            f"Frecuencia de términos vinculados a innovación, conocimiento y expresión creativa ({open_count} apariciones clave).",
            f"Diversidad de contenido y amplitud temática en publicaciones ('{', '.join([m[0] for m in open_matches[:4]]) if open_matches else 'intereses generales'}').",
            f"Uso de etiquetas temáticas e interconexión ({len(set(self.all_hashtags))} hashtags distintos)."
        ]

        # 2. CONSCIENTIOUSNESS (Responsabilidad)
        cons_count, cons_matches = self._count_lexicon(LEXICONS["conscientiousness"]["keywords"])
        cons_density = (cons_count / self.total_words) * 1000
        cons_score = 46 + (cons_density * 3.6) + (min(avg_caption_len / 40, 8))
        if any(w in self.bio.lower() for w in ["trabajo", "meta", "disciplina", "profesional", "oficial"]):
            cons_score += 7
        cons_score = min(max(round(cons_score, 1), 20), 97)

        cons_reasons = [
            f"Presencia de vocabulario orientado a disciplina, consistencia y propósitos ({cons_count} menciones).",
            f"Estructura comunicativa ordenada y longitud promedio de descripciones ({int(avg_caption_len)} caracteres por post).",
            f"Narrativa de constancia y balance entre actividades personales y formativas/laborales."
        ]

        # 3. EXTRAVERSION (Extraversión)
        extra_count, extra_matches = self._count_lexicon(LEXICONS["extraversion"]["keywords"])
        extra_density = (extra_count / self.total_words) * 1000
        exclamation_count = self.full_corpus.count("!")
        extra_score = 45 + (extra_density * 3.2) + (min(mentions_per_post, 4) * 4.0) + (min(exclamation_count / 10, 5))
        extra_score = min(max(round(extra_score, 1), 18), 95)

        extra_reasons = [
            f"Frecuencia de menciones y apertura hacia redes interpersonales ({len(self.all_mentions)} menciones '@' detectadas).",
            f"Tono discursivo comunicativo y dirigido hacia audiencias ('{', '.join([m[0] for m in extra_matches[:4]]) if extra_matches else 'lenguaje cercano'}').",
            f"Ratio social de {ratio_social:.2f} con una comunidad activa de {self.total_followers} seguidores."
        ]

        # 4. AGREEABLENESS (Amabilidad / Afabilidad)
        agree_count, agree_matches = self._count_lexicon(LEXICONS["agreeableness"]["keywords"])
        agree_density = (agree_count / self.total_words) * 1000
        agree_score = 42 + (agree_density * 4.2) + (min(emoji_counts["positive"], 10) * 1.5)
        if any(w in self.bio.lower() for w in ["amor", "familia", "gracias", "amigos"]):
            agree_score += 8
        agree_score = min(max(round(agree_score, 1), 20), 98)

        agree_reasons = [
            f"Expresiones de afecto, gratitud o cercanía interpersonal ({agree_count} apariciones léxicas).",
            f"Presencia de elementos empáticos, calidez emocional y emojis positivos ({emoji_counts['positive']} detectados).",
            f"Tono constructivo, accesible y sin confrontaciones abiertas en sus publicaciones."
        ]

        # 5. NEUROTICISM (Neuroticismo / Reactividad Emocional)
        neuro_count, neuro_matches = self._count_lexicon(LEXICONS["neuroticism"]["keywords"])
        neuro_density = (neuro_count / self.total_words) * 1000
        neuro_score = 25 + (neuro_density * 4.5) + (min(emoji_counts["stress_urgency"], 5) * 3)
        if agree_score > 65 and cons_score > 65:
            neuro_score = max(neuro_score - 8, 18)
        neuro_score = min(max(round(neuro_score, 1), 12), 85)

        neuro_reasons = [
            f"Baja frecuencia de términos vinculados a estrés, quejas o reactividad ({neuro_count} términos de alerta).",
            f"Manejo comunicativo sereno, constructivo y enfocado en momentos vitales positivos.",
            f"Equilibrio emocional observable en el balance entre afabilidad y constancia en sus publicaciones."
        ]

        traits_data = [
            {
                "id": "openness",
                "trait_name": "Apertura a la Experiencia",
                "trait_en": "Openness",
                "score": open_score,
                "level": self._get_level(open_score),
                "summary": "Curiosidad intelectual, apreciación estética y receptividad a nuevas ideas e intereses.",
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
                "summary": "Autodisciplina, constancia en metas y orientación organizada hacia actividades de su interés.",
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
                "summary": "Sociabilidad, entusiasmo interactivo y energía canalizada hacia su comunidad digital.",
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
                "summary": "Empatía, valoración de vínculos significativos y disposición colaborativa.",
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
                "summary": "Nivel bajo de neuroticismo refleja alta estabilidad, compostura y control afectivo.",
                "reasons": neuro_reasons,
                "keywords": neuro_matches[:6],
                "evidence": self._extract_evidence_snippets(LEXICONS["neuroticism"]["keywords"][:6])
            }
        ]

        # Determinar arquetipo heurístico
        if agree_score >= 65 and extra_score >= 60:
            arquetipo = "El Conector Social Empático"
        elif open_score >= 65 and cons_score >= 60:
            arquetipo = "El Estratega Analítico & Creador"
        elif cons_score >= 65:
            arquetipo = "El Realizador Disciplinado"
        elif agree_score >= 65:
            arquetipo = "El Cuidador Afectuoso & Colaborador"
        else:
            arquetipo = "El Observador Autónomo & Pragmático"

        return {
            "usuario": self.username,
            "biografia": self.bio,
            "foto_perfil_url": self.avatar_url,
            "foto_perfil_local": self.avatar_local,
            "motor_analisis": "Motor Heurístico Léxico (Offline)",
            "es_ia": False,
            "arquetipo": arquetipo,
            "sintesis_psicologica": (
                f"El perfil digital de @{self.username} proyecta una personalidad orientada a "
                f"{'vínculos humanos cercanos y calidez afectiva' if agree_score > 60 else 'intereses temáticos focalizados y comunicación directa'}. "
                f"Presenta un nivel de responsabilidad del {cons_score}% y una estabilidad emocional favorable con {neuro_score}% en reactividad al estrés."
            ),
            "estilo_comunicacion": "Expresivo y selectivo, centrado en vivencias personales.",
            "fortalezas": [
                "Estabilidad emocional y control reflexivo",
                "Capacidad de conexión con círculos afines",
                "Constancia en el mensaje y estilo propio"
            ],
            "areas_observacion": [
                "Exploración de mayor variedad de temas conceptuales",
                "Ampliación del alcance interactivo con otras comunidades"
            ],
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

    avatar_src = resultado.get("foto_perfil_local") or resultado.get("foto_perfil_url")
    if avatar_src:
        avatar_html = f'<img src="{avatar_src}" alt="{u}" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover;" onerror="this.onerror=null; this.parentElement.innerText=\'{u[:2].upper()}\';">'
    else:
        avatar_html = u[:2].upper()

    es_ia = resultado.get("es_ia", False)
    motor = resultado.get("motor_analisis", "Análisis Heurístico")
    if es_ia:
        badge_html = f'<div class="engine-badge ai-badge"><span class="badge-sparkle">✨</span> {motor}</div>'
    else:
        badge_html = f'<div class="engine-badge offline-badge"><span>⚙️</span> {motor}</div>'

    arquetipo = resultado.get("arquetipo", "Perfil Multidimensional")
    sintesis = resultado.get("sintesis_psicologica", "")
    estilo_com = resultado.get("estilo_comunicacion", "")
    fortalezas = resultado.get("fortalezas", [])
    observaciones = resultado.get("areas_observacion", [])

    fortalezas_html = "".join([f"<li><span class='bullet-icon text-green'>✓</span><span>{f}</span></li>" for f in fortalezas]) if fortalezas else "<li>Análisis general en progreso</li>"
    observaciones_html = "".join([f"<li><span class='bullet-icon text-amber'>•</span><span>{o}</span></li>" for o in observaciones]) if observaciones else "<li>Sin observaciones críticas</li>"

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

        .engine-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 11.5px;
            font-weight: 700;
            letter-spacing: 0.3px;
        }}
        .ai-badge {{
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(6, 182, 212, 0.2));
            color: #c084fc;
            border: 1px solid rgba(192, 132, 252, 0.35);
            box-shadow: 0 0 15px rgba(139, 92, 246, 0.2);
        }}
        .offline-badge {{
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-secondary);
            border: 1px solid var(--border);
        }}
        .synthesis-card {{
            padding: 26px 30px;
            margin-bottom: 24px;
            position: relative;
            overflow: hidden;
        }}
        .synthesis-card::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: linear-gradient(90deg, #8b5cf6, #06b6d4, #10b981);
        }}
        .synthesis-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 14px;
            margin-bottom: 16px;
        }}
        .archetype-tag {{
            font-size: 11.5px;
            font-weight: 700;
            color: #38bdf8;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 5px;
            margin-bottom: 4px;
        }}
        .archetype-title {{
            font-size: 24px;
            font-weight: 800;
            letter-spacing: -0.4px;
            background: linear-gradient(135deg, #ffffff, #cbd5e1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .comm-style-tag {{
            font-size: 12.5px;
            color: var(--text-secondary);
            background: rgba(255, 255, 255, 0.04);
            padding: 8px 14px;
            border-radius: 10px;
            border: 1px solid var(--border);
        }}
        .synthesis-text {{
            font-size: 14.5px;
            line-height: 1.7;
            color: #cbd5e1;
            margin-bottom: 20px;
        }}
        .insights-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
        }}
        .insight-box {{
            padding: 16px 20px;
            border-radius: 12px;
            background: rgba(0, 0, 0, 0.2);
        }}
        .insight-title {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}
        .text-green {{ color: #34d399; }}
        .text-amber {{ color: #fbbf24; }}
        .insight-list {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .insight-list li {{
            font-size: 13px;
            color: var(--text-secondary);
            display: flex;
            align-items: flex-start;
            gap: 10px;
            line-height: 1.45;
        }}
        .bullet-icon {{
            font-weight: 800;
            flex-shrink: 0;
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
                <div class="avatar-box" style="overflow: hidden; padding: 0;">{avatar_html}</div>
                <div>
                    <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                        <h1 class="profile-title">@{u}</h1>
                        {badge_html}
                    </div>
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

        <!-- Executive Psychological Synthesis -->
        <div class="synthesis-card glass">
            <div class="synthesis-header">
                <div>
                    <div class="archetype-tag">
                        <span>✨</span> Arquetipo de Personalidad
                    </div>
                    <h2 class="archetype-title">{arquetipo}</h2>
                </div>
                {f'<div class="comm-style-tag"><strong>Estilo de Comunicación:</strong> {estilo_com}</div>' if estilo_com else ''}
            </div>
            <div class="synthesis-body">
                <div class="section-subtitle">Síntesis Psicológica Integral:</div>
                <p class="synthesis-text">{sintesis.replace(chr(10), '<br><br>')}</p>
            </div>
            <div class="insights-grid">
                <div class="insight-box glass">
                    <div class="insight-title text-green">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        Fortalezas Conductuales Clave
                    </div>
                    <ul class="insight-list">
                        {fortalezas_html}
                    </ul>
                </div>
                <div class="insight-box glass">
                    <div class="insight-title text-amber">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                        Áreas de Observación & Dinámica
                    </div>
                    <ul class="insight-list">
                        {observaciones_html}
                    </ul>
                </div>
            </div>
        </div>

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
    motor = resultado.get("motor_analisis", "Heurístico")
    arquetipo = resultado.get("arquetipo", "Perfil Multidimensional")
    estilo = resultado.get("estilo_comunicacion", "")
    sintesis = resultado.get("sintesis_psicologica", "")
    fortalezas = resultado.get("fortalezas", [])

    print("\n" + "=" * 65)
    print(f" 🧠 REPORTE PSICOMÉTRICO BIG FIVE (OCEAN) · @{u}")
    print(f" ⚙️  Motor: {motor}")
    print("=" * 65)
    print(f" ✨ Arquetipo: {arquetipo}")
    if estilo:
        print(f" 🗣️  Estilo: {estilo}")
    print(f" 📊 Posts analizados: {m['posts_analizados']} | Palabras: {m['palabras_procesadas']}")
    print(f" 👥 Seguidores: {m['total_seguidores']:,} | Seguidos: {m['total_seguidos']:,} | Menciones: {m['menciones_totales']}")
    print("-" * 65)

    if sintesis:
        print("\n📝 SÍNTESIS PSICOLÓGICA:")
        for par in sintesis.split("\n"):
            if par.strip():
                print(f"   {par.strip()}")
        print("-" * 65)

    if fortalezas:
        print("\n🌟 FORTALEZAS CONDUCTUALES CLAVE:")
        for f in fortalezas:
            print(f"   ✓ {f}")
        print("-" * 65)

    print("\nDIMENSIONES BIG FIVE (OCEAN):")
    for r in resultado["rasgos"]:
        barra_len = int(r["score"] / 5)
        barra = "█" * barra_len + "░" * (20 - barra_len)
        print(f"\n[{r['id'].upper()[:4]}] {r['trait_name'].upper()}")
        print(f"      Puntaje: {r['score']}% [{barra}] ({r['level']})")
        print(f"      Resumen: {r['summary']}")
        print("      Factores clave:")
        for reason in r["reasons"]:
            print(f"       • {reason}")
        if r.get("evidence"):
            print("      Evidencias extraídas:")
            for ev in r["evidence"][:2]:
                print(f"       💬 \"{ev}\"")
    print("\n" + "=" * 65)


# ─────────────────────────────────────────────────────────
# Punto de Entrada Principal
# ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Analizador Psicométrico Big Five (OCEAN) para Instagram")
    parser.add_argument("archivo", nargs="?", default=None, help="Ruta al archivo JSON de datos extraídos")
    parser.add_argument("--api-key", default=None, help="Google Gemini API Key (o definir GEMINI_API_KEY en .env)")
    parser.add_argument("--model", default="gemini-3.5-flash", help="Modelo de Gemini (por defecto: gemini-3.5-flash)")
    parser.add_argument("--offline", action="store_true", help="Forzar análisis léxico heurístico offline sin usar la API de Gemini")
    args = parser.parse_args()

    target_file = args.archivo
    if not target_file:
        candidatos = [f for f in os.listdir(".") if f.endswith("_datos.json") and os.path.isfile(f)]
        if candidatos:
            print("\nArchivos de datos encontrados:")
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

    api_key = args.api_key or os.getenv("GEMINI_API_KEY")

    if not args.offline and not api_key:
        print("\n" + "─" * 65)
        print("💡 Puedes analizar este perfil con Inteligencia Artificial (Google Gemini)")
        print("   o presionar Enter para usar el motor psicométrico léxico local (offline).")
        print("─" * 65)
        key_input = input("🔑 Ingresa tu Gemini API Key (Enter para offline): ").strip()
        if key_input:
            api_key = key_input
            try:
                guardar = input("💾 ¿Deseas guardar la API Key en tu archivo .env? [s/N]: ").strip().lower()
                if guardar in ["s", "si", "y", "yes"]:
                    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
                    line_to_add = f"\nGEMINI_API_KEY={api_key}\n"
                    with open(env_path, "a", encoding="utf-8") as env_f:
                        env_f.write(line_to_add)
                    print(f"✅ API Key guardada exitosamente en '{env_path}'.")
            except Exception as e:
                print(f"[AVISO] No se pudo escribir en .env: {e}")

    print(f"\n📂 Cargando datos desde '{target_file}'...")
    with open(target_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    analyzer = BigFiveAnalyzer(data, api_key=api_key, model_name=args.model)
    resultado = analyzer.analyze(force_offline=args.offline)

    imprimir_resumen_terminal(resultado)

    output_html = f"{analyzer.username}_bigfive_analisis.html"
    abs_path = generar_reporte_html(resultado, output_html)
    print(f"\n✅ Reporte visual generado exitosamente:")
    print(f"   {abs_path}")

    try:
        webbrowser.open(f"file://{abs_path}")
        print("   🌐 Abriendo reporte en tu navegador predeterminado...")
    except Exception:
        pass


if __name__ == "__main__":
    main()
