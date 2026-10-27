/**
 * bigfive.js - Motor Psicométrico Big Five (OCEAN)
 * Soporta análisis con IA (Google Gemini API REST) y motor léxico local de contingencia.
 */

const BIGFIVE_LEXICONS = {
    openness: {
        nombre: 'Apertura a la Experiencia',
        en: 'Openness',
        keywords: [
            'aprender', 'aprendizaje', 'innovar', 'innovacion', 'datos', 'creatividad',
            'ideas', 'estrategia', 'cultura', 'vision', 'conectar', 'perspectiva',
            'tecnologia', 'digital', 'futuro', 'cambio', 'reto', 'conocimiento', 'ciencia',
            'arte', 'analisis', 'pensar', 'reflexion', 'crear', 'diseno', 'investigar'
        ]
    },
    conscientiousness: {
        nombre: 'Responsabilidad / Conciencia',
        en: 'Conscientiousness',
        keywords: [
            'trabajo', 'labor', 'organizar', 'orden', 'puntual', 'disciplina', 'tareas',
            'resultado', 'resultados', 'meta', 'metas', 'objetivo', 'campana', 'responsable',
            'compromiso', 'esfuerzo', 'constancia', 'logro', 'logros', 'profesional',
            'preparar', 'cumplir', 'plan', 'planificar', 'calidad'
        ]
    },
    extraversion: {
        nombre: 'Extraversión / Energía Social',
        en: 'Extraversion',
        keywords: [
            'gente', 'personas', 'equipo', 'amigos', 'comunidad', 'hablar', 'social',
            'evento', 'fiesta', 'celebrar', 'publico', 'compartir', 'juntos', 'vamos',
            'bienvenidos', 'hola', 'abrazos', 'vivir', 'feliz', 'entusiasmo', 'actitud'
        ]
    },
    agreeableness: {
        nombre: 'Amabilidad / Afabilidad',
        en: 'Agreeableness',
        keywords: [
            'amor', 'carino', 'agradezco', 'gracias', 'honor', 'familia', 'hijos', 'mama',
            'papa', 'bendicion', 'cuidar', 'ayudar', 'colaborar', 'apoyo', 'respeto',
            'solidaridad', 'empatia', 'corazon', 'generosidad', 'amabilidad', 'paz', 'confianza'
        ]
    },
    neuroticism: {
        nombre: 'Estabilidad Emocional vs Reactividad',
        en: 'Neuroticism',
        keywords: [
            'miedo', 'temor', 'ansiedad', 'estres', 'crisis', 'dificil', 'preocupacion',
            'cansancio', 'tristeza', 'angustia', 'problema', 'tension', 'frustracion',
            'incertidumbre', 'presion', 'dolor', 'queja', 'alerta', 'caos'
        ]
    }
};

/**
 * Normaliza y tokeniza texto en español
 */
function tokenizeWords(text) {
    if (!text) return [];
    return text
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^\w\s]/g, ' ')
        .split(/\s+/)
        .filter(w => w.length > 2);
}

/**
 * Motor Heurístico Léxico Local (Fallback offline y transparente)
 */
