/* ============================================================
   animematch-bg.js
   背景图选择器：列缩略图、切换、上传、删除、樱花飘落
   ============================================================ */

(function () {
    'use strict';

    const $ = (id) => document.getElementById(id);

    // ---- 元素（可能不存在：quiz / mylist 页不一定有背景按钮） ----
    const bgPicker = $('bg-picker');
    if (!bgPicker) {
        // 没有背景选择器也要加载背景图
        loadCurrentBackground();
        spawnSakura();
        return;
    }

    const bgToggle = $('bg-toggle');
    const bgPanel = $('bg-panel');
    const bgGrid = $('bg-grid');
    const bgUploadBtn = $('bg-upload-btn');
    const bgFileInput = $('bg-file-input');
    const bgClearBtn = $('bg-clear');
    const bgImage = $('bg-image');

    // ---- 樱花飘落 ----
    function spawnSakura() {
        const container = $('sakura-container');
        if (!container) return;
        const count = window.innerWidth < 768 ? 8 : 16;
        for (let i = 0; i < count; i++) {
            const petal = document.createElement('div');
            petal.className = 'sakura';
            petal.style.left = Math.random() * 100 + 'vw';
            petal.style.animationDuration = (8 + Math.random() * 8) + 's';
            petal.style.animationDelay = (Math.random() * 10) + 's';
            petal.style.opacity = (0.4 + Math.random() * 0.5).toFixed(2);
            petal.style.transform = `scale(${0.6 + Math.random() * 0.7})`;
            container.appendChild(petal);
        }
    }

    // ---- 加载当前背景图 ----
    async function loadCurrentBackground() {
        try {
            const r = await fetch('/api/background/current');
            const data = await r.json();
            if (data.url && bgImage) {
                bgImage.style.backgroundImage = `url(${data.url})`;
                bgImage.classList.add('show');
            }
        } catch (e) {
            console.warn('加载背景失败:', e);
        }
    }

    // ---- 加载列表 ----
    async function loadBackgroundList() {
        try {
            const r = await fetch('/api/background/list');
            const data = await r.json();
            renderGrid(data.backgrounds || [], data.selected);
        } catch (e) {
            bgGrid.innerHTML = '<div class="bg-empty">加载失败</div>';
        }
    }

    function renderGrid(items, selected) {
        if (!items.length) {
            bgGrid.innerHTML = '<div class="bg-empty">还没有背景图<br>点上面"上传"添加一张<br>或把图片放到<br><code>static/backgrounds/</code> 文件夹</div>';
            return;
        }
        bgGrid.innerHTML = '';
        for (const bg of items) {
            const div = document.createElement('div');
            div.className = 'bg-thumb' + (bg.file === selected ? ' active' : '');
            div.title = bg.name;
            div.dataset.file = bg.file;
            div.innerHTML = `
                <img src="${bg.url}" alt="${bg.name}" loading="lazy">
                <div class="bg-name">${bg.name}</div>
                <button class="bg-del" title="删除">✕</button>
            `;
            div.addEventListener('click', (e) => {
                if (e.target.classList.contains('bg-del')) return;
                selectBackground(bg.file);
            });
            div.querySelector('.bg-del').addEventListener('click', (e) => {
                e.stopPropagation();
                if (confirm(`删除背景「${bg.name}」？`)) {
                    deleteBackground(bg.file);
                }
            });
            bgGrid.appendChild(div);
        }
    }

    // ---- 选择背景 ----
    async function selectBackground(file) {
        try {
            const r = await fetch('/api/background/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file }),
            });
            if (!r.ok) {
                const err = await r.json().catch(() => ({}));
                alert('切换失败：' + (err.error || r.status));
                return;
            }
            // 立即更新显示
            if (bgImage) {
                if (file) {
                    bgImage.style.backgroundImage = `url(/static/backgrounds/${file})`;
                    bgImage.classList.add('show');
                } else {
                    bgImage.style.backgroundImage = '';
                    bgImage.classList.remove('show');
                }
            }
            // 更新高亮
            bgGrid.querySelectorAll('.bg-thumb').forEach(el => {
                el.classList.toggle('active', el.dataset.file === file);
            });
        } catch (e) {
            alert('切换失败：' + e.message);
        }
    }

    // ---- 删除背景 ----
    async function deleteBackground(file) {
        try {
            const r = await fetch('/api/background/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file }),
            });
            if (!r.ok) {
                const err = await r.json().catch(() => ({}));
                alert('删除失败：' + (err.error || r.status));
                return;
            }
            // 刷新列表
            await loadBackgroundList();
            // 如果删的是当前选中的，清除背景图
            if (bgImage) {
                bgImage.style.backgroundImage = '';
                bgImage.classList.remove('show');
            }
        } catch (e) {
            alert('删除失败：' + e.message);
        }
    }

    // ---- 上传 ----
    bgUploadBtn.addEventListener('click', () => bgFileInput.click());
    bgFileInput.addEventListener('change', async () => {
        if (!bgFileInput.files[0]) return;
        const fd = new FormData();
        fd.append('file', bgFileInput.files[0]);
        bgUploadBtn.disabled = true;
        bgUploadBtn.textContent = '上传中…';
        try {
            const r = await fetch('/api/background/upload', { method: 'POST', body: fd });
            if (!r.ok) {
                const err = await r.json().catch(() => ({}));
                alert('上传失败：' + (err.error || r.status));
                return;
            }
            const data = await r.json();
            // 刷新列表
            await loadBackgroundList();
            // 自动选中新上传的
            await selectBackground(data.file);
        } catch (e) {
            alert('上传失败：' + e.message);
        } finally {
            bgUploadBtn.disabled = false;
            bgUploadBtn.textContent = '上传';
            bgFileInput.value = '';
        }
    });

    // ---- 用默认渐变 ----
    bgClearBtn.addEventListener('click', () => selectBackground(null));

    // ---- 开关面板 ----
    bgToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        const show = !bgPanel.classList.contains('show');
        bgPanel.classList.toggle('show', show);
        bgToggle.classList.toggle('active', show);
        if (show) loadBackgroundList();
    });
    document.addEventListener('click', (e) => {
        if (!bgPicker.contains(e.target) && bgPanel.classList.contains('show')) {
            bgPanel.classList.remove('show');
            bgToggle.classList.remove('active');
        }
    });

    // ---- 启动 ----
    loadCurrentBackground();
    loadBackgroundList();
    spawnSakura();
})();
