// ========================================
// va.js - v1.2 声优 tab 前端
// ========================================

const searchVA = document.getElementById('search-va');
const vaResults = document.getElementById('va-search-results');
const vaDetail = document.getElementById('va-detail');
const vaCount = document.getElementById('va-count');
const resultsVA = document.getElementById('results-va');

let currentVA = null;

searchVA.addEventListener('input', debounce(async () => {
    const q = searchVA.value.trim();
    if (!q) {
        vaResults.classList.remove('show');
        return;
    }
    try {
        const r = await fetch(`/api/voice-actors?q=${encodeURIComponent(q)}&limit=20`);
        const data = await r.json();
        if (!data.results || data.results.length === 0) {
            vaResults.innerHTML = '<div class="search-result-item" style="color:#9ca3af">没找到声优</div>';
        } else {
            vaResults.innerHTML = data.results.map(va => `
                <div class="va-result-item" data-name="${escapeHtml(va.name)}">
                    <div class="va-name">${escapeHtml(va.name)}</div>
                    <div class="va-score">${Math.round(va.score)}</div>
                </div>
            `).join('');
            vaResults.querySelectorAll('.va-result-item[data-name]').forEach(item => {
                item.addEventListener('click', () => {
                    const name = item.dataset.name;
                    searchVA.value = name;
                    vaResults.classList.remove('show');
                    loadVAAnime(name);
                });
            });
        }
        vaResults.classList.add('show');
    } catch (e) {
        console.error(e);
    }
}, 250));

document.addEventListener('click', (e) => {
    if (searchVA && !searchVA.contains(e.target) && !vaResults.contains(e.target)) {
        vaResults.classList.remove('show');
    }
});

async function loadVAAnime(name) {
    currentVA = name;
    vaDetail.style.display = 'block';
    resultsVA.innerHTML = '<div class="loading">加载中...</div>';
    vaCount.textContent = '';
    try {
        const r = await fetch(`/api/anime-by-va?name=${encodeURIComponent(name)}&limit=50`);
        const data = await r.json();
        if (data.error) {
            resultsVA.innerHTML = `<div class="empty">出错了: ${data.error}</div>`;
            return;
        }
        vaCount.textContent = `（${data.results.length} 部）`;
        renderResults(resultsVA, data.results, '该声优暂无番剧数据');
    } catch (e) {
        resultsVA.innerHTML = `<div class="empty">网络错误</div>`;
    }
}
