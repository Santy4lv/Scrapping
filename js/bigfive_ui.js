/**
 * bigfive_ui.js - Renderizado visual e interactividad para la pestaña Big Five (OCEAN)
 */

let bigFiveRadarChart = null;

function renderBigFiveTab() {
    const container = document.getElementById('bigfive-content');
    if (!container) return;
    if (!DATA) {
        container.innerHTML = createEmptyBigFiveState('Carga un archivo JSON para analizar la personalidad.');
        return;
    }
    const cached = typeof getStoredBigFiveAnalysis === 'function' ? getStoredBigFiveAnalysis() : null;
    if (cached) renderBigFiveAnalysisView(cached);
    else renderBigFivePromptView();
}

function renderBigFivePromptView() {
    const container = document.getElementById('bigfive-content');
    if (!container) return;
    const detectedKey = (typeof DATA === 'object' && DATA && DATA.gemini_api_key)
        ? DATA.gemini_api_key
        : (typeof getStoredGeminiApiKey === 'function' ? getStoredGeminiApiKey() : '');

    let keySectionHtml = '';
    let btnText = '⚡ Analizar Personalidad con Gemini AI';

    if (detectedKey) {
        keySectionHtml = `
            <div style="text-align: left; background: rgba(6, 182, 212, 0.08); border: 1px solid rgba(6, 182, 212, 0.3); border-radius: 12px; padding: 16px; margin-bottom: 24px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 22px;">✨</span>
                        <div>
                            <div style="font-size: 13px; font-weight: 700; color: #67e8f9;">Gemini API Key Detectada desde .env</div>
                            <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">El análisis de personalidad se ejecutará con Google Gemini AI.</div>
                        </div>
                    </div>
                    <span class="badge-gemini" style="font-size: 10px;">IA Lista</span>
                </div>
                <input type="hidden" id="gemini-key-input" value="${escapeHtml(detectedKey)}">
            </div>
        `;
    } else {
        btnText = '⚡ Iniciar Análisis de Personalidad';
        keySectionHtml = `
            <div style="text-align: left; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 24px;">
                <label style="display: block; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-secondary); margin-bottom: 8px;">
                    🔑 Gemini API Key (Opcional)
                </label>
                <input type="password" id="gemini-key-input" class="search-bar" style="width: 100%; border-radius: 8px; font-size: 13px;" placeholder="AIzaSy... (opcional)">
                <p style="font-size: 11px; color: var(--text-dim); margin-top: 6px;">
                    💡 Si no configuras una API Key en <code>.env</code> ni aquí, se ejecutará el <strong>motor léxico local de contingencia</strong> (100% privado y offline).
                </p>
            </div>
        `;
    }

    container.innerHTML = `
        <div class="empty-state glass" style="padding: 48px 32px; text-align: center; max-width: 640px; margin: 0 auto;">
            <div style="font-size: 48px; margin-bottom: 12px;">🧠</div>
            <h2 style="font-size: 22px; font-weight: 800; margin-bottom: 8px;">Análisis de Personalidad (Big Five OCEAN)</h2>
            <p style="color: var(--text-secondary); font-size: 14px; line-height: 1.6; margin-bottom: 24px;">
                Evalúa los 5 factores de la personalidad (Apertura, Responsabilidad, Extraversión, Amabilidad y Estabilidad) a partir del lenguaje en publicaciones, biografía e interacciones.
            </p>
            ${keySectionHtml}
            <button class="upload-btn" id="btn-run-bigfive" onclick="executeBigFiveAnalysis()" style="display: inline-flex; align-items: center; justify-content: center; gap: 8px; cursor: pointer; border: none;">
                ${btnText}
            </button>
        </div>
    `;
}

