// ========================================
// script.js - v1.2
// 新增：分页（加载更多）、续集行、名称 fallback
// ========================================

// ===== Tab 切换 =====
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
    });
});

// ===== 工具函数 =====
function debounce(fn, delay = 300) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}

function escapeHtml(s) {
    if (!s) return '';
    return String(s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}

function animeNameFeedbackLink(query) {
    const title = `番剧名称纠错：${query}`;
    const body = `搜索词或现有译名：${query}\n建议的中文名：\n作品原名或 Bangumi 链接：\n问题说明：`;
    const url = 'https://github.com/Neptune-ux-sys/nep2.0/issues/new?' + new URLSearchParams({title, body});
    return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">反馈缺失或译名错误</a>`;
}

// renderResults 由 card.js 覆盖（增强版用 renderCardDetailed 显示 reasons/tags_cn），
// 这里先给个 fallback，让 card.js 加载前也能跑
function renderResults(container, results, emptyMsg) {
    if (!container) return;
    if (!results || results.length === 0) {
        container.innerHTML = `<div class="empty">${emptyMsg || '没有结果'}</div>`;
        return;
    }
    // 简单版（被 card.js 覆盖）
    container.innerHTML = results.map(a => `
        <div class="anime-card" data-id="${a.id}">
            <img class="image" src="${escapeHtml(a.image)}" loading="lazy"
                 onerror="this.style.background='#374151'; this.removeAttribute('src')">
            <div class="body">
                <div class="title">${escapeHtml(a.name_cn || a.name || '(无标题)')}</div>
            </div>
        </div>
    `).join('');
}

// ===== Tab 1: 按番剧 =====
const searchInput = document.getElementById('search-anime');
const searchResults = document.getElementById('search-results');
const resultsAnime = document.getElementById('results-anime');
const resultsSequels = document.getElementById('results-sequels');
const sequelsRow = document.getElementById('sequels-row');
const loadMoreAnime = document.getElementById('load-more-anime');

// 状态：当前查询 + 偏移
let currentAnimeId = null;
let currentOffset = 0;
const PAGE_SIZE = 12;

searchInput.addEventListener('input', debounce(async () => {
    const q = searchInput.value.trim();
    if (!q) {
        searchResults.classList.remove('show');
        return;
    }
    try {
        const r = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
        const data = await r.json();
        if (!data.results || data.results.length === 0) {
            searchResults.innerHTML = `<div class="search-result-item" style="color:#9ca3af">没找到。${animeNameFeedbackLink(q)}</div>`;
        } else {
            searchResults.innerHTML = data.results.map(a => `
                <div class="search-result-item" data-id="${a.id}">
                    <img src="${escapeHtml(a.image)}" onerror="this.style.background='#374151'; this.removeAttribute('src')">
                    <div class="info">
                        <div class="name">${escapeHtml(a.name_cn || a.name)}</div>
                        <div class="name-cn">${escapeHtml(a.name)}</div>
                    </div>
                    <div class="rating">${a.rating ? '⭐ ' + a.rating.toFixed(1) : ''}</div>
                </div>
            `).join('');
            searchResults.querySelectorAll('.search-result-item[data-id]').forEach(item => {
                item.addEventListener('click', () => {
                    const id = parseInt(item.dataset.id);
                    searchResults.classList.remove('show');
                    if (id && typeof openAnimeDetail === 'function') {
                        openAnimeDetail(id);
                    }
                });
            });
        }
        searchResults.classList.add('show');
    } catch (e) {
        console.error(e);
    }
}, 250));

document.addEventListener('click', (e) => {
    if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
        searchResults.classList.remove('show');
    }
});

async function fetchRecommendationsByAnime(id, append = false) {
    if (!append) {
        currentAnimeId = id;
        currentOffset = 0;
        resultsAnime.innerHTML = '<div class="loading">推荐中...</div>';
        sequelsRow.style.display = 'none';
        loadMoreAnime.style.display = 'none';
    } else {
        currentOffset += PAGE_SIZE;
    }
    try {
        const r = await fetch(`/api/recommend/anime?id=${id}&with_sequels=1&limit=${PAGE_SIZE}&offset=${currentOffset}&style=${currentStyle}&tuning=${encodeURIComponent(JSON.stringify(getUserTuning?.() || {}))}&${nepApiFilterQuery()}`);
        const data = await r.json();
        if (data.error) {
            resultsAnime.innerHTML = `<div class="empty">出错了: ${data.error}</div>`;
            return;
        }
        // 续集行（只在第一页显示）
        if (!append && data.sequels && data.sequels.length > 0) {
            sequelsRow.style.display = 'block';
            resultsSequels.innerHTML = data.sequels.map(s => `
                <div class="anime-card mini" data-id="${s.id}">
                    <img class="image" src="${escapeHtml(s.image)}" loading="lazy"
                         onerror="this.style.background='#374151'; this.removeAttribute('src')">
                    <div class="body">
                        <div class="title">${escapeHtml(s.name_cn || s.name)}</div>
                        <div class="meta"><span>${s.year || '?'}</span><span>${s.format || ''}</span></div>
                    </div>
                </div>
            `).join('');
            // 点击续集：由全局事件委托处理（index.html 中的 document click 监听）
        } else if (!append) {
            sequelsRow.style.display = 'none';
        }
        // 主推荐
        if (append) {
            const tmp = document.createElement('div');
            tmp.innerHTML = data.results.map(renderCardDetailed).join('');
            while (tmp.firstChild) {
                const node = tmp.firstChild;
                resultsAnime.appendChild(node);
            }
        } else {
            renderResults(resultsAnime, data.results, '没找到相似的番剧');
        }
        // 加载更多按钮
        loadMoreAnime.style.display = data.has_more ? 'block' : 'none';
    } catch (e) {
        if (!append) resultsAnime.innerHTML = `<div class="empty">网络错误</div>`;
    }
}

