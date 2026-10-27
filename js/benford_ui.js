/**
 * benford_ui.js - Renderizado visual e interactividad para la Detección de Bots (Ley de Benford)
 */

let currentBenfordAnalysis = null;
let currentBenfordSeries = null;
let benfordChartInstance = null;

function renderBenfordTab() {
    const container = document.getElementById('benford-content');
    if (!container) return;

    if (!DATA) {
        container.innerHTML = createEmptyBenfordState('Carga un archivo JSON para visualizar el análisis de Benford.');
        return;
    }

    if (typeof analyzeNetworkBenford !== 'function') {
        container.innerHTML = createEmptyBenfordState('El motor de análisis de Benford no está disponible.');
        return;
    }

    const res = analyzeNetworkBenford(DATA);
    if (!res || !res.success) {
        container.innerHTML = createEmptyBenfordState(res?.reason || 'No se encontraron datos numéricos de seguidores o seguidos para analizar.');
        return;
    }

    currentBenfordAnalysis = res;
    if (!currentBenfordSeries || !res.availableSources.includes(currentBenfordSeries)) {
        currentBenfordSeries = res.availableSources[0];
    }

    renderBenfordView();
}

function getActiveSeriesData() {
    if (!currentBenfordAnalysis) return null;
    if (currentBenfordSeries === 'followers') return currentBenfordAnalysis.statFollowers;
    if (currentBenfordSeries === 'following') return currentBenfordAnalysis.statFollowing;
    if (currentBenfordSeries === 'both') return currentBenfordAnalysis.statCombined;
    return currentBenfordAnalysis.statFollowers || currentBenfordAnalysis.statFollowing || currentBenfordAnalysis.statCombined;
}

