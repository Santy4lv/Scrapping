/**
 * benford.js - Motor Estadístico Forense de la Ley de Benford (Detección de Bots)
 */
const BENFORD_THEORETICAL = {
    1: Math.log10(1 + 1/1),
    2: Math.log10(1 + 1/2),
    3: Math.log10(1 + 1/3),
    4: Math.log10(1 + 1/4),
    5: Math.log10(1 + 1/5),
    6: Math.log10(1 + 1/6),
    7: Math.log10(1 + 1/7),
    8: Math.log10(1 + 1/8),
    9: Math.log10(1 + 1/9)
};

const BENFORD_CDF = (() => {
    const cdf = {};
    let cum = 0;
    for (let d = 1; d <= 9; d++) {
        cum += BENFORD_THEORETICAL[d];
        cdf[d] = cum;
    }
    return cdf;
})();

function extractFirstSignificantDigit(val) {
    if (!val || val <= 0) return null;
    const str = String(Math.abs(Math.floor(val))).replace(/^0+/, '');
    if (!str) return null;
    const d = parseInt(str.charAt(0), 10);
    return (d >= 1 && d <= 9) ? d : null;
}

function chiSquareSurvival8df(chi2) {
    if (chi2 <= 0) return 1.0;
    const x = chi2 / 2.0;
    const poly = 1.0 + x + (x * x) / 2.0 + (x * x * x) / 6.0;
    const p = Math.exp(-x) * poly;
    return Math.max(0.0, Math.min(1.0, p));
}

function calculateHumanScore(chi2Val, madVal, n, zeroPct = 0) {
    const chi2Critico = 15.507;
    const madCritico = 0.015;
    const ratioChi2 = chi2Val / chi2Critico;
    const ratioMad = madVal / madCritico;

    const distancia = 0.45 * Math.min(3.0, ratioChi2) + 0.55 * Math.min(3.0, ratioMad);
    let humanPct = 100.0 / (1.0 + Math.pow(distancia / 1.5, 2.4));

    // Ajuste forense si existe alta concentración de cuentas con 0 métricas (fantasmas/inactivas)
    if (zeroPct > 15) {
        const penalizacionCero = Math.min(25, (zeroPct - 15) * 1.2);
        humanPct -= penalizacionCero;
    }

    humanPct = Math.max(3.0, Math.min(99.0, humanPct));

    let nivel = '';
    let veredicto = '';

    if (madVal <= 0.006 && ratioChi2 <= 1.0) {
        nivel = 'Conformidad Estricta (Orgánico)';
        veredicto = 'Alta Probabilidad de Red Humana / Orgánica';
    } else if (madVal <= 0.012 && ratioChi2 <= 1.3) {
        nivel = 'Conformidad Aceptable';
        veredicto = 'Probablemente Humano / Comportamiento Natural';
    } else if (madVal <= 0.018 || ratioChi2 <= 1.8) {
        nivel = 'No Conformidad Marginal';
        veredicto = 'Actividad Mixta / Red Atípica';
    } else {
        nivel = 'No Conformidad Severa (Anómalo)';
        veredicto = 'Alta Probabilidad de Comportamiento Artificial / Botnet';
    }

    if (zeroPct > 20) {
        veredicto += ` (Atención: ${zeroPct}% cuentas con 0 métricas)`;
    }

    if (n < 40) {
        veredicto += ` (Muestra preliminar N=${n})`;
    }

    return {
        humanScore: Math.round(humanPct * 10) / 10,
        nivelConformidad: nivel,
        veredicto: veredicto
    };
}