// 加载更多按钮
if (loadMoreAnime) {
    loadMoreAnime.querySelector('.load-more-btn').addEventListener('click', () => {
        if (currentAnimeId) fetchRecommendationsByAnime(currentAnimeId, true);
    });
}

// ===== Tab 2: 按历史 =====
let historyOffset = 0;
let historyPayload = null;  // 缓存请求参数，避免每次点"加载更多"重新构造
const loadMoreHistory = document.getElementById('load-more-history');
const HISTORY_PAGE = 12;
const historyInput = document.getElementById('search-history');
const historySearchResults = document.getElementById('history-search-results');
const historyList = document.getElementById('history-list');
const btnRecommendHistory = document.getElementById('btn-recommend-history');
const resultsHistory = document.getElementById('results-history');

// 使用 localStorage 持久化列表
function loadHistory() {
    try {
        const saved = localStorage.getItem('anime_history');
        const parsed = saved ? JSON.parse(saved) : [];
        return Array.isArray(parsed) ? parsed : [];
    } catch (_) { return []; }
}

function saveHistory() {
    try {
        localStorage.setItem('anime_history', JSON.stringify(history));
        return true;
    } catch (_) {
        alert('看番记录未能保存，请检查浏览器是否允许本站存储数据，或先导出备份。');
        return false;
    }
}

const history = loadHistory();

// A rating can also be changed from recommendation cards or the list page.
window.addEventListener('storage', event => {
    if (event.key !== 'anime_history') return;
    history.splice(0, history.length, ...loadHistory());
    renderHistory();
});

// Bangumi import previews matches and leaves ambiguous entries for explicit selection.
const bangumiPanel = document.getElementById('bangumi-import-panel');
const bangumiResult = document.getElementById('bangumi-import-result');
let bangumiPreview = null;
document.getElementById('btn-bangumi-import')?.addEventListener('click', () => {
    bangumiPanel.style.display = bangumiPanel.style.display === 'none' ? 'block' : 'none';
    if (bangumiPanel.style.display === 'block') bangumiPanel.scrollIntoView({behavior:'smooth', block:'nearest'});
});
document.getElementById('btn-close-bangumi')?.addEventListener('click', () => { bangumiPanel.style.display = 'none'; });
document.getElementById('btn-fetch-bangumi')?.addEventListener('click', async () => {
    const username = document.getElementById('bangumi-username').value.trim();
    if (!username) { bangumiResult.textContent = '请输入 Bangumi 用户名或数字 ID。'; return; }
    const button = document.getElementById('btn-fetch-bangumi');
    button.disabled = true;
    bangumiResult.textContent = '正在读取公开收藏并匹配本地番剧，请稍候……';
    try {
        const response = await fetch('/api/bangumi/import', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username})});
        const data = await response.json();
        if (!response.ok || data.error) throw new Error(data.error || `请求失败（${response.status}）`);
        bangumiPreview = data;
        const counts = data.counts || {};
        const ambiguous = (data.ambiguous || []).map((item, index) => `
            <label style="display:block;margin:8px 0;">${escapeHtml(item.name || '未命名番剧')}：
                <select class="bangumi-choice" data-index="${index}">
                    <option value="">暂不导入</option>
                    ${(item.candidates || []).map((candidate, i) => `<option value="${i}">${escapeHtml(candidate.name_cn || candidate.name || String(candidate.id))} · ${escapeHtml(candidate.name || '')} · ${escapeHtml(candidate.year || '?')}</option>`).join('')}
                </select>
            </label>`).join('');
        const unmatched = (data.unmatched || []).map(item => `<li>${escapeHtml(item.name || String(item.bgm_subject_id || '未知作品'))}：${escapeHtml(item.reason || '未匹配')}</li>`).join('');
        bangumiResult.innerHTML = `
            <p>读取 ${Number(data.total) || 0} 条；自动匹配 ${Number(counts.matched) || 0} 条，待确认 ${Number(counts.ambiguous) || 0} 条，未匹配 ${Number(counts.unmatched) || 0} 条。</p>
            ${ambiguous ? `<h4>重名或近似匹配，请选择正确作品</h4>${ambiguous}` : ''}
            ${unmatched ? `<details><summary>查看未匹配作品</summary><ul>${unmatched}</ul></details>` : ''}
            <button id="btn-apply-bangumi" class="btn-primary" ${!(data.matched || []).length && !ambiguous ? 'disabled' : ''}>导入已匹配的作品</button>`;
        document.getElementById('btn-apply-bangumi')?.addEventListener('click', applyBangumiImport);
    } catch (error) {
        bangumiResult.textContent = `导入失败：${error.message}`;
    } finally { button.disabled = false; }
});

