/**
 * app.js - Lógica de presentación e interacción para IG Analyzer
 */

/* ════════════════════════════════════════════════════
   STATE
   ════════════════════════════════════════════════════ */
let DATA = null;

/* ════════════════════════════════════════════════════
   FILE LOADING & DRAG-AND-DROP
   ════════════════════════════════════════════════════ */
const fileInput = document.getElementById('file-input');
const dropZone = document.getElementById('drop-zone');

if (fileInput) {
    fileInput.addEventListener('change', e => {
        if (e.target.files[0]) loadFile(e.target.files[0]);
    });
}

if (dropZone) {
    dropZone.addEventListener('click', () => fileInput && fileInput.click());
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', e => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files[0]) loadFile(e.dataTransfer.files[0]);
    });
}

const btnReload = document.getElementById('btn-reload');
if (btnReload) {
    btnReload.addEventListener('click', () => {
        if (typeof clearDashboardState === 'function') {
            clearDashboardState();
        }
        document.getElementById('upload-screen').classList.remove('hidden');
        document.getElementById('dashboard-screen').classList.add('hidden');
        if (fileInput) fileInput.value = '';
    });
}

function loadFile(file) {
    const reader = new FileReader();
    reader.onload = e => {
        try {
            DATA = JSON.parse(e.target.result);
            if (typeof saveDashboardState === 'function') {
                saveDashboardState();
            }
            showDashboard();
        } catch (err) {
            alert('Error al leer el archivo JSON: ' + err.message);
        }
    };
    reader.readAsText(file);
}

/* ════════════════════════════════════════════════════
   DASHBOARD RENDERING
   ════════════════════════════════════════════════════ */
function showDashboard() {
    document.getElementById('upload-screen').classList.add('hidden');
    document.getElementById('dashboard-screen').classList.remove('hidden');

    renderProfile();
    renderStats();
    renderOverviewCharts();
    renderPosts();
    renderUsers('followers');
    renderUsers('following');
    setupSearch();
    setupTabs();
}

/* ── Profile ── */
function renderProfile() {
    const name = DATA.perfil || 'unknown';
    document.getElementById('profile-name').textContent = name;
    document.getElementById('profile-bio').textContent = DATA.biografia || '';
    document.getElementById('nav-username').textContent = '@' + name;

    const avatarEl = document.getElementById('profile-avatar');
    const avatarSrc = DATA.foto_perfil_local || DATA.foto_perfil_url;
    if (avatarSrc) {
        avatarEl.innerHTML = `<img src="${escapeHtml(avatarSrc)}" alt="${escapeHtml(name)}" onerror="this.remove(); document.getElementById('profile-avatar').textContent='${name.charAt(0).toUpperCase()}';">`;
    } else {
        avatarEl.textContent = name.charAt(0).toUpperCase();
    }
}

/* ── Stats with counter animation ── */
function renderStats() {
    const totalComments = (DATA.publicaciones || []).reduce((sum, p) => sum + (p.total_comentarios || 0), 0);
    animateCounter('stat-posts', DATA.publicaciones_count || (DATA.publicaciones || []).length);
    animateCounter('stat-followers', DATA.total_seguidores || 0);
    animateCounter('stat-following', DATA.total_seguidos || 0);
    animateCounter('stat-comments', totalComments);
}

function animateCounter(id, target) {
    const el = document.getElementById(id);
    if (!el) return;
    if (!target) { el.textContent = '0'; return; }
    let current = 0;
    const duration = 1200;
    const steps = 40;
    const increment = target / steps;
    const interval = duration / steps;
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) { current = target; clearInterval(timer); }
        el.textContent = formatNumber(Math.round(current));
    }, interval);
}

function formatNumber(n) {
    return Number(n || 0).toLocaleString('es-EC');
}

/* ── Overview Charts ── */
function renderOverviewCharts() {
    const posts = DATA.publicaciones || [];

    // Engagement chart (likes per post)
    const engContainer = document.getElementById('chart-engagement');
    if (engContainer) {
        engContainer.innerHTML = '';
        if (posts.length === 0) {
            engContainer.innerHTML = '<div style="color:var(--text-dim);font-size:13px;">Sin datos de publicaciones</div>';
        } else {
            const maxLikes = Math.max(...posts.map(p => p.likes || 0), 1);
            posts.forEach((post, i) => {
                const pct = ((post.likes || 0) / maxLikes) * 100;
                const bar = document.createElement('div');
                bar.className = 'v-bar';
                bar.style.height = Math.max(pct, 2) + '%';
                bar.style.animationDelay = (i * 0.02) + 's';
                const dateStr = post.fecha ? new Date(post.fecha).toLocaleDateString('es-EC', { day: 'numeric', month: 'short' }) : '#' + (i + 1);
                bar.innerHTML = `<div class="v-bar-tip">❤️ ${formatNumber(post.likes || 0)}<br>${dateStr}</div>`;
                engContainer.appendChild(bar);
            });
        }
    }

    // Top hashtags
    renderHBarChart('chart-hashtags', getFrequency(posts.flatMap(p => p.hashtags || [])), 'purple');

    // Top commenters
    const allCommenters = posts.flatMap(p => (p.comentarios || []).map(c => c.usuario));
    renderHBarChart('chart-commenters', getFrequency(allCommenters), 'cyan');

    // Top mentions
    renderHBarChart('chart-mentions', getFrequency(posts.flatMap(p => p.menciones || [])), 'pink');
}

