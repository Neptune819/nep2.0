// ========================================
// detail.js - 番剧详情弹窗
// 点击番剧卡片 → 显示完整详情，而非跳转推荐
// 支持：加入待看、收藏
// ========================================

// 延迟获取元素，确保DOM已加载
let detailOverlay = null;
let currentDetailId = null;
let currentDetailData = null; // 缓存当前弹窗数据

// ===== 待看 / 收藏 localStorage =====
const WATCHLIST_KEY = 'anime_watchlist';
const FAVORITES_KEY = 'anime_history'; // 收藏列表 = 现有番剧列表

function loadListFromStorage(key) {
    try {
        const raw = localStorage.getItem(key);
        return raw ? JSON.parse(raw) : [];
    } catch (e) { return []; }
}

function saveListToStorage(key, list) {
    try { localStorage.setItem(key, JSON.stringify(list)); } catch (e) {}
}

function isInList(key, id) {
    return loadListFromStorage(key).some(a => a.id === id);
}

function addToList(key, anime) {
    const list = loadListFromStorage(key);
    if (list.some(a => a.id === anime.id)) return false;
    list.push({
        id: anime.id,
        name: anime.name_cn || anime.name_original || anime.name || '',
        name_cn: anime.name_cn || '',
        name_en: anime.name_original || anime.name || '',
        image: anime.image || '',
        rating: anime.rating || 0,
        year: anime.year || null,
        format: anime.format || null,
        tags_cn: (anime.tags || []).map(t => t.cn || t.en).slice(0, 5),
        tags: (anime.tags || []).map(t => t.cn || t.en).slice(0, 5),
    });
    saveListToStorage(key, list);
    return true;
}

function removeFromList(key, id) {
    let list = loadListFromStorage(key);
    list = list.filter(a => a.id !== id);
    saveListToStorage(key, list);
}

// 初始化函数
function initDetail() {
    detailOverlay = document.getElementById('anime-detail-overlay');
    if (detailOverlay) {
        // 关闭按钮
        const closeBtn = detailOverlay.querySelector('.detail-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', closeDetail);
        }
        // 点击遮罩关闭
        detailOverlay.addEventListener('click', (e) => {
            if (e.target === detailOverlay) closeDetail();
        });
    }
}

// DOM加载完成后初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDetail);
} else {
    initDetail();
}

// ESC 关闭
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && detailOverlay?.classList.contains('show')) {
        closeDetail();
    }
});

// ===== 打开详情弹窗 =====
async function openAnimeDetail(animeId) {
    if (!detailOverlay) return;
    currentDetailId = animeId;
    detailOverlay.classList.add('show');
    document.body.style.overflow = 'hidden';

    // 显示加载状态
    const scroll = detailOverlay.querySelector('.detail-scroll');
    scroll.innerHTML = '<div class="detail-loading">加载中...</div>';

    try {
        const r = await fetch(`/api/anime/${animeId}`);
        if (!r.ok) throw new Error('not found');
        const data = await r.json();
        currentDetailData = data;
        renderDetail(data);
    } catch (e) {
        scroll.innerHTML = '<div class="detail-loading" style="color:#f87171">加载失败，请重试</div>';
    }
}