function applyBangumiImport() {
    if (!bangumiPreview) return;
    const previousHistory = history.map(item => ({...item}));
    const selected = [...(bangumiPreview.matched || [])];
    bangumiResult.querySelectorAll('.bangumi-choice').forEach(select => {
        if (select.value === '') return;
        const item = bangumiPreview.ambiguous[Number(select.dataset.index)];
        const candidate = item?.candidates?.[Number(select.value)];
        if (candidate) selected.push({...candidate, rating:item.rating || 0});
    });
    let added = 0, updated = 0;
    for (const item of selected) {
        const id = Number(item.id);
        if (!Number.isInteger(id)) continue;
        const existing = history.find(a => Number(a.id) === id);
        if (existing) {
            if (Number(item.rating) > 0 && Number(existing.rating) !== Number(item.rating)) {
                existing.rating = Number(item.rating);
                updated++;
            }
        } else {
            history.push({...item, id, name:item.name_cn || item.name || '', rating:Number(item.rating) || 0});
            added++;
        }
    }
    try {
        if (!saveHistory()) {
            history.splice(0, history.length, ...previousHistory);
            return;
        }
        renderHistory();
        bangumiResult.insertAdjacentHTML('afterbegin', `<p role="status">已新增 ${added} 部，更新评分 ${updated} 部；未匹配和未选择的作品没有写入。现在的推荐会排除已看作品。</p>`);
        document.getElementById('btn-apply-bangumi').disabled = true;
    } catch (error) { bangumiResult.insertAdjacentHTML('afterbegin', '<p role="alert">保存失败，请检查浏览器存储空间。</p>'); }
}

historyInput.addEventListener('input', debounce(async () => {
    const q = historyInput.value.trim();
    if (!q) {
        historySearchResults.classList.remove('show');
        return;
    }
    const r = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const data = await r.json();
    if (!data.results.length) {
        historySearchResults.innerHTML = `<div class="search-result-item" style="color:#9ca3af">没找到。${animeNameFeedbackLink(q)}</div>`;
    } else {
        historySearchResults.innerHTML = data.results.map(a => `
            <div class="search-result-item" data-id="${a.id}">
                <img src="${escapeHtml(a.image)}" onerror="this.style.background='#374151'; this.removeAttribute('src')">
                <div class="info">
                    <div class="name">${escapeHtml(a.name_cn || a.name)}</div>
                    <div class="name-cn">${escapeHtml(a.name)}</div>
                </div>
                <div class="rating">${a.rating ? '⭐ ' + a.rating.toFixed(1) : ''}</div>
            </div>
        `).join('');
        historySearchResults.querySelectorAll('.search-result-item[data-id]').forEach(item => {
            item.addEventListener('click', () => {
                const a = data.results.find(x => x.id == item.dataset.id);
                if (a && !history.find(h => h.id == a.id)) {
                    // 不设置默认评分，让用户自己打分
                    history.push({...a, rating: 0});
                    renderHistory();
                }
                historyInput.value = '';
                historySearchResults.classList.remove('show');
            });
        });
    }
    historySearchResults.classList.add('show');
}, 250));

document.addEventListener('click', (e) => {
    if (!historyInput.contains(e.target) && !historySearchResults.contains(e.target)) {
        historySearchResults.classList.remove('show');
    }
});

function renderHistory() {
    saveHistory(); // 每次渲染都保存
    
    if (history.length === 0) {
        historyList.innerHTML = '<li class="empty">还没添加番剧。使用上方搜索、批量导入或文件导入添加。</li>';
        btnRecommendHistory.disabled = true;
        btnRecommendHistory.textContent = '📚 推荐';
        return;
    }
    historyList.innerHTML = history.map((h, i) => `
        <li class="history-item" data-idx="${i}">
            <span class="idx">${i + 1}</span>
            <img src="${escapeHtml(h.image)}" onerror="this.style.background='#374151'; this.removeAttribute('src')">
            <div class="name">
                <div class="cn">${escapeHtml(h.name_cn || h.name)}</div>
                <div class="en">${escapeHtml(h.name)}</div>
            </div>
            <div class="rating-input">
                <span>评分:</span>
                <input type="number" min="1" max="10" step="1" value="${h.rating}" data-idx="${i}">
            </div>
            <button class="remove-btn" data-idx="${i}">移除</button>
        </li>
    `).join('');
    historyList.querySelectorAll('.remove-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            history.splice(+btn.dataset.idx, 1);
            renderHistory();
        });
    });
    historyList.querySelectorAll('.rating-input input').forEach(inp => {
        inp.addEventListener('change', () => {
            const v = parseInt(inp.value);
            if (v >= 1 && v <= 10) {
                const previous = history[+inp.dataset.idx].rating;
                history[+inp.dataset.idx].rating = v;
                if (!saveHistory()) {
                    history[+inp.dataset.idx].rating = previous;
                    inp.value = String(previous || 0);
                }
            }
        });
    });
    btnRecommendHistory.disabled = history.length === 0;
    btnRecommendHistory.textContent = `📚 推荐 (${history.length}部)`;
}