async function executeBigFiveAnalysis() {
    const keyInput = document.getElementById('gemini-key-input');
    const apiKey = keyInput ? keyInput.value.trim() : '';
    const container = document.getElementById('bigfive-content');
    if (container) {
        container.innerHTML = `
            <div class="empty-state glass" style="padding: 60px 32px; text-align: center; max-width: 500px; margin: 40px auto;">
                <div style="font-size: 44px; margin-bottom: 16px; animation: spin 1.5s linear infinite; display: inline-block;">⚙️</div>
                <h3 style="font-size: 20px; font-weight: 700; margin-bottom: 8px;">Procesando Análisis Psicométrico</h3>
                <p style="color: var(--text-secondary); font-size: 14px;">
                    ${apiKey ? 'Consultando a Google Gemini AI y evaluando patrones conductuales...' : 'Analizando densidad léxica y vocabulario con el motor local...'}
                </p>
            </div>
        `;
    }

    try {
        const result = await runBigFiveAnalysis(DATA, apiKey);
        if (typeof saveBigFiveAnalysis === 'function') saveBigFiveAnalysis(result);
        if (apiKey && typeof saveGeminiApiKey === 'function') saveGeminiApiKey(apiKey);
        renderBigFiveAnalysisView(result);
    } catch (err) {
        alert('Error durante el análisis: ' + err.message);
        renderBigFivePromptView();
    }
}

function renderBigFiveAnalysisView(res) {
    const container = document.getElementById('bigfive-content');
    if (!container || !res) return;

    const engineBadge = res.es_ia
        ? `<span class="badge-gemini">✨ ${escapeHtml(res.motor)}</span>`
        : `<span class="badge-fallback">⚡ ${escapeHtml(res.motor)}</span>`;

    const noticeHtml = res.aviso_fallback
        ? `<div class="alert-box" style="margin-bottom: 16px;">⚠️ ${escapeHtml(res.aviso_fallback)}</div>`
        : '';

    let traitsHtml = '';
    (res.rasgos || []).forEach(t => {
        const score = Math.round(t.score);
        let barColor = t.trait_id === 'neuroticism'
            ? (score > 50 ? 'linear-gradient(135deg, #f59e0b, #ef4444)' : 'linear-gradient(135deg, #10b981, #06b6d4)')
            : 'var(--gradient-primary)';
        const reasonsList = (t.reasons || []).map(r => `<li>${escapeHtml(r)}</li>`).join('');

        traitsHtml += `
            <div class="trait-card glass">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                    <div>
                        <h4 style="font-size: 15px; font-weight: 700; color: var(--text-primary);">${escapeHtml(t.trait_name)}</h4>
                        <span style="font-size: 11px; text-transform: uppercase; color: var(--text-dim);">${escapeHtml(t.trait_en)}</span>
                    </div>
                    <div style="text-align: right;">
                        <span style="font-size: 18px; font-weight: 800; color: var(--cyan);">${score}%</span>
                        <div style="font-size: 11px; font-weight: 600; color: var(--text-secondary);">${escapeHtml(t.level)}</div>
                    </div>
                </div>
                <div class="trait-progress-track">
                    <div class="trait-progress-fill" style="width: ${score}%; background: ${barColor};"></div>
                </div>
                <p style="font-size: 12px; color: var(--text-secondary); margin: 10px 0 8px 0; line-height: 1.4;">
                    ${escapeHtml(t.summary)}
                </p>
                ${reasonsList ? `<ul class="trait-reasons-list">${reasonsList}</ul>` : ''}
            </div>
        `;
    });

    const strengthsList = (res.fortalezas || []).map(f => `<li>✅ ${escapeHtml(f)}</li>`).join('');
    const observationsList = (res.areas_observacion || []).map(o => `<li>🔍 ${escapeHtml(o)}</li>`).join('');

    container.innerHTML = `
        ${noticeHtml}
        <div class="benford-verdict-card glass" style="flex-wrap: wrap;">
            <div style="flex: 1; min-width: 260px;">
                ${engineBadge}
                <h2 style="font-size: 24px; font-weight: 800; margin: 10px 0 6px 0;">${escapeHtml(res.arquetipo)}</h2>
                <p style="font-size: 13px; color: var(--text-secondary); line-height: 1.5;">${escapeHtml(res.sintesis_psicologica)}</p>
                <div style="margin-top: 10px; font-size: 12px; color: var(--text-dim);">
                    🗣️ <strong>Estilo de comunicación:</strong> ${escapeHtml(res.estilo_comunicacion || 'No especificado')}
                </div>
            </div>
            <div style="text-align: right; min-width: 140px;">
                <button class="btn-ghost" onclick="renderBigFivePromptView()" style="border: 1px solid var(--border); border-radius: 8px; padding: 8px 14px; font-size: 12px; cursor: pointer;">
                    🔄 Reanalizar
                </button>
                <div style="font-size: 11px; color: var(--text-dim); margin-top: 8px;">Analizado: ${escapeHtml(res.timestamp || '')}</div>
            </div>
        </div>

        <div class="charts-grid" style="grid-template-columns: 1.2fr 1fr; margin-bottom: 24px;">
            <div class="chart-card glass">
                <h3>🕸️ Perfil Psicométrico Radar (OCEAN)</h3>
                <div style="position: relative; height: 320px; margin-top: 12px;">
                    <canvas id="bigfive-radar-chart"></canvas>
                </div>
            </div>
            <div class="chart-card glass" style="display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <h3>🌟 Fortalezas Conductuales</h3>
                    <ul class="trait-reasons-list" style="margin: 12px 0 20px 0; font-size: 13px; line-height: 1.8;">
                        ${strengthsList || '<li>No registradas</li>'}
                    </ul>
                </div>
                <div>
                    <h3>🎯 Áreas de Observación</h3>
                    <ul class="trait-reasons-list" style="margin: 12px 0 0 0; font-size: 13px; line-height: 1.8;">
                        ${observationsList || '<li>No registradas</li>'}
                    </ul>
                </div>
            </div>
        </div>

        <div style="margin-bottom: 16px;">
            <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 12px;">Desglose Dimensional de los Cinco Grandes Factores</h3>
            <div class="traits-grid">
                ${traitsHtml}
            </div>
        </div>
    `;

    setTimeout(() => buildBigFiveRadarChart(res), 50);
}

