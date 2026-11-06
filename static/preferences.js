// Shared recommendation exclusions. Kept in the browser with the watch history.
const NEP_FILTER_KEY = 'nep_recommendation_filters_v1';

function nepReadFilters() {
    try {
        const raw = JSON.parse(localStorage.getItem(NEP_FILTER_KEY) || '{}');
        return {
            excludeWatched: raw.excludeWatched !== false,
            minYear: Number.isInteger(Number(raw.minYear)) && Number(raw.minYear) >= 1900 ? Number(raw.minYear) : null,
            excludeTags: Array.isArray(raw.excludeTags) ? raw.excludeTags.filter(t => typeof t === 'string') : [],
        };
    } catch (_) {
        return {excludeWatched: true, minYear: null, excludeTags: []};
    }
}

function nepWatchedIds() {
    try {
        const list = JSON.parse(localStorage.getItem('anime_history') || '[]');
        return new Set(Array.isArray(list) ? list.map(a => String(a.id)) : []);
    } catch (_) { return new Set(); }
}

function nepAllowedAnime(anime, filters = nepReadFilters(), watched = nepWatchedIds()) {
    if (!anime || !anime.id) return false;
    if (filters.excludeWatched && watched.has(String(anime.id))) return false;
    if (filters.minYear && (!Number(anime.year || anime.season_year) || Number(anime.year || anime.season_year) < filters.minYear)) return false;
    const tags = [...(anime.tags || []), ...(anime.tags_cn || [])].map(t => String(typeof t === 'string' ? t : (t.cn || t.en || '')).trim().toLocaleLowerCase());
    return !filters.excludeTags.some(t => tags.includes(t.trim().toLocaleLowerCase()));
}

function nepFilterAnimeList(items) {
    if (!Array.isArray(items)) return [];
    const filters = nepReadFilters();
    const watched = nepWatchedIds();
    return items.filter(a => nepAllowedAnime(a, filters, watched));
}

window.nepReadFilters = nepReadFilters;
window.nepAllowedAnime = nepAllowedAnime;
window.nepFilterAnimeList = nepFilterAnimeList;

function nepApiFilterPayload() {
    const filters = nepReadFilters();
    return {
        exclude_ids: filters.excludeWatched ? [...nepWatchedIds()].map(Number).filter(Number.isInteger) : [],
        exclude_tags: filters.excludeTags,
        min_year: filters.minYear,
    };
}
function nepApiFilterQuery() {
    const prefs = nepApiFilterPayload();
    const params = new URLSearchParams();
    if (prefs.exclude_ids.length) params.set('exclude_ids', prefs.exclude_ids.join(','));
    if (prefs.exclude_tags.length) params.set('exclude_tags', prefs.exclude_tags.join(','));
    if (prefs.min_year) params.set('min_year', String(prefs.min_year));
    return params;
}
window.nepApiFilterPayload = nepApiFilterPayload;
window.nepApiFilterQuery = nepApiFilterQuery;

function nepRefreshVisibleCards() {
    const data = window.nepCardData;
    if (!data) return;
    for (const card of document.querySelectorAll('.results .anime-card')) {
        const anime = data.get(Number(card.dataset.id));
        if (anime) card.hidden = !nepAllowedAnime(anime);
    }
}

function nepInitFilterSettings() {
    const save = document.getElementById('nep-save-filters');
    if (!save) return;
    const watched = document.getElementById('nep-exclude-watched');
    const year = document.getElementById('nep-min-year');
    const tags = document.getElementById('nep-exclude-tags');
    const status = document.getElementById('nep-filter-status');
    const current = nepReadFilters();
    watched.checked = current.excludeWatched;
    year.value = current.minYear || '';
    tags.value = current.excludeTags.join('，');

    save.addEventListener('click', () => {
        const y = year.value.trim();
        const minYear = y ? Number(y) : null;
        if (y && (!Number.isInteger(minYear) || minYear < 1900 || minYear > 2100)) {
            status.textContent = '请输入 1900 到 2100 之间的完整年份。';
            return;
        }
        const excludeTags = [...new Set(tags.value.split(/[,，、;；\n]+/).map(t => t.trim()).filter(Boolean))];
        localStorage.setItem(NEP_FILTER_KEY, JSON.stringify({excludeWatched: watched.checked, minYear, excludeTags}));
        status.textContent = '已保存。当前结果已过滤；重新点击推荐可获取符合条件的新结果。';
        nepRefreshVisibleCards();
        document.dispatchEvent(new CustomEvent('nepFiltersChanged'));
    });
    document.getElementById('nep-reset-filters').addEventListener('click', () => {
        watched.checked = true;
        year.value = '';
        tags.value = '';
        localStorage.setItem(NEP_FILTER_KEY, JSON.stringify({excludeWatched: true, minYear: null, excludeTags: []}));
        status.textContent = '已清空；重新点击推荐可刷新结果。';
        nepRefreshVisibleCards();
        document.dispatchEvent(new CustomEvent('nepFiltersChanged'));
    });
    fetch('/api/tags').then(r => r.json()).then(data => {
        const options = document.getElementById('nep-filter-tag-options');
        for (const item of (data.tags || [])) {
            const option = document.createElement('option');
            option.value = Array.isArray(item) ? item[0] : String(item);
            options.appendChild(option);
        }
    }).catch(() => {});
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', nepInitFilterSettings);
else nepInitFilterSettings();