btnRecommendHistory.addEventListener('click', async () => {
    historyOffset = 0;
    historyPayload = {
        history: history.map(h => ({id: h.id, rating: h.rating})),
        ...nepApiFilterPayload(),
        limit: HISTORY_PAGE,
        offset: 0,
        style: currentStyle,
        tuning: getUserTuning?.() || null,
    };
    await fetchHistoryPage();
});

async function fetchHistoryPage() {
    if (!historyPayload) return;
    if (historyOffset === 0) {
        resultsHistory.innerHTML = '<div class="loading">推荐中...</div>';
        loadMoreHistory.style.display = 'none';
    } else {
        historyPayload.offset = historyOffset;
    }
    try {
        const r = await fetch('/api/recommend/history', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(historyPayload),
        });
        const data = await r.json();
        if (data.error) {
            resultsHistory.innerHTML = `<div class="empty">出错了: ${data.error}</div>`;
            return;
        }
        if (historyOffset === 0) {
            renderResults(resultsHistory, data.results, '没找到推荐');
        } else {
            // 追加
            const tmp = document.createElement('div');
            tmp.innerHTML = data.results.map(renderCardDetailed || (a => `
                <div class="anime-card" data-id="${a.id}">
                    <img class="image" src="${escapeHtml(a.image)}" loading="lazy"
                         onerror="this.style.background='#374151'; this.removeAttribute('src')">
                    <div class="body"><div class="title">${escapeHtml(a.name_cn || a.name || '')}</div></div>
                </div>
            `)).join('');
            while (tmp.firstChild) resultsHistory.appendChild(tmp.firstChild);
        }
        historyOffset += data.results.length;
        loadMoreHistory.style.display = data.has_more ? 'block' : 'none';
    } catch (e) {
        if (historyOffset === 0) resultsHistory.innerHTML = `<div class="empty">网络错误</div>`;
    }
}

if (loadMoreHistory) {
    loadMoreHistory.querySelector('.load-more-btn').addEventListener('click', fetchHistoryPage);
}

// ===== 批量导入 =====
const btnBatchImport = document.getElementById('btn-batch-import');
const batchImportPanel = document.getElementById('batch-import-panel');
const batchImportText = document.getElementById('batch-import-text');
const btnParseBatch = document.getElementById('btn-parse-batch');
const btnCancelBatch = document.getElementById('btn-cancel-batch');
const batchParseResult = document.getElementById('batch-parse-result');

btnBatchImport.addEventListener('click', () => {
    batchImportPanel.style.display = batchImportPanel.style.display === 'none' ? 'block' : 'none';
    batchParseResult.style.display = 'none';
    batchImportText.value = '';
});

btnCancelBatch.addEventListener('click', () => {
    batchImportPanel.style.display = 'none';
    batchParseResult.style.display = 'none';
});

btnParseBatch.addEventListener('click', async () => {
    const text = batchImportText.value.trim();
    if (!text) return;

    btnParseBatch.disabled = true;
    btnParseBatch.textContent = '解析中...';
    batchParseResult.style.display = 'block';
    batchParseResult.innerHTML = '<div class="loading">正在解析...</div>';

    try {
        const r = await fetch('/api/parse-history', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text})
        });
        const data = await r.json();

        if (data.error) {
            batchParseResult.innerHTML = `<div class="empty">错误: ${data.error}</div>`;
            return;
        }

        let html = `<div class="result-header">
            <span class="success">匹配 ${data.total_matched}</span> / 
            <span>共 ${data.total_input} 个</span>
            ${data.unmatched.length > 0 ? `，<span class="fail">${data.unmatched.length} 个未匹配</span>` : ''}
        </div>`;

        if (data.matched.length > 0) {
            html += '<div class="matched-list">';
            data.matched.forEach(a => {
                html += `<div class="matched-item" data-id="${a.id}">
                    <img src="${escapeHtml(a.image)}" onerror="this.style.background='#374151'; this.removeAttribute('src')">
                    <div class="name">
                        <div>${escapeHtml(a.name_cn || a.name)}</div>
                        <div class="query">查询: ${escapeHtml(a.query)}</div>
                    </div>
                </div>`;
            });
            html += '</div>';
        }

        if (data.unmatched.length > 0) {
            html += '<div style="margin-top:12px"><strong style="color:#f87171">未匹配：</strong></div>';
            data.unmatched.forEach(name => {
                html += `<div class="unmatched-item">• ${escapeHtml(name)}</div>`;
            });
        }

        batchParseResult.innerHTML = html;

        // 自动添加到列表
        let addedCount = 0;
        data.matched.forEach(a => {
            if (!history.find(h => h.id == a.id)) {
                history.push({...a, rating: 7});
                addedCount++;
            }
        });
        renderHistory();
        
        // 显示添加结果
        const addMsg = document.createElement('div');
        addMsg.className = 'add-result-msg';
        addMsg.innerHTML = `<span style="color:#34d399">✓ 已自动添加 ${addedCount} 部到列表</span>`;
        batchParseResult.insertBefore(addMsg, batchParseResult.firstChild);
        
        // 2秒后自动关闭面板并滚动到列表
        setTimeout(() => {
            batchImportPanel.style.display = 'none';
            batchParseResult.style.display = 'none';
            historyList.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 1500);

    } catch (e) {
        batchParseResult.innerHTML = '<div class="empty">网络错误</div>';
    } finally {
        btnParseBatch.disabled = false;
        btnParseBatch.textContent = '🔍 解析';
    }
});