function analyzeBigFiveLocalFallback(data) {
    if (!data) return null;
    const posts = Array.isArray(data.publicaciones) ? data.publicaciones : [];
    const bio = data.biografia || '';
    const captions = posts.map(p => p.caption || '').filter(Boolean);
    const fullText = (bio + ' ' + captions.join(' ')).toLowerCase();
    const tokens = tokenizeWords(fullText);
    const totalWords = Math.max(tokens.length, 1);

    const traits = [];
    const scoresMap = {};

    Object.keys(BIGFIVE_LEXICONS).forEach(traitKey => {
        const info = BIGFIVE_LEXICONS[traitKey];
        const normalizedKeywords = info.keywords.map(k => k.normalize('NFD').replace(/[\u0300-\u036f]/g, ''));
        let count = 0;
        const matched = [];

        tokens.forEach(tok => {
            if (normalizedKeywords.includes(tok)) {
                count++;
                if (!matched.includes(tok)) matched.push(tok);
            }
        });

        const density = (count / totalWords) * 1000;
        let baseScore = 48 + (density * 3.5);
        if (traitKey === 'neuroticism') {
            baseScore = Math.max(15, Math.min(85, Math.round((25 + (density * 4.0)) * 10) / 10));
        } else {
            baseScore = Math.max(20, Math.min(95, Math.round(baseScore * 10) / 10));
        }
        scoresMap[traitKey] = baseScore;

        let level = 'Moderado';
        if (traitKey === 'neuroticism') {
            level = baseScore <= 35 ? 'Muy Estable (Bajo)' : baseScore <= 55 ? 'Estable' : 'Reactivo';
        } else {
            level = baseScore >= 75 ? 'Muy Alto' : baseScore >= 60 ? 'Alto' : baseScore >= 40 ? 'Moderado' : 'Bajo';
        }

        traits.push({
            trait_id: traitKey,
            trait_name: info.nombre,
            trait_en: info.en,
            score: baseScore,
            level: level,
            summary: `Presencia ${level.toLowerCase()} (${baseScore}%) basada en densidad léxica contextual.`,
            reasons: [
                `Detección de ${count} apariciones de términos representativos (${matched.slice(0, 4).join(', ') || 'patrón estándar'}).`,
                `Densidad léxica estimada de ${density.toFixed(2)} palabras clave por cada mil vocablos.`,
                `Consistencia discursiva analizada en bio y ${captions.length} publicaciones.`
            ],
            evidence: matched.slice(0, 3).map(w => `Uso clave de '${w}' en publicaciones`),
            keywords: matched.slice(0, 5).map(w => [w, 1])
        });
    });

    const arquetipo = scoresMap.openness >= 60 && scoresMap.agreeableness >= 60
        ? 'El Creador Empático & Conector Social'
        : scoresMap.conscientiousness >= 60
        ? 'El Estratega Disciplinado & Enfocado'
        : 'Perfil Multidimensional';

    return {
        es_ia: false,
        motor: 'Motor Léxico Local (Fallback)',
        arquetipo: arquetipo,
        sintesis_psicologica: `El perfil analizado exhibe un patrón de personalidad evaluado mediante el modelo de los Cinco Grandes Factores (OCEAN). Su comunicación refleja un equilibrio adaptativo con énfasis en ${traits[0].trait_name.toLowerCase()} y dinámica social constructiva.`,
        estilo_comunicacion: 'Cercano, comunicativo y estructurado según temáticas de interés.',
        fortalezas: [
            'Capacidad de expresión y conexión temática',
            'Enfoque consistente en sus publicaciones',
            'Estabilidad comunicativa en interacciones'
        ],
        areas_observacion: [
            'Variabilidad en frecuencia de interacción',
            'Amplitud de nichos explorados'
        ],
        rasgos: traits,
        timestamp: new Date().toLocaleString()
    };
}

const GEMINI_CANDIDATE_MODELS = [
    'gemini-3.5-flash-lite',
    'gemini-3.5-flash',
    'gemini-flash-lite-latest',
    'gemini-3.8-flash',
    'gemini-3.6-flash',
    'gemini-3.7-flash',
    'gemini-2.5-flash-lite'
];

/**
 * Motor IA con Google Gemini API REST con cascada automática de modelos
 */
