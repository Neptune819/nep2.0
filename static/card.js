// ========================================
// card.js - v1.2 增强 renderCard
// - tags 用 tags_cn（如「校园」而非 "School"）
// - 标题: name_cn（来自 display_name_cn，已 fallback）
// - 副标题: name（罗马字原名）若与标题不同才显示
// - reasons 标签
// ========================================

function renderCardDetailed(anime) {
    const title = anime.name_cn || anime.name || '(无标题)';
    // 原名（罗马字）只在与标题不同时显示
    const titleEn = anime.name && anime.name !== title ? anime.name : '';
    const score = anime.score || 0;
    const scorePct = Math.min(100, Math.max(0, score * 100));
    const rating = anime.rating ? `⭐ ${anime.rating.toFixed(1)}` : '';
    const year = anime.year || '?';
    const fmt = anime.format || '';
    const status = anime.status || '';
    const isUnreleased = status === 'NOT_YET_RELEASED';
    const isReleasing = status === 'RELEASING';
    const statusBadge = isUnreleased ? '<span class="status-badge unreleased">未开播</span>'
        : isReleasing ? '<span class="status-badge releasing">放送中</span>' : '';
    const reasons = anime.reasons || [];
    // tags 优先用 tags_cn
    const tagList = (anime.tags_cn && anime.tags_cn.length) ? anime.tags_cn : (anime.tags || []);
    return `
        <div class="anime-card detailed${isUnreleased ? ' unreleased-card' : ''}" data-id="${anime.id}">
            <img class="image" src="${escapeHtml(anime.image)}" alt="${escapeHtml(title)}" loading="lazy"
                 onerror="this.style.background='#374151'; this.removeAttribute('src')">
            ${statusBadge ? `<div class="card-status-badge">${statusBadge}</div>` : ''}
            <div class="body">
                <div class="title">${escapeHtml(title)}</div>
                ${titleEn ? `<div class="title-en">${escapeHtml(titleEn)}</div>` : ''}
                <div class="meta">
                    <span>${rating}</span>
                    <span>${year}</span>
                    <span>${fmt}</span>
                </div>
                <div class="score-bar"><div class="score-bar-fill" style="width:${scorePct}%"></div></div>
                ${tagList.length ? `<div class="tags">${tagList.slice(0, 3).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}</div>` : ''}
                ${reasons.length ? `<div class="reasons">${reasons.slice(0, 4).map(r => `<span class="reason">${escapeHtml(r)}</span>`).join('')}</div>` : ''}
            </div>
        </div>
    `;
}

// 覆盖原 renderResults
// 注意：卡片点击事件由 index.html 的全局事件委托处理
if (typeof renderResults === 'function') {
    window.renderResults = function(container, results, emptyMsg) {
        if (!results || results.length === 0) {
            container.innerHTML = `<div class="empty">${emptyMsg}</div>`;
            return;
        }
        container.innerHTML = results.map(renderCardDetailed).join('');
        // 不再需要逐个绑定点击事件——全局事件委托统一处理
    };
}