// ===== 文件导入 =====
const btnFileImport = document.getElementById('btn-file-import');
const fileImportPanel = document.getElementById('file-import-panel');
const fileInput = document.getElementById('file-input');
const fileUploadArea = document.getElementById('file-upload-area');
const fileUploadInfo = document.getElementById('file-upload-info');
const fileNameSpan = document.getElementById('file-name');
const btnClearFile = document.getElementById('btn-clear-file');
const btnParseFile = document.getElementById('btn-parse-file');
const btnCancelFile = document.getElementById('btn-cancel-file');
const fileParseResult = document.getElementById('file-parse-result');

let selectedFile = null;

btnFileImport.addEventListener('click', () => {
    fileImportPanel.style.display = fileImportPanel.style.display === 'none' ? 'block' : 'none';
    batchImportPanel.style.display = 'none'; // 关闭另一个面板
    fileParseResult.style.display = 'none';
    selectedFile = null;
    fileUploadInfo.style.display = 'none';
    btnParseFile.disabled = true;
});

btnCancelFile.addEventListener('click', () => {
    fileImportPanel.style.display = 'none';
    fileParseResult.style.display = 'none';
});

// 点击上传区域
fileUploadArea.addEventListener('click', () => {
    fileInput.click();
});

// 拖拽上传
fileUploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    fileUploadArea.classList.add('dragover');
});

fileUploadArea.addEventListener('dragleave', () => {
    fileUploadArea.classList.remove('dragover');
});

fileUploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    fileUploadArea.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
        handleFileSelect(e.dataTransfer.files[0]);
    }
});

// 文件选择
fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        handleFileSelect(fileInput.files[0]);
    }
});

function handleFileSelect(file) {
    // 检查文件大小 (10MB)
    if (file.size > 10 * 1024 * 1024) {
        alert('文件太大，请选择小于10MB的文件');
        return;
    }
    
    selectedFile = file;
    fileNameSpan.textContent = `📎 ${file.name} (${(file.size / 1024).toFixed(1)}KB)`;
    fileUploadInfo.style.display = 'flex';
    btnParseFile.disabled = false;
}

btnClearFile.addEventListener('click', () => {
    selectedFile = null;
    fileInput.value = '';
    fileUploadInfo.style.display = 'none';
    btnParseFile.disabled = true;
});

btnParseFile.addEventListener('click', async () => {
    if (!selectedFile) return;
    
    btnParseFile.disabled = true;
    btnParseFile.textContent = '解析中...';
    fileParseResult.style.display = 'block';
    fileParseResult.innerHTML = '<div class="loading">正在解析文件...</div>';
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    
    try {
        const r = await fetch('/api/parse-file', {
            method: 'POST',
            body: formData
        });
        const data = await r.json();
        
        if (data.error) {
            fileParseResult.innerHTML = `<div class="empty">错误: ${data.error}</div>`;
            return;
        }
        
        let html = `<div class="result-header">
            <span class="success">匹配 ${data.total_matched}</span> / 
            <span>共 ${data.total_input} 个</span>
            ${data.unmatched.length > 0 ? `，<span class="fail">${data.unmatched.length} 个未匹配</span>` : ''}
        </div>`;
        
        if (data.matched.length > 0) {
            html += '<div class="matched-list">';
            data.matched.forEach(a => {
                html += `<div class="matched-item" data-id="${a.id}">
                    <img src="${escapeHtml(a.image)}" onerror="this.style.background='#374151'; this.removeAttribute('src')">
                    <div class="name">
                        <div>${escapeHtml(a.name_cn || a.name)}</div>
                        <div class="query">查询: ${escapeHtml(a.query)}</div>
                    </div>
                </div>`;
            });
            html += '</div>';
        }
        
        if (data.unmatched.length > 0) {
            html += '<div style="margin-top:12px"><strong style="color:#f87171">未匹配：</strong></div>';
            data.unmatched.forEach(name => {
                html += `<div class="unmatched-item">• ${escapeHtml(name)}</div>`;
            });
        }
        
        fileParseResult.innerHTML = html;
        
        // 自动添加到列表
        let addedCount = 0;
        data.matched.forEach(a => {
            if (!history.find(h => h.id == a.id)) {
                history.push({...a, rating: 7});
                addedCount++;
            }
        });
        renderHistory();
        
        // 显示添加结果
        const addMsg = document.createElement('div');
        addMsg.className = 'add-result-msg';
        addMsg.innerHTML = `<span style="color:#34d399">✓ 已自动添加 ${addedCount} 部到列表</span>`;
        fileParseResult.insertBefore(addMsg, fileParseResult.firstChild);
        
        // 2秒后自动关闭面板并滚动到列表
        setTimeout(() => {
            fileImportPanel.style.display = 'none';
            fileParseResult.style.display = 'none';
            historyList.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 1500);
        
    } catch (e) {
        fileParseResult.innerHTML = '<div class="empty">网络错误</div>';
    } finally {
        btnParseFile.disabled = false;
        btnParseFile.textContent = '🔍 解析文件';
    }
});

// ===== 导出（多格式）=====
const btnExportMenu = document.getElementById('btn-export-menu');
const exportMenu = document.getElementById('export-menu');
if (btnExportMenu && exportMenu) {
    btnExportMenu.addEventListener('click', (e) => {
        e.stopPropagation();
        exportMenu.style.display = exportMenu.style.display === 'block' ? 'none' : 'block';
    });
    document.addEventListener('click', () => {
        exportMenu.style.display = 'none';
    });
    exportMenu.querySelectorAll('button[data-fmt]').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            exportMenu.style.display = 'none';
            if (history.length === 0) {
                alert('列表为空，没有可导出的内容');
                return;
            }
            await exportAnimeList(history, btn.dataset.fmt, btn);
        });
    });
}