function getFrequency(arr) {
    const freq = {};
    arr.forEach(item => { freq[item] = (freq[item] || 0) + 1; });
    return Object.entries(freq)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10);
}

function renderHBarChart(containerId, data, colorClass) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    if (data.length === 0) {
        container.innerHTML = '<div style="color:var(--text-dim);font-size:13px;">Sin datos disponibles</div>';
        return;
    }
    const maxVal = data[0][1];
    data.forEach(([label, value]) => {
        const pct = (value / maxVal) * 100;
        const row = document.createElement('div');
        row.className = 'h-bar-row';
        row.innerHTML = `
            <span class="h-bar-label" title="${escapeHtml(label)}">${escapeHtml(label)}</span>
            <div class="h-bar-track"><div class="h-bar-fill ${colorClass}" style="width:${pct}%"></div></div>
            <span class="h-bar-value">${value}</span>
        `;
        container.appendChild(row);
    });
}

/* ── Posts ── */
function renderPosts(filter = '') {
    const grid = document.getElementById('posts-grid');
    if (!grid) return;
    grid.innerHTML = '';
    const posts = DATA.publicaciones || [];
    const filtered = posts.filter(p =>
        !filter || (p.caption || '').toLowerCase().includes(filter)
        || (p.hashtags || []).join(' ').toLowerCase().includes(filter)
        || (p.comentarios || []).some(c => (c.texto || '').toLowerCase().includes(filter) || (c.usuario || '').toLowerCase().includes(filter))
    );

    const countPosts = document.getElementById('count-posts');
    if (countPosts) {
        countPosts.textContent = `${filtered.length} de ${posts.length}`;
    }

    filtered.forEach((post, idx) => {
        const card = document.createElement('div');
        card.className = 'post-card glass';
        card.style.animationDelay = (idx * 0.03) + 's';
        card.addEventListener('click', () => card.classList.toggle('expanded'));

        const dateStr = post.fecha
            ? new Date(post.fecha).toLocaleDateString('es-EC', { day: 'numeric', month: 'short', year: 'numeric' })
            : '';

        const captionHtml = post.caption
            ? `<div class="post-caption">${escapeHtml(post.caption)}</div>`
            : `<div class="post-caption post-caption-empty">Sin descripción</div>`;

        const tagsHtml = [
            ...(post.hashtags || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`),
            ...(post.menciones || []).map(m => `<span class="tag mention">${escapeHtml(m)}</span>`),
        ].join('');

        const commentsHtml = (post.comentarios || []).length > 0
            ? (post.comentarios || []).map(c => {
                const u = (c && c.usuario) ? String(c.usuario) : 'Anónimo';
                const initial = u ? u.charAt(0).toUpperCase() : '?';
                return `
                <div class="comment">
                    <div class="comment-avatar">${initial}</div>
                    <div class="comment-body">
                        <div class="comment-user">${escapeHtml(u)}</div>
                        <div class="comment-text">${escapeHtml(c.texto || '')}</div>
                    </div>
                </div>`;
            }).join('')
            : '<div class="no-comments">Sin comentarios extraídos</div>';

        // Media HTML
        let mediaHtml = '';
        if (post.imagen_url) {
            const badgeText = (post.tipo_media === 'carousel' && post.imagenes && post.imagenes.length > 1)
                ? `📸 Carrusel (${post.imagenes.length})`
                : (post.tipo_media === 'video' ? '▶ Video / Reel' : '');
            const badgeHtml = badgeText ? `<span class="post-media-badge">${badgeText}</span>` : '';

            mediaHtml = `
                <div class="post-media-wrap">
                    <img src="${escapeHtml(post.imagen_url)}" 
                         alt="${escapeHtml(post.alt_texto || post.caption || 'Publicación')}" 
                         class="post-media-img" 
                         loading="lazy" 
                         onerror="this.closest('.post-media-wrap').style.display='none';">
                    ${badgeHtml}
                </div>
            `;
        }

        const altHtml = post.alt_texto
            ? `<div class="post-alt-tag" title="${escapeHtml(post.alt_texto)}">📸 ${escapeHtml(post.alt_texto)}</div>`
            : '';

        let carouselThumbsHtml = '';
        if (post.tipo_media === 'carousel' && post.imagenes && post.imagenes.length > 1) {
            carouselThumbsHtml = `
                <div class="carousel-preview" title="Fotos del carrusel">
                    ${post.imagenes.map((imgUrl, i) => `
                        <img src="${escapeHtml(imgUrl)}" 
                             alt="Foto ${i + 1}" 
                             class="carousel-thumb" 
                             loading="lazy" 
                             onerror="this.style.display='none';">
                    `).join('')}
                </div>
            `;
        }

        const linkHtml = post.url
            ? `<a href="${post.url}" target="_blank" rel="noopener" class="post-link-btn" title="Abrir en Instagram" onclick="event.stopPropagation()">Instagram ↗</a>`
            : '';

        card.innerHTML = `
            <div class="post-header">
                <span class="post-index">#${posts.indexOf(post) + 1}</span>
                <div class="post-header-right">
                    ${linkHtml}
                    <span class="post-date">${dateStr}</span>
                </div>
            </div>
            ${mediaHtml}
            ${carouselThumbsHtml}
            ${captionHtml}
            ${altHtml}
            ${tagsHtml ? `<div class="post-tags">${tagsHtml}</div>` : ''}
            <div class="post-meta">
                <span>❤️ ${formatNumber(post.likes || 0)}</span>
                <span>💬 ${post.total_comentarios || 0}</span>
                ${post.hashtags?.length ? `<span>#️⃣ ${post.hashtags.length}</span>` : ''}
            </div>
            ${(post.comentarios || []).length > 0 || post.caption ? '<div class="post-expand-hint">▸ Click para expandir</div>' : ''}
            <div class="comments-section">
                <div class="comments-title">Comentarios (${(post.comentarios || []).length})</div>
                ${commentsHtml}
            </div>
        `;
        grid.appendChild(card);
    });
}

/* ── Users (followers / following) ── */
function renderUsers(type, filter = '') {
    const list = type === 'followers' ? (DATA.seguidores || []) : (DATA.seguidos || []);
    const grid = document.getElementById(type === 'followers' ? 'followers-grid' : 'following-grid');
    if (!grid) return;
    grid.innerHTML = '';

    const getUsername = item => (typeof item === 'object' && item !== null) ? (item.usuario || '') : String(item || '');
    const filtered = list.filter(u => !filter || getUsername(u).toLowerCase().includes(filter));
    const countId = type === 'followers' ? 'count-followers' : 'count-following';
    const countEl = document.getElementById(countId);
    if (countEl) {
        countEl.textContent = `${filtered.length} de ${list.length}`;
    }

    filtered.forEach((item, i) => {
        const username = getUsername(item);
        const initial = username ? username.charAt(0).toUpperCase() : '?';
        const chip = document.createElement('div');
        chip.className = 'user-chip glass';
        chip.style.animationDelay = Math.min(i * 0.01, 0.5) + 's';

        let metricasBadge = '';
        if (typeof item === 'object' && item !== null && (item.seguidores !== undefined || item.seguidos !== undefined)) {
            metricasBadge = `<div class="user-metrics-mini" style="font-size:11px;color:var(--text-dim);margin-top:2px;">
                👥 ${Number(item.seguidores || 0).toLocaleString()} seg. | 🫂 ${Number(item.seguidos || 0).toLocaleString()} seguidos
            </div>`;
        }

        chip.innerHTML = `
            <div class="user-avatar-mini">${initial}</div>
            <div style="display:flex;flex-direction:column;">
                <a href="https://www.instagram.com/${escapeHtml(username)}/" target="_blank" rel="noopener">@${escapeHtml(username)}</a>
                ${metricasBadge}
            </div>
        `;
        grid.appendChild(chip);
    });
}

/* ════════════════════════════════════════════════════
   INTERACTIONS & TABS
   ════════════════════════════════════════════════════ */
function switchTab(tabName) {
    const tabBtn = document.querySelector(`.tab[data-tab="${tabName}"]`);
    const panel = document.getElementById('panel-' + tabName);
    if (!tabBtn || !panel) return;

    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    tabBtn.classList.add('active');
    panel.classList.add('active');
    try {
        localStorage.setItem(STORAGE_KEY_ACTIVE_TAB, tabName);
    } catch (e) {}
}

function setupTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            switchTab(tab.dataset.tab);
        });
    });
}

function setupSearch() {
    const searchPosts = document.getElementById('search-posts');
    if (searchPosts) {
        searchPosts.addEventListener('input', e => {
            renderPosts(e.target.value.toLowerCase());
        });
    }
    const searchFollowers = document.getElementById('search-followers');
    if (searchFollowers) {
        searchFollowers.addEventListener('input', e => {
            renderUsers('followers', e.target.value.toLowerCase());
        });
    }
    const searchFollowing = document.getElementById('search-following');
    if (searchFollowing) {
        searchFollowing.addEventListener('input', e => {
            renderUsers('following', e.target.value.toLowerCase());
        });
    }
}

/* ════════════════════════════════════════════════════
   UTILITIES & AUTO-INIT
   ════════════════════════════════════════════════════ */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Inicializar sesión persistente si existe
if (typeof restoreDashboardState === 'function') {
    restoreDashboardState();
}