function buildBigFiveRadarChart(res) {
    const canvas = document.getElementById('bigfive-radar-chart');
    if (!canvas || typeof Chart === 'undefined' || !res) return;
    if (bigFiveRadarChart) {
        bigFiveRadarChart.destroy();
        bigFiveRadarChart = null;
    }

    const labels = [];
    const values = [];
    (res.rasgos || []).forEach(t => {
        if (t.trait_id === 'neuroticism') {
            labels.push('Estabilidad');
            values.push(Math.max(10, 100 - t.score));
        } else {
            labels.push(t.trait_name.split(' ')[0]);
            values.push(t.score);
        }
    });

    const ctx = canvas.getContext('2d');
    bigFiveRadarChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Intensidad de Rasgo (%)',
                data: values,
                backgroundColor: 'rgba(139, 92, 246, 0.25)',
                borderColor: '#8b5cf6',
                borderWidth: 2,
                pointBackgroundColor: '#06b6d4',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: '#06b6d4'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.raw}%` } }
            },
            scales: {
                r: {
                    angleLines: { color: 'rgba(255, 255, 255, 0.08)' },
                    grid: { color: 'rgba(255, 255, 255, 0.08)' },
                    pointLabels: { color: '#f1f5f9', font: { family: 'Inter', size: 12, weight: '600' } },
                    ticks: { backdropColor: 'transparent', color: '#94a3b8', stepSize: 20 },
                    suggestedMin: 0,
                    suggestedMax: 100
                }
            }
        }
    });
}

function onBigFiveTabShown() {
    if (bigFiveRadarChart) bigFiveRadarChart.resize();
    else renderBigFiveTab();
}

function createEmptyBigFiveState(message) {
    return `
        <div class="empty-state glass" style="padding: 48px 24px; text-align: center;">
            <div style="font-size: 40px; margin-bottom: 12px;">🧠</div>
            <h3 style="color: var(--text-primary); margin-bottom: 8px;">Análisis de Personalidad no iniciado</h3>
            <p style="color: var(--text-secondary); max-width: 480px; margin: 0 auto; font-size: 14px;">
                ${escapeHtml(message)}
            </p>
        </div>
    `;
}