renderHistory();

// ===== Tab 3: 按标签 =====
const tagCloud = document.getElementById('tag-cloud');
const btnRecommendTags = document.getElementById('btn-recommend-tags');
const btnClearTags = document.getElementById('btn-clear-tags');
const resultsTags = document.getElementById('results-tags');
const selectedTags = new Set();

(async () => {
    try {
        const r = await fetch('/api/tags');
        const data = await r.json();
        tagCloud.innerHTML = data.tags.map(([name, count]) => `
            <span class="tag-item" data-tag="${escapeHtml(name)}">
                ${escapeHtml(name)}<span class="count">${count}</span>
            </span>
        `).join('');
        tagCloud.querySelectorAll('.tag-item').forEach(item => {
            item.addEventListener('click', () => {
                const t = item.dataset.tag;
                if (selectedTags.has(t)) {
                    selectedTags.delete(t);
                    item.classList.remove('selected');
                } else {
                    selectedTags.add(t);
                    item.classList.add('selected');
                }
                btnRecommendTags.disabled = selectedTags.size === 0;
            });
        });
    } catch (e) {
        tagCloud.innerHTML = '<div class="empty">标签加载失败</div>';
    }
})();

btnClearTags.addEventListener('click', () => {
    selectedTags.clear();
    document.querySelectorAll('.tag-item.selected').forEach(el => el.classList.remove('selected'));
    btnRecommendTags.disabled = true;
});

let tagsOffset = 0;
let tagsPayload = null;
const loadMoreTags = document.getElementById('load-more-tags');
const TAGS_PAGE = 12;

btnRecommendTags.addEventListener('click', async () => {
    tagsOffset = 0;
    tagsPayload = {
        tags: [...selectedTags],
        ...nepApiFilterPayload(),
        limit: TAGS_PAGE,
        offset: 0,
        style: currentStyle,
        tuning: getUserTuning?.() || null,
    };
    await fetchTagsPage();
});

async function fetchTagsPage() {
    if (!tagsPayload) return;
    if (tagsOffset === 0) {
        resultsTags.innerHTML = '<div class="loading">推荐中...</div>';
        loadMoreTags.style.display = 'none';
    } else {
        tagsPayload.offset = tagsOffset;
    }
    try {
        const r = await fetch('/api/recommend/tags', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(tagsPayload),
        });
        const data = await r.json();
        if (data.error) {
            resultsTags.innerHTML = `<div class="empty">出错了: ${data.error}</div>`;
            return;
        }
        if (tagsOffset === 0) {
            renderResults(resultsTags, data.results, '没找到匹配的番剧');
        } else {
            const tmp = document.createElement('div');
            tmp.innerHTML = data.results.map(renderCardDetailed || (a => `
                <div class="anime-card" data-id="${a.id}">
                    <img class="image" src="${escapeHtml(a.image)}" loading="lazy"
                         onerror="this.style.background='#374151'; this.removeAttribute('src')">
                    <div class="body"><div class="title">${escapeHtml(a.name_cn || a.name || '')}</div></div>
                </div>
            `)).join('');
            while (tmp.firstChild) resultsTags.appendChild(tmp.firstChild);
        }
        tagsOffset += data.results.length;
        loadMoreTags.style.display = data.has_more ? 'block' : 'none';
    } catch (e) {
        if (tagsOffset === 0) resultsTags.innerHTML = `<div class="empty">网络错误</div>`;
    }
}

if (loadMoreTags) {
    loadMoreTags.querySelector('.load-more-btn').addEventListener('click', fetchTagsPage);
}

// ===== BGM 音乐播放器 =====
const bgmToggle = document.getElementById('bgm-toggle');
const bgmPanel = document.getElementById('bgm-panel');
const bgmTrackList = document.getElementById('bgm-track-list');
const bgmPlay = document.getElementById('bgm-play');
const bgmPrev = document.getElementById('bgm-prev');
const bgmNext = document.getElementById('bgm-next');
const bgmVolume = document.getElementById('bgm-volume');
const bgmNowPlaying = document.getElementById('bgm-now-playing');
const bgmUploadBtn = document.getElementById('bgm-upload-btn');
const bgmFileInput = document.getElementById('bgm-file-input');