async function analyzeBigFiveWithGemini(data, apiKey, preferredModel = null) {
    if (!apiKey) throw new Error('API Key de Gemini no proporcionada');
    if (!data) throw new Error('Datos del perfil vacíos');

    const posts = (data.publicaciones || []).slice(0, 15).map((p, idx) => ({
        n: idx + 1,
        caption: (p.caption || '').slice(0, 300),
        hashtags: (p.hashtags || []).slice(0, 5),
        likes: p.likes || 0
    }));

    const prompt = `
Actúa como psicólogo computacional senior. Analiza la personalidad según el modelo Big Five (OCEAN) para este perfil de Instagram:
Usuario: @${data.perfil || 'usuario'}
Bio: ${data.biografia || 'Sin biografía'}
Muestra de publicaciones:
${JSON.stringify(posts, null, 2)}

Devuelve ÚNICAMENTE un JSON con este formato exacto:
{
  "arquetipo": "Título representativo",
  "sintesis_psicologica": "Resumen narrativo de 2 párrafos",
  "estilo_comunicacion": "Descripción de 1 línea",
  "fortalezas": ["F1", "F2", "F3"],
  "areas_observacion": ["A1", "A2"],
  "rasgos": {
    "openness": { "score": 85, "level": "Muy Alto", "summary": "...", "reasons": ["r1", "r2", "r3"] },
    "conscientiousness": { "score": 75, "level": "Alto", "summary": "...", "reasons": ["r1", "r2", "r3"] },
    "extraversion": { "score": 70, "level": "Alto", "summary": "...", "reasons": ["r1", "r2", "r3"] },
    "agreeableness": { "score": 80, "level": "Muy Alto", "summary": "...", "reasons": ["r1", "r2", "r3"] },
    "neuroticism": { "score": 25, "level": "Muy Estable", "summary": "...", "reasons": ["r1", "r2", "r3"] }
  }
}
`;

    const modelsToTry = preferredModel
        ? [preferredModel, ...GEMINI_CANDIDATE_MODELS.filter(m => m !== preferredModel)]
        : GEMINI_CANDIDATE_MODELS;

    let lastError = null;

    for (const modelName of modelsToTry) {
        try {
            const url = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${apiKey}`;
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    contents: [{ parts: [{ text: prompt }] }],
                    generationConfig: { responseMimeType: 'application/json' }
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                lastError = new Error(`Error Gemini API (${response.status}) con ${modelName}: ${errorText}`);
                console.warn(`[BigFive] Modelo ${modelName} no disponible (${response.status}), intentando siguiente en cascada...`);
                continue;
            }

            const jsonRes = await response.json();
            const rawText = jsonRes.candidates?.[0]?.content?.parts?.[0]?.text;
            if (!rawText) throw new Error('Respuesta vacía de Gemini');

            const parsed = JSON.parse(rawText);

            const traitsList = Object.keys(BIGFIVE_LEXICONS).map(tId => {
                const info = BIGFIVE_LEXICONS[tId];
                const tObj = parsed.rasgos?.[tId] || {};
                return {
                    trait_id: tId,
                    trait_name: info.nombre,
                    trait_en: info.en,
                    score: tObj.score || 50,
                    level: tObj.level || 'Moderado',
                    summary: tObj.summary || '',
                    reasons: Array.isArray(tObj.reasons) ? tObj.reasons : [],
                    evidence: [],
                    keywords: []
                };
            });

            return {
                es_ia: true,
                motor: `Google Gemini (${modelName})`,
                arquetipo: parsed.arquetipo || 'Perfil Multidimensional',
                sintesis_psicologica: parsed.sintesis_psicologica || '',
                estilo_comunicacion: parsed.estilo_comunicacion || '',
                fortalezas: parsed.fortalezas || [],
                areas_observacion: parsed.areas_observacion || [],
                rasgos: traitsList,
                timestamp: new Date().toLocaleString()
            };
        } catch (err) {
            lastError = err;
            console.warn(`[BigFive] Error con modelo ${modelName}:`, err.message);
        }
    }

    throw lastError || new Error('No se pudo conectar con ningún modelo de Gemini disponible');
}

/**
 * Orquestador principal: ejecuta Gemini si hay API Key disponible o recurre al fallback local
 */
async function runBigFiveAnalysis(data, apiKey) {
    if (apiKey && apiKey.trim()) {
        try {
            return await analyzeBigFiveWithGemini(data, apiKey.trim());
        } catch (err) {
            console.warn('[BigFive] Error con Gemini API, recurriendo a motor local:', err);
            const fallback = analyzeBigFiveLocalFallback(data);
            fallback.aviso_fallback = `No se pudo conectar con Gemini (${err.message}). Se usó el motor local de contingencia.`;
            return fallback;
        }
    }
    return analyzeBigFiveLocalFallback(data);
}