function renderBenfordView() {
    const container = document.getElementById('benford-content');
    const seriesData = getActiveSeriesData();
    if (!container || !seriesData) return;

    const score = seriesData.humanScore;
    let badgeClass = 'badge-organic';
    if (score < 40) badgeClass = 'badge-botnet';
    else if (score < 65) badgeClass = 'badge-atypical';
    else if (score < 80) badgeClass = 'badge-acceptable';

    const sources = currentBenfordAnalysis.availableSources || [];
    let toggleHtml = '';
    if (sources.length > 1) {
        toggleHtml = `
            <div class="series-toggle-bar">
                ${sources.includes('followers') ? `<button class="series-btn ${currentBenfordSeries === 'followers' ? 'active' : ''}" onclick="switchBenfordSeries('followers')">👥 Seguidores (${currentBenfordAnalysis.statFollowers?.nTotal || 0})</button>` : ''}
                ${sources.includes('following') ? `<button class="series-btn ${currentBenfordSeries === 'following' ? 'active' : ''}" onclick="switchBenfordSeries('following')">👤 Seguidos (${currentBenfordAnalysis.statFollowing?.nTotal || 0})</button>` : ''}
                ${sources.includes('both') ? `<button class="series-btn ${currentBenfordSeries === 'both' ? 'active' : ''}" onclick="switchBenfordSeries('both')">🌐 Red Consolidada (${currentBenfordAnalysis.statCombined?.nTotal || 0})</button>` : ''}
            </div>
        `;
    }

    let rowsHtml = '';
    for (let d = 1; d <= 9; d++) {
        const obsPct = seriesData.porcentajesObservados[d] || 0;
        const espPct = seriesData.porcentajesEsperados[d] || 0;
        const diff = Math.round(Math.abs(obsPct - espPct) * 100) / 100;
        const count = seriesData.conteosObservados[d] || 0;
        rowsHtml += `
            <tr>
                <td style="font-weight: 700; color: var(--cyan);">${d}</td>
                <td>${count}</td>
                <td><strong>${obsPct.toFixed(1)}%</strong></td>
                <td style="color: var(--text-dim);">${espPct.toFixed(1)}%</td>
                <td style="color: ${diff > 5 ? '#f87171' : 'var(--text-secondary)'};">${diff > 0 ? '+' : ''}${diff.toFixed(1)}%</td>
            </tr>
        `;
    }

    container.innerHTML = `
        <!-- Veredicto Principal -->
        <div class="benford-verdict-card glass">
            <div>
                <span class="benford-verdict-badge ${badgeClass}">${escapeHtml(seriesData.nivelConformidad)}</span>
                <h2 class="benford-verdict-title" style="margin-top: 8px;">${escapeHtml(seriesData.veredicto)}</h2>
                <p style="color: var(--text-secondary); font-size: 13px; margin-top: 4px;">
                    Evaluación forense sobre la serie: <strong>${escapeHtml(seriesData.nombre)}</strong>
                </p>
            </div>
            <div class="benford-score-box">
                <div class="benford-score-num" style="color: ${score >= 75 ? '#34d399' : score >= 50 ? '#fbbf24' : '#f87171'};">
                    ${score}%
                </div>
                <div class="benford-score-label">Probabilidad Humana</div>
            </div>
        </div>

        ${toggleHtml}

        <!-- Tarjetas Estadísticas -->
        <div class="stats-grid" style="margin-bottom: 24px;">
            <div class="stat-card glass">
                <div class="stat-icon">📐</div>
                <div class="stat-value" style="font-size: 24px;">${seriesData.chi2}</div>
                <div class="stat-label">Chi-cuadrado (χ² ≤ 15.51)</div>
            </div>
            <div class="stat-card glass">
                <div class="stat-icon">🎯</div>
                <div class="stat-value" style="font-size: 24px;">${seriesData.pValue}</div>
                <div class="stat-label">p-valor (p ≥ 0.05)</div>
            </div>
            <div class="stat-card glass">
                <div class="stat-icon">📏</div>
                <div class="stat-value" style="font-size: 24px;">${seriesData.mad}</div>
                <div class="stat-label">MAD Nigrini (≤ 0.012)</div>
            </div>
            <div class="stat-card glass">
                <div class="stat-icon">📊</div>
                <div class="stat-value" style="font-size: 24px;">${seriesData.nTotal}</div>
                <div class="stat-label">Muestra Analizada (N)</div>
            </div>
        </div>

        <!-- Gráfico y Tabla -->
        <div class="charts-grid" style="grid-template-columns: 1.6fr 1.2fr; margin-bottom: 24px;">
            <div class="chart-card glass">
                <h3>📊 Distribución del Primer Dígito (Observado vs Benford)</h3>
                <div style="position: relative; height: 320px; margin-top: 16px;">
                    <canvas id="benford-chart"></canvas>
                </div>
            </div>
            <div class="chart-card glass">
                <h3>📋 Desglose por Dígito (1 al 9)</h3>
                <div style="overflow-x: auto;">
                    <table class="benford-table">
                        <thead>
                            <tr>
                                <th>Dígito</th>
                                <th>Conteo</th>
                                <th>% Obs</th>
                                <th>% Benford</th>
                                <th>Desv.</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rowsHtml}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;

    setTimeout(buildBenfordChart, 50);
}

function switchBenfordSeries(seriesKey) {
    currentBenfordSeries = seriesKey;
    renderBenfordView();
}

function buildBenfordChart() {
    const canvas = document.getElementById('benford-chart');
    if (!canvas || typeof Chart === 'undefined') return;

    const seriesData = getActiveSeriesData();
    if (!seriesData) return;

    if (benfordChartInstance) {
        benfordChartInstance.destroy();
        benfordChartInstance = null;
    }

    const digits = [1, 2, 3, 4, 5, 6, 7, 8, 9];
    const obsValues = digits.map(d => seriesData.porcentajesObservados[d] || 0);
    const espValues = digits.map(d => seriesData.porcentajesEsperados[d] || 0);

    const ctx = canvas.getContext('2d');
    benfordChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: digits.map(d => `Dígito ${d}`),
            datasets: [
                {
                    label: 'Observado (%)',
                    data: obsValues,
                    backgroundColor: 'rgba(6, 182, 212, 0.75)',
                    borderColor: '#06b6d4',
                    borderWidth: 1.5,
                    borderRadius: 6
                },
                {
                    label: 'Ley de Benford (%)',
                    data: espValues,
                    backgroundColor: 'rgba(245, 158, 11, 0.4)',
                    borderColor: '#f59e0b',
                    borderWidth: 1.5,
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#94a3b8', font: { family: 'Inter', size: 12 } }
                },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%`
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8' }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        color: '#94a3b8',
                        callback: val => `${val}%`
                    }
                }
            }
        }
    });
}

function onBenfordTabShown() {
    if (benfordChartInstance) {
        benfordChartInstance.resize();
    } else {
        renderBenfordTab();
    }
}

function createEmptyBenfordState(message) {
    return `
        <div class="empty-state glass" style="padding: 48px 24px; text-align: center;">
            <div style="font-size: 40px; margin-bottom: 12px;">🤖</div>
            <h3 style="color: var(--text-primary); margin-bottom: 8px;">Detección de Bots no disponible</h3>
            <p style="color: var(--text-secondary); max-width: 480px; margin: 0 auto; font-size: 14px;">
                ${escapeHtml(message)}
            </p>
        </div>
    `;
}