let bgmTracks = [];
let bgmCurrentIndex = -1;
let bgmAudio = new Audio();
bgmAudio.volume = 0.5;

// 切换面板显示
bgmToggle.addEventListener('click', () => {
    bgmPanel.style.display = bgmPanel.style.display === 'none' ? 'block' : 'none';
    if (bgmPanel.style.display === 'block' && bgmTracks.length === 0) {
        loadBgmList();
    }
});

// 加载BGM列表
async function loadBgmList() {
    try {
        const r = await fetch('/api/bgm/list');
        const data = await r.json();
        bgmTracks = data.tracks || [];
        renderBgmList();
    } catch (e) {
        bgmTrackList.innerHTML = '<div class="empty">加载失败</div>';
    }
}

// 渲染BGM列表
function renderBgmList() {
    if (bgmTracks.length === 0) {
        bgmTrackList.innerHTML = '<div class="empty">暂无音乐，请点击上方"上传音乐"添加</div>';
        return;
    }
    
    bgmTrackList.innerHTML = bgmTracks.map((t, i) => `
        <div class="bgm-track-item ${i === bgmCurrentIndex ? 'active' : ''}" data-idx="${i}">
            <span class="track-icon">${i === bgmCurrentIndex ? '▶' : '♪'}</span>
            <span class="track-name" title="${escapeHtml(t.name)}">${escapeHtml(t.name)}</span>
            <button class="track-delete" data-file="${escapeHtml(t.file)}" title="删除">✕</button>
        </div>
    `).join('');
    
    // 点击播放
    bgmTrackList.querySelectorAll('.bgm-track-item').forEach(item => {
        item.addEventListener('click', (e) => {
            if (e.target.classList.contains('track-delete')) return;
            const idx = parseInt(item.dataset.idx);
            playBgmTrack(idx);
        });
    });
    
    // 删除按钮
    bgmTrackList.querySelectorAll('.track-delete').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const file = btn.dataset.file;
            if (confirm(`确定删除 "${file}"？`)) {
                try {
                    await fetch('/api/bgm/delete', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({file})
                    });
                    await loadBgmList();
                } catch (err) {
                    alert('删除失败');
                }
            }
        });
    });
}

// 播放指定曲目
function playBgmTrack(idx) {
    if (idx < 0 || idx >= bgmTracks.length) return;
    
    bgmCurrentIndex = idx;
    const track = bgmTracks[idx];
    bgmAudio.src = track.url;
    bgmAudio.play();
    bgmPlay.textContent = '⏸';
    bgmToggle.classList.add('playing');
    bgmNowPlaying.textContent = `正在播放: ${track.name}`;
    renderBgmList();
}

// 播放/暂停
bgmPlay.addEventListener('click', () => {
    if (bgmTracks.length === 0) return;
    
    if (bgmCurrentIndex === -1) {
        playBgmTrack(0);
        return;
    }
    
    if (bgmAudio.paused) {
        bgmAudio.play();
        bgmPlay.textContent = '⏸';
        bgmToggle.classList.add('playing');
    } else {
        bgmAudio.pause();
        bgmPlay.textContent = '▶';
        bgmToggle.classList.remove('playing');
    }
});

// 上一首
bgmPrev.addEventListener('click', () => {
    if (bgmTracks.length === 0) return;
    let idx = bgmCurrentIndex - 1;
    if (idx < 0) idx = bgmTracks.length - 1;
    playBgmTrack(idx);
});

// 下一首
bgmNext.addEventListener('click', () => {
    if (bgmTracks.length === 0) return;
    let idx = bgmCurrentIndex + 1;
    if (idx >= bgmTracks.length) idx = 0;
    playBgmTrack(idx);
});

// 音量控制
bgmVolume.addEventListener('input', () => {
    bgmAudio.volume = bgmVolume.value / 100;
});

// 播放结束自动下一首
bgmAudio.addEventListener('ended', () => {
    bgmNext.click();
});

// 上传音乐
bgmUploadBtn.addEventListener('click', () => {
    bgmFileInput.click();
});

bgmFileInput.addEventListener('change', async () => {
    const file = bgmFileInput.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const r = await fetch('/api/bgm/upload', {
            method: 'POST',
            body: formData
        });
        const data = await r.json();
        if (data.error) {
            alert(data.error);
        } else {
            await loadBgmList();
            alert(`已上传: ${data.name}`);
        }
    } catch (e) {
        alert('上传失败');
    }
    
    bgmFileInput.value = '';
});


