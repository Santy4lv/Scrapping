/**
 * storage.js - Persistencia en localStorage para IG Analyzer
 */
const STORAGE_KEY_DATA = 'ig_analyzer_data';
const STORAGE_KEY_ACTIVE_TAB = 'ig_analyzer_active_tab';
const STORAGE_KEY_BIGFIVE = 'ig_analyzer_bigfive';
const STORAGE_KEY_GEMINI_KEY = 'ig_analyzer_gemini_key';

function saveDashboardState() {
    if (!DATA) return;
    try {
        localStorage.setItem(STORAGE_KEY_DATA, JSON.stringify(DATA));
        if (DATA.gemini_api_key) {
            saveGeminiApiKey(DATA.gemini_api_key);
        }
    } catch (err) {
        console.warn('No se pudo guardar en localStorage (límite de cuota alcanzado):', err);
    }
}

function saveBigFiveAnalysis(result) {
    if (!result) return;
    try {
        localStorage.setItem(STORAGE_KEY_BIGFIVE, JSON.stringify(result));
    } catch (err) {
        console.warn('No se pudo guardar Big Five en localStorage:', err);
    }
}

function getStoredBigFiveAnalysis() {
    try {
        const stored = localStorage.getItem(STORAGE_KEY_BIGFIVE);
        return stored ? JSON.parse(stored) : null;
    } catch (e) {
        return null;
    }
}

function saveGeminiApiKey(key) {
    try {
        if (key) localStorage.setItem(STORAGE_KEY_GEMINI_KEY, key);
        else localStorage.removeItem(STORAGE_KEY_GEMINI_KEY);
    } catch (e) {}
}

function getStoredGeminiApiKey() {
    try {
        return localStorage.getItem(STORAGE_KEY_GEMINI_KEY) || '';
    } catch (e) {
        return '';
    }
}

function clearDashboardState() {
    DATA = null;
    try {
        localStorage.removeItem(STORAGE_KEY_DATA);
        localStorage.removeItem(STORAGE_KEY_ACTIVE_TAB);
        localStorage.removeItem(STORAGE_KEY_BIGFIVE);
    } catch (e) {}
}

function restoreDashboardState() {
    try {
        const cached = localStorage.getItem(STORAGE_KEY_DATA);
        if (cached) {
            DATA = JSON.parse(cached);
            if (DATA && typeof DATA === 'object' && (DATA.perfil || DATA.publicaciones)) {
                if (typeof showDashboard === 'function') {
                    showDashboard();
                }
                const savedTab = localStorage.getItem(STORAGE_KEY_ACTIVE_TAB);
                if (savedTab && typeof switchTab === 'function') {
                    switchTab(savedTab);
                }
                return true;
            }
        }
    } catch (err) {
        console.warn('Error al restaurar sesión previa:', err);
        clearDashboardState();
    }
    return false;
}