// ===== 渲染详情内容 =====
function renderDetail(data) {
    const a = data.anime;
    const scroll = detailOverlay.querySelector('.detail-scroll');

    // ---- 封面 & 标题 ----
    const coverImg = a.image || '';
    const title = a.name_cn || a.name_original || '(无标题)';
    const original = a.name_original || a.name_jp || '';

    // ---- 统计标签 ----
    const statsHtml = [];
    if (a.rating > 0) {
        statsHtml.push(`<span class="detail-stat rating-stat">⭐ ${a.rating.toFixed(1)}</span>`);
    }
    if (a.favourites > 0) {
        statsHtml.push(`<span class="detail-stat pop-stat">❤️ ${a.favourites.toLocaleString()}</span>`);
    }
    if (a.popularity > 0) {
        statsHtml.push(`<span class="detail-stat pop-stat">👁 #${a.popularity.toLocaleString()}</span>`);
    }
    if (a.year) {
        statsHtml.push(`<span class="detail-stat year-stat">📅 ${a.year}</span>`);
    }
    if (a.format) {
        statsHtml.push(`<span class="detail-stat year-stat">${a.format}</span>`);
    }
    if (a.eps > 0) {
        statsHtml.push(`<span class="detail-stat year-stat">${a.eps} 话</span>`);
    }
    if (a.status) {
        const statusMap = { 'FINISHED': '已完结', 'RELEASING': '放送中', 'NOT_YET_RELEASED': '未开播', 'CANCELLED': '已取消', 'HIATUS': '停更中' };
        const statusCN = statusMap[a.status] || a.status;
        const isUnreleased = a.status === 'NOT_YET_RELEASED';
        const isReleasing = a.status === 'RELEASING';
        const statusBadgeClass = isUnreleased ? 'unreleased' : (isReleasing ? 'releasing' : '');
        statsHtml.push(`<span class="detail-stat status-stat ${statusBadgeClass}">${statusCN}</span>`);
        if (isUnreleased) {
            statsHtml.push(`<span class="detail-stat unreleased-warn">⏳ 尚未开播，数据可能存在变动</span>`);
        }
    }

    // ---- Tags ----
    const tagsHtml = (a.tags || []).map(t =>
        `<span class="detail-tag">${escapeHtml(t.cn !== t.en ? t.cn : t.en)}</span>`
    ).join('');

    // ---- 简介（已由服务端翻译为中文） ----
    const rawSummary = (a.summary || '').trim();
    const summary = rawSummary
        ? rawSummary.replace(/<br\s*\/?>/gi, '\n').slice(0, 1500)
        : '暂无简介';

    // ---- 制作信息 ----
    const infoRows = [];
    if (a.studios && a.studios.length) {
        infoRows.push(`<div class="detail-info-row"><strong>制作</strong><span>${escapeHtml(a.studios.join(' / '))}</span></div>`);
    }
    if (a.season) {
        infoRows.push(`<div class="detail-info-row"><strong>季度</strong><span>${a.season} ${a.year || ''}</span></div>`);
    }
    if (a.duration > 0) {
        infoRows.push(`<div class="detail-info-row"><strong>时长</strong><span>${a.duration} 分钟/话</span></div>`);
    }
    if (a.staff && a.staff.length) {
        // 优先显示 Director
        const directors = a.staff.filter(s => /Director|监督/i.test(s.role || s.role_cn || ''));
        const directorNames = directors.length
            ? directors.map(s => s.name).join(' / ')
            : (a.staff.find(s => /Series Composition|系列构成/i.test(s.role || ''))?.name || '');
        if (directorNames) {
            infoRows.push(`<div class="detail-info-row"><strong>监督</strong><span>${escapeHtml(directorNames)}</span></div>`);
        }
    }
    if (a.status) {
        const statusMap = { 'FINISHED': '已完结', 'RELEASING': '放送中', 'NOT_YET_RELEASED': '未开播', 'CANCELLED': '已取消', 'HIATUS': '停更中' };
        infoRows.push(`<div class="detail-info-row"><strong>状态</strong><span>${statusMap[a.status] || a.status}</span></div>`);
    }

    // ---- 声优（双语显示） ----
    const roleCnMap = { 'MAIN': '主角', 'SUPPORTING': '配角', 'BACKGROUND': '背景' };
    let vaHtml = '<p style="color:#9ca3af">暂无数据</p>';
    if (a.va && a.va.length) {
        vaHtml = '<div class="detail-va-grid">' + a.va.map(v => {
            // 显示：中日双语，竖排
            const cnName = v.cn ? `<span class="va-cn">${escapeHtml(v.cn)}</span>` : '';
            const charName = v.character ? escapeHtml(v.character) : '?';
            const charRole = v.role && roleCnMap[v.role] ? `<span class="va-role-tag">${roleCnMap[v.role]}</span>` : '';
            return `
                <div class="detail-va-item">
                    <div class="va-line">
                        <span class="va-jp">🎙️ ${escapeHtml(v.name)}</span>
                        ${cnName}
                    </div>
                    <div class="va-char">
                        ${charRole}
                        <span class="char-name">饰 ${charName}</span>
                    </div>
                </div>
            `;
        }).join('') + '</div>';
    }

    // ---- Staff（角色 + 中文） ----
    let staffHtml = '';
    if (a.staff && a.staff.length) {
        staffHtml = '<div class="detail-staff-grid">' + a.staff.map(s => {
            const roleLabel = s.role_cn && s.role_cn !== s.role ? `${s.role_cn} <span class="role-en">(${escapeHtml(s.role)})</span>` : (s.role_cn || s.role);
            return `<div class="detail-staff-item"><span class="staff-role">${roleLabel}</span><span class="staff-name">${escapeHtml(s.name)}</span></div>`;
        }).join('') + '</div>';
    }

    // ---- 续集卡片 ----
    let sequelsSection = '';
    if (data.sequels && data.sequels.length) {
        sequelsSection = `
            <div class="detail-section" id="detail-sequels-section">
                <h3>📺 续集系列</h3>
                <div class="detail-card-row" id="detail-sequels">
                    ${data.sequels.map(s => renderMiniCard(s)).join('')}
                </div>
            </div>`;
    }

    // ---- 相似番剧卡片 ----
    let similarSection = '';
    if (data.similar && data.similar.length) {
        similarSection = `
            <div class="detail-section" id="detail-similar-section">
                <h3>🎯 相似番剧</h3>
                <div class="detail-card-row" id="detail-similar">
                    ${data.similar.map(s => renderMiniCard(s)).join('')}
                </div>
            </div>`;
    }

    // ---- 组装 HTML ----
    scroll.innerHTML = `
        <div class="detail-header">
            <div class="detail-cover">
                <img src="${escapeHtml(coverImg)}" alt="${escapeHtml(title)}"
                     onerror="this.style.background='#374151'; this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 140%22><rect fill=%22%23374151%22 width=%22100%22 height=%22140%22/><text fill=%22%236b7280%22 x=%2250%22 y=%2275%22 text-anchor=%22middle%22 font-size=%2214%22>暂无封面</text></svg>'">
            </div>
            <div class="detail-meta">
                <h2>${escapeHtml(title)}</h2>
                ${original ? `<div class="detail-original-name">${escapeHtml(original)}</div>` : ''}
                <div class="detail-stats">${statsHtml.join('')}</div>
                ${tagsHtml ? `<div class="detail-tags">${tagsHtml}</div>` : ''}
            </div>
        </div>
        ${summary !== '暂无简介' ? `
        <div class="detail-section">
            <h3>📖 简介</h3>
            <p>${escapeHtml(summary)}</p>
        </div>` : ''}
        ${infoRows.length ? `
        <div class="detail-section">
            <h3>📋 制作信息</h3>
            <div class="detail-info-grid">${infoRows.join('')}</div>
        </div>` : ''}
        ${staffHtml ? `
        <div class="detail-section">
            <h3>👥 Staff</h3>
            ${staffHtml}
        </div>` : ''}
        <div class="detail-section">
            <h3>🎤 声优阵容</h3>
            ${vaHtml}
        </div>
        ${sequelsSection}
        ${similarSection}
    `;

    // ---- 重新绑定 mini 卡片点击 ----
    scroll.querySelectorAll('.detail-mini-card').forEach(card => {
        card.addEventListener('click', () => {
            const id = parseInt(card.dataset.id);
            if (id) openAnimeDetail(id);
        });
    });

    // ---- 推荐按钮 ----
    const btnRec = document.getElementById('detail-btn-recommend');
    if (btnRec) {
        btnRec.onclick = () => {
            // 先捕获 ID：closeDetail 会把 currentDetailId 重置为 null
            const id = currentDetailId;
            if (!id) {
                console.warn('无 currentDetailId，关闭弹窗');
                closeDetail();
                return;
            }
            closeDetail();
            // 切换到"按番剧"tab 并用当前番剧做种子推荐
            const tabAnime = document.querySelector('.tab[data-tab="anime"]');
            if (tabAnime) tabAnime.click();
            if (typeof fetchRecommendationsByAnime === 'function') {
                const searchInput = document.getElementById('search-anime');
                if (searchInput) searchInput.value = title;
                fetchRecommendationsByAnime(id);
            }
            // 滚动到推荐区域
            setTimeout(() => {
                document.getElementById('results-anime')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 300);
        };
    }

    // ---- 待看按钮 ----
    const btnWatch = document.getElementById('detail-btn-watchlist');
    if (btnWatch) {
        updateListBtnState(btnWatch, WATCHLIST_KEY, a, '📌 加入待看', '📌 已在待看');
        btnWatch.onclick = () => {
            const id = currentDetailId;
            if (!id) return;
            if (isInList(WATCHLIST_KEY, id)) {
                removeFromList(WATCHLIST_KEY, id);
                btnWatch.textContent = '📌 加入待看';
                btnWatch.classList.remove('btn-added');
            } else {
                addToList(WATCHLIST_KEY, a);
                btnWatch.textContent = '📌 已在待看';
                btnWatch.classList.add('btn-added');
            }
        };
    }

    // ---- 收藏按钮 ----
    const btnFav = document.getElementById('detail-btn-favorite');
    if (btnFav) {
        updateListBtnState(btnFav, FAVORITES_KEY, a, '⭐ 收藏', '⭐ 已收藏');
        btnFav.onclick = () => {
            const id = currentDetailId;
            if (!id) return;
            if (isInList(FAVORITES_KEY, id)) {
                removeFromList(FAVORITES_KEY, id);
                btnFav.textContent = '⭐ 收藏';
                btnFav.classList.remove('btn-added');
            } else {
                addToList(FAVORITES_KEY, a);
                btnFav.textContent = '⭐ 已收藏';
                btnFav.classList.add('btn-added');
            }
        };
    }

    // ---- 滚动到顶部 ----
    scroll.scrollTop = 0;
}

// ===== 小卡片渲染 =====
function renderMiniCard(item) {
    const title = item.name_cn || item.name || '(无标题)';
    const score = item.rating ? `⭐ ${item.rating.toFixed(1)}` : '';
    const year = item.year || '';
    return `
        <div class="detail-mini-card" data-id="${item.id}">
            <img src="${escapeHtml(item.image)}" loading="lazy" alt="${escapeHtml(title)}"
                 onerror="this.style.background='#374151'; this.removeAttribute('src')">
            <div class="mini-body">
                <div class="mini-title">${escapeHtml(title)}</div>
                ${year ? `<div class="mini-meta">${year}</div>` : ''}
                ${score ? `<div class="mini-score">${score}</div>` : ''}
            </div>
        </div>`;
}

// ===== 更新列表按钮状态 =====
function updateListBtnState(btn, storageKey, anime, defaultText, addedText) {
    if (isInList(storageKey, anime.id)) {
        btn.textContent = addedText;
        btn.classList.add('btn-added');
    } else {
        btn.textContent = defaultText;
        btn.classList.remove('btn-added');
    }
}

// ===== 关闭弹窗 =====
function closeDetail() {
    if (!detailOverlay) return;
    detailOverlay.classList.remove('show');
    document.body.style.overflow = '';
    currentDetailId = null;
    currentDetailData = null;
}