// ===== 每日推荐 =====
(function() {
    // 初始值：优先从全局风格选择器读取（localStorage），否则 standard
    let dailyStyle = (typeof currentStyle === 'string') ? currentStyle : 'standard';
    let dailyCache = null;

    // 获取用户心理画像（从localStorage）
    function getProfile() {
        try {
            const saved = localStorage.getItem('quizResult');
            if (saved) {
                const result = JSON.parse(saved);
                return result.profile || {};
            }
        } catch(e) {}
        return {};
    }

    // 同步 daily tab 内的风格按钮 UI 到当前风格
    function syncDailyStyleButtons() {
        document.querySelectorAll('.daily-style-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.style === dailyStyle);
        });
    }

    // 加载每日推荐
    async function loadDailyRecommend() {
        const loading = document.getElementById('daily-loading');
        const results = document.getElementById('daily-results');
        const btn = document.getElementById('btn-load-daily');

        if (loading) loading.textContent = '加载中...';
        if (btn) btn.disabled = true;

        try {
            const profile = getProfile();
            // 也带上用户历史（如果存在）和调参
            let history = null;
            try {
                const saved = localStorage.getItem('animeList');
                if (saved) {
                    const list = JSON.parse(saved);
                    if (Array.isArray(list) && list.length > 0) {
                        history = list.map(h => ({id: h.id, rating: h.rating || 0}));
                    }
                }
            } catch (e) {}
            const r = await fetch('/api/daily-recommend', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    profile: profile,
                    style: dailyStyle,
                    history: history,
                    ...nepApiFilterPayload(),
                    tuning: getUserTuning?.() || null,
                })
            });
            const data = await r.json();

            if (data.error) {
                if (loading) loading.textContent = '加载失败: ' + data.error;
                return;
            }

            dailyCache = data;

            // 更新状态
            const dateEl = document.getElementById('daily-date');
            const countEl = document.getElementById('daily-count');
            if (dateEl) dateEl.textContent = '📅 ' + data.date;
            if (countEl) countEl.textContent = '共 ' + data.total + ' 部';

            // 渲染结果
            const allResults = [
                ...(data.recommendations?.underrated || []),
                ...(data.recommendations?.vintage || []),
                ...(data.recommendations?.blind_spot || [])
            ];

            if (loading) loading.style.display = 'none';
            if (results) {
                results.style.display = 'grid';
                renderResults(results, allResults, '暂无推荐');
            }
        } catch(e) {
            if (loading) loading.textContent = '加载失败，请重试';
            console.error('每日推荐加载失败:', e);
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    // 初始化事件
    document.addEventListener('DOMContentLoaded', function() {
        // 同步 daily tab 内的风格按钮（反映全局选择）
        syncDailyStyleButtons();

        // 加载按钮
        const btn = document.getElementById('btn-load-daily');
        if (btn) {
            btn.addEventListener('click', loadDailyRecommend);
        }

        // 风格选择按钮（保留 tab 内的旧入口，已与全局同步）
        document.querySelectorAll('.daily-style-btn').forEach(b => {
            b.addEventListener('click', function() {
                dailyStyle = this.dataset.style;
                syncDailyStyleButtons();
                // 同步给全局选择器
                if (typeof switchStyle === 'function') {
                    switchStyle(dailyStyle);
                }
                // 如果已有缓存，重新加载
                if (dailyCache) {
                    loadDailyRecommend();
                }
            });
        });

        // 监听全局风格切换
        document.addEventListener('recommendStyleChanged', function(e) {
            const newStyle = e.detail?.style;
            if (newStyle && newStyle !== dailyStyle) {
                dailyStyle = newStyle;
                syncDailyStyleButtons();
                if (dailyCache) {
                    loadDailyRecommend();
                }
            }
        });

        // 每日推荐导出
        const dailyExportBtn = document.getElementById('btn-daily-export');
        const dailyExportMenu = document.getElementById('daily-export-menu');
        if (dailyExportBtn && dailyExportMenu) {
            dailyExportBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                dailyExportMenu.style.display = dailyExportMenu.style.display === 'block' ? 'none' : 'block';
            });
            document.addEventListener('click', () => {
                dailyExportMenu.style.display = 'none';
            });
            dailyExportMenu.querySelectorAll('button[data-fmt]').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    dailyExportMenu.style.display = 'none';
                    if (!dailyCache) {
                        alert('请先加载每日推荐');
                        return;
                    }
                    const allResults = [
                        ...(dailyCache.recommendations?.underrated || []),
                        ...(dailyCache.recommendations?.vintage || []),
                        ...(dailyCache.recommendations?.blind_spot || [])
                    ];
                    if (allResults.length === 0) {
                        alert('没有可导出的推荐结果');
                        return;
                    }
                    await exportAnimeList(allResults, btn.dataset.fmt, btn);
                });
            });
        }
    });
})();

// ===== 通用导出函数 =====
async function exportAnimeList(list, fmt, btnEl) {
    const origText = btnEl ? btnEl.textContent : '';
    if (btnEl) { btnEl.textContent = '导出中...'; btnEl.disabled = true; }
    try {
        const r = await fetch('/api/export', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({list: list, format: fmt}),
        });
        if (!r.ok) {
            const err = await r.json().catch(() => ({}));
            alert('导出失败: ' + (err.error || r.status));
            return;
        }
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const cd = r.headers.get('Content-Disposition') || '';
        const match = cd.match(/filename\*?=(?:UTF-8''|"?)(.+?)"?$/);
        a.download = match ? decodeURIComponent(match[1]) : `export.${fmt}`;
        a.click();
        URL.revokeObjectURL(url);
    } catch (err) {
        alert('导出失败: ' + err.message);
    } finally {
        if (btnEl) { btnEl.textContent = origText; btnEl.disabled = false; }
    }
}
