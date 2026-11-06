// ========================================
// card.js - v1.2 增强 renderCard
// - tags 用 tags_cn（如「校园」而非 "School"）
// - 标题: name_cn（来自 display_name_cn，已 fallback）
// - 副标题: name（罗马字原名）若与标题不同才显示
// - reasons 标签
// ========================================

window.nepCardData = window.nepCardData || new Map();

function nepSavedPersonalRating(id) {
    try {
        const list = JSON.parse(localStorage.getItem('anime_history') || '[]');
        const item = Array.isArray(list) ? list.find(a => String(a.id) === String(id)) : null;
        return Number(item?.rating) || 0;
    } catch (_) { return 0; }
}

function renderCardDetailed(anime) {
    if (typeof nepAllowedAnime === 'function' && !nepAllowedAnime(anime)) return '';
    window.nepCardData.set(Number(anime.id), anime);
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
                <label class="personal-rating" style="display:flex;align-items:center;gap:6px;margin:8px 0;font-size:12px;">
                    我的评分
                    <select data-anime-id="${anime.id}" aria-label="为 ${escapeHtml(title)} 设置个人评分" style="background:#1f2937;color:#fff;border:1px solid #6b7280;border-radius:6px;padding:3px;">
                        <option value="0">未评分</option>
                        ${Array.from({length:10}, (_, i) => i + 1).map(n => `<option value="${n}" ${nepSavedPersonalRating(anime.id) === n ? 'selected' : ''}>${n} 分</option>`).join('')}
                    </select>
                </label>
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
        const visible = typeof nepFilterAnimeList === 'function' ? nepFilterAnimeList(results) : (results || []);
        if (!visible.length) {
            container.innerHTML = `<div class="empty">${results?.length ? '没有符合全站过滤条件的作品，可到「调参」页调整。' : (emptyMsg || '没有结果')}</div>`;
            return;
        }
        container.innerHTML = visible.map(renderCardDetailed).join('');
        // 不再需要逐个绑定点击事件——全局事件委托统一处理
    };
}

document.addEventListener('change', (event) => {
    const select = event.target.closest('.personal-rating select[data-anime-id]');
    if (!select) return;
    event.stopPropagation();
    const id = Number(select.dataset.animeId);
    const rating = Number(select.value);
    const anime = window.nepCardData.get(id);
    if (!anime || !Number.isInteger(id) || rating < 0 || rating > 10) return;
    try {
        const list = JSON.parse(localStorage.getItem('anime_history') || '[]');
        const items = Array.isArray(list) ? list : [];
        const existing = items.find(a => Number(a.id) === id);
        if (existing) existing.rating = rating;
        else if (rating > 0) items.push({id, name: anime.name_cn || anime.name || '', name_cn: anime.name_cn || '', name_en: anime.name || '', image: anime.image || '', year: anime.year || null, format: anime.format || '', tags: anime.tags || [], tags_cn: anime.tags_cn || [], rating});
        localStorage.setItem('anime_history', JSON.stringify(items));
        if (typeof history !== 'undefined' && Array.isArray(history)) {
            history.splice(0, history.length, ...items);
            if (typeof renderHistory === 'function') renderHistory();
        }
        document.querySelectorAll(`.personal-rating select[data-anime-id="${id}"]`).forEach(other => { other.value = String(rating); });
        document.dispatchEvent(new CustomEvent('nepHistoryChanged', {detail:{id, rating}}));
    } catch (error) {
        select.value = String(nepSavedPersonalRating(id));
        alert('评分未能保存，请检查浏览器是否允许本站存储数据。');
    }
});
