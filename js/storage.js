/**
 * storage.js - Persistencia en localStorage para IG Analyzer
 */
const STORAGE_KEY_DATA = 'ig_analyzer_data';
const STORAGE_KEY_ACTIVE_TAB = 'ig_analyzer_active_tab';

function saveDashboardState() {
    if (!DATA) return;
    try {
        localStorage.setItem(STORAGE_KEY_DATA, JSON.stringify(DATA));
    } catch (err) {
        console.warn('No se pudo guardar en localStorage (límite de cuota alcanzado):', err);
    }
}

function clearDashboardState() {
    DATA = null;
    try {
        localStorage.removeItem(STORAGE_KEY_DATA);
        localStorage.removeItem(STORAGE_KEY_ACTIVE_TAB);
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