function analyzeBenfordSeries(numbers, seriesName) {
    const digits = [];
    let zeroCount = 0;
    let totalRaw = 0;

    (numbers || []).forEach(v => {
        totalRaw++;
        const num = (typeof v === 'number') ? v : parseInt(v, 10);
        if (num === 0 || isNaN(num)) {
            zeroCount++;
        }
        const d = extractFirstSignificantDigit(num);
        if (d !== null) digits.push(d);
    });

    const n = digits.length;
    if (n === 0 && zeroCount === 0) return null;

    const zeroPct = totalRaw > 0 ? Math.round((zeroCount / totalRaw) * 1000) / 10 : 0;

    if (n === 0) {
        return {
            nombre: seriesName,
            totalRaw: totalRaw,
            cuentasCero: zeroCount,
            pctCero: 100.0,
            nTotal: 0,
            conteosObservados: { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0 },
            porcentajesObservados: {},
            porcentajesEsperados: {},
            chi2: 99.9,
            pValue: 0.0,
            mad: 0.1,
            ksDistance: 1.0,
            humanScore: 5.0,
            nivelConformidad: 'No Conformidad Severa (Anómalo)',
            veredicto: '100% Cuentas con 0 métricas (Red Fantasma / Bots Inactivos)'
        };
    }

    const conteos = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0 };
    digits.forEach(d => { conteos[d]++; });

    const pctObs = {};
    const pctEsp = {};
    for (let d = 1; d <= 9; d++) {
        pctObs[d] = conteos[d] / n;
        pctEsp[d] = BENFORD_THEORETICAL[d];
    }

    let chi2Val = 0.0;
    for (let d = 1; d <= 9; d++) {
        const esperado = n * pctEsp[d];
        if (esperado > 0) {
            chi2Val += Math.pow(conteos[d] - esperado, 2) / esperado;
        }
    }

    const pVal = chiSquareSurvival8df(chi2Val);

    let madSum = 0.0;
    for (let d = 1; d <= 9; d++) {
        madSum += Math.abs(pctObs[d] - pctEsp[d]);
    }
    const madVal = madSum / 9.0;

    let cumObs = 0.0;
    let ksMax = 0.0;
    for (let d = 1; d <= 9; d++) {
        cumObs += pctObs[d];
        const diff = Math.abs(cumObs - BENFORD_CDF[d]);
        if (diff > ksMax) ksMax = diff;
    }

    const scoreInfo = calculateHumanScore(chi2Val, madVal, n, zeroPct);

    const pctObsRound = {};
    const pctEspRound = {};
    for (let d = 1; d <= 9; d++) {
        pctObsRound[d] = Math.round(pctObs[d] * 10000) / 100;
        pctEspRound[d] = Math.round(pctEsp[d] * 10000) / 100;
    }

    return {
        nombre: seriesName,
        totalRaw: totalRaw,
        cuentasCero: zeroCount,
        pctCero: zeroPct,
        nTotal: n,
        conteosObservados: conteos,
        porcentajesObservados: pctObsRound,
        porcentajesEsperados: pctEspRound,
        chi2: Math.round(chi2Val * 1000) / 1000,
        pValue: Math.round(pVal * 10000) / 10000,
        mad: Math.round(madVal * 100000) / 100000,
        ksDistance: Math.round(ksMax * 10000) / 10000,
        humanScore: scoreInfo.humanScore,
        nivelConformidad: scoreInfo.nivelConformidad,
        veredicto: scoreInfo.veredicto
    };
}

function analyzeNetworkBenford(data) {
    if (!data || typeof data !== 'object') {
        return { success: false, reason: 'Datos de perfil no disponibles' };
    }

    const followersRaw = Array.isArray(data.seguidores) ? data.seguidores : [];
    const followingRaw = Array.isArray(data.seguidos) ? data.seguidos : [];

    const extractMetricNumbers = (list, key) => {
        const nums = [];
        list.forEach(item => {
            if (typeof item === 'object' && item !== null) {
                const val = item[key];
                if (val !== undefined && val !== null && !isNaN(val)) {
                    nums.push(Number(val));
                }
            }
        });
        return nums;
    };

    const followersNums = extractMetricNumbers(followersRaw, 'seguidores');
    const followingNums = extractMetricNumbers(followingRaw, 'seguidos');

    const statFollowers = followersNums.length > 0 ? analyzeBenfordSeries(followersNums, 'Seguidores') : null;
    const statFollowing = followingNums.length > 0 ? analyzeBenfordSeries(followingNums, 'Seguidos') : null;

    const combinedNums = [...followersNums, ...followingNums];
    const statCombined = combinedNums.length > 0 ? analyzeBenfordSeries(combinedNums, 'Red Consolidada') : null;

    const availableSources = [];
    if (statFollowers) availableSources.push('followers');
    if (statFollowing) availableSources.push('following');
    if (statCombined && availableSources.length > 1) availableSources.push('both');

    if (availableSources.length === 0) {
        return {
            success: false,
            reason: 'No se encontraron cuentas con métricas numéricas para analizar la Ley de Benford.'
        };
    }

    let globalScore = 50;
    let globalVeredicto = '';
    if (statFollowers && statFollowing) {
        globalScore = Math.round((statFollowers.humanScore * 0.6 + statFollowing.humanScore * 0.4) * 10) / 10;
        globalVeredicto = statFollowers.veredicto;
    } else if (statFollowers) {
        globalScore = statFollowers.humanScore;
        globalVeredicto = statFollowers.veredicto;
    } else if (statFollowing) {
        globalScore = statFollowing.humanScore;
        globalVeredicto = statFollowing.veredicto;
    }

    return {
        success: true,
        availableSources: availableSources,
        statFollowers: statFollowers,
        statFollowing: statFollowing,
        statCombined: statCombined,
        globalScore: globalScore,
        globalVeredicto: globalVeredicto
    };
}
