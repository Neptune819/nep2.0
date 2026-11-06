// ========================================
// trending.js - v1.4 加分页（加载更多）
// ========================================

const resultsTrending = document.getElementById('results-trending');
const chkCurrentYear = document.getElementById('chk-current-year');
const chkFall2026 = document.getElementById('chk-fall-2026');
const loadMoreTrending = document.getElementById('load-more-trending');
const TRENDING_PAGE = 24;

let trendingOffset = 0;
let trendingBaseParams = new URLSearchParams();

function buildTrendingParams(offset) {
    const p = new URLSearchParams(trendingBaseParams);
    p.set('limit', String(TRENDING_PAGE));
    p.set('offset', String(offset));
    if (typeof nepApiFilterQuery === 'function') {
        for (const [key, value] of nepApiFilterQuery()) p.set(key, value);
    }
    return p;
}

async function fetchTrendingPage(append) {
    if (!append) {
        trendingOffset = 0;
        resultsTrending.innerHTML = '<div class="loading">加载中...</div>';
        loadMoreTrending.style.display = 'none';
    } else {
        trendingOffset += TRENDING_PAGE;
    }
    try {
        const r = await fetch('/api/recommend/trending?' + buildTrendingParams(trendingOffset));
        const data = await r.json();
        if (data.error) {
            if (!append) resultsTrending.innerHTML = `<div class="empty">${data.error}</div>`;
            return;
        }
        if (append) {
            const tmp = document.createElement('div');
            tmp.innerHTML = data.results.map(window.renderCardDetailed || (a => `
                <div class="anime-card" data-id="${a.id}">
                    <img class="image" src="${(a.image || '').replace(/"/g, '&quot;')}" loading="lazy"
                         onerror="this.style.background='#374151'; this.removeAttribute('src')">
                    <div class="body"><div class="title">${(a.name_cn || a.name || '').replace(/</g, '&lt;')}</div></div>
                </div>
            `)).join('');
            while (tmp.firstChild) resultsTrending.appendChild(tmp.firstChild);
        } else {
            window.renderResults(resultsTrending, data.results, '本季暂无数据');
        }
        loadMoreTrending.style.display = data.has_more ? 'block' : 'none';
    } catch (e) {
        if (!append) resultsTrending.innerHTML = '<div class="empty">网络错误</div>';
    }
}

function loadTrending() {
    trendingBaseParams = new URLSearchParams();
    if (chkCurrentYear && chkCurrentYear.checked) {
        trendingBaseParams.set('year', '2026');
        if (chkFall2026 && chkFall2026.checked) {
            trendingBaseParams.set('season', 'FALL');
        }
    } else if (chkFall2026 && chkFall2026.checked) {
        trendingBaseParams.set('season', 'FALL');
    }
    fetchTrendingPage(false);
}

if (chkCurrentYear) chkCurrentYear.addEventListener('change', loadTrending);
if (chkFall2026) chkFall2026.addEventListener('change', loadTrending);

const trendingTab = document.querySelector('.tab[data-tab="trending"]');
if (trendingTab) trendingTab.addEventListener('click', loadTrending);

if (loadMoreTrending) {
    loadMoreTrending.querySelector('.load-more-btn').addEventListener('click', () => fetchTrendingPage(true));
}
