// ========================================
// weights.js - 调参 tab（v3.2 三档按钮）
// 全部 15 因子平铺，每个因子三个按钮：低 / 中 / 高
// ========================================

// 全部 15 因子配置
const FACTORS = [
    { key: 'tag',            label: '标签相似度',   tier: 'high', defaultW: 0.10 },
    { key: 'rating',         label: '评分',         tier: 'mid',  defaultW: 0.08 },
    { key: 'popularity',     label: '人气',         tier: 'mid',  defaultW: 0.04 },
    { key: 'favourites',     label: '收藏数',       tier: 'mid',  defaultW: 0.06 },
    { key: 'consensus',      label: '综合质量',     tier: 'mid',  defaultW: 0.12 },
    { key: 'history',        label: '历史因素',     tier: 'high', defaultW: 0.40 },
    { key: 'studio',         label: '制作公司',     tier: 'high', defaultW: 0.03 },
    { key: 'va',             label: '声优',         tier: 'high', defaultW: 0.02 },
    { key: 'staff',          label: 'Staff',        tier: 'high', defaultW: 0.02 },
    { key: 'era',            label: '年代匹配',     tier: 'low',  defaultW: 0.02 },
    { key: 'format',         label: '格式',         tier: 'low',  defaultW: 0.02 },
    { key: 'eps',            label: '集数偏好',     tier: 'low',  defaultW: 0.01 },
    { key: 'duration',       label: '时长偏好',     tier: 'low',  defaultW: 0.01 },
    { key: 'recency',        label: '新番优先',     tier: 'low',  defaultW: 0.01 },
    { key: 'quality_signal', label: '标签丰富度',   tier: 'low',  defaultW: 0.01 },
];

// 档位配置：gain 值 → 显示
const LEVELS = [
    { gain: -1, label: '低', cls: 'level-low'  },
    { gain:  0, label: '中', cls: 'level-mid'  },
    { gain:  1, label: '高', cls: 'level-high' },
];

const TIER_INFO = {
    low:  { icon: '🟢', label: '低档', range: '×0.5 ~ ×1.5' },
    mid:  { icon: '🟡', label: '中档', range: '×0.8 ~ ×1.2' },
    high: { icon: '🔴', label: '高档', range: '×0.3 ~ ×3.0' },
};

const TUNING_STORAGE_KEY = 'nep_user_tuning';

function loadTuning() {
    try {
        const raw = localStorage.getItem(TUNING_STORAGE_KEY);
        if (raw) return JSON.parse(raw);
    } catch (e) {}
    return {};
}

function saveTuning(tuning) {
    try { localStorage.setItem(TUNING_STORAGE_KEY, JSON.stringify(tuning)); } catch (e) {}
}

let currentTuning = loadTuning();

function getActiveCount() {
    return Object.values(currentTuning).filter(v => v !== 0 && v !== undefined).length;
}

function renderTuningUI() {
    const container = document.getElementById('weight-sliders');
    if (!container) return;

    const activeCount = getActiveCount();

    let html = `
        <div class="tuning-intro">
            <p>每个因子可选 <strong>低</strong> / <strong>中</strong>（默认）/ <strong>高</strong> 三档。
            建议只调 2-3 个你最在意的因子。</p>
        </div>
        <div class="tuning-status-bar">
            <span class="status-count ${activeCount > 3 ? 'warn' : ''}">${activeCount > 0 ? '已调整 ' + activeCount + ' 项' : '全部默认'}</span>
            ${activeCount > 3 ? '<span class="status-warn">⚠ 调整过多，结果可能不稳定</span>' : ''}
        </div>
    `;

    // 表头
    html += `<div class="tuning-table">`;
    html += `<div class="tuning-header">
        <span class="tuning-col-name">因子</span>
        <span class="tuning-col-w">默认权重</span>
        <span class="tuning-col-tier">档位</span>
        <span class="tuning-col-btns">偏好</span>
    </div>`;

    for (const f of FACTORS) {
        const gain = currentTuning[f.key] || 0;
        const tier = TIER_INFO[f.tier];

        html += `<div class="tuning-row ${gain !== 0 ? 'active' : ''}" data-key="${f.key}">`;
        html += `<span class="tuning-col-name">${f.label}</span>`;
        html += `<span class="tuning-col-w">${(f.defaultW * 100).toFixed(0)}%</span>`;
        html += `<span class="tuning-col-tier"><span class="tier-dot ${f.tier}">${tier.icon}</span></span>`;
        html += `<span class="tuning-col-btns">`;

        for (const lv of LEVELS) {
            const isActive = gain === lv.gain;
            html += `<button class="level-btn ${lv.cls} ${isActive ? 'selected' : ''}"
                        data-key="${f.key}" data-gain="${lv.gain}">${lv.label}</button>`;
        }

        html += `</span></div>`;
    }
    html += `</div>`;

    container.innerHTML = html;

    // 绑定按钮事件
    container.querySelectorAll('.level-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const key = btn.dataset.key;
            const gain = parseInt(btn.dataset.gain);

            if (gain === 0) {
                delete currentTuning[key];
            } else {
                currentTuning[key] = gain;
            }

            // 更新按钮状态
            const row = btn.closest('.tuning-row');
            row.querySelectorAll('.level-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            row.classList.toggle('active', gain !== 0);

            updateStatusBar();
        });
    });

    updateStatusBar();
}

function updateStatusBar() {
    const bar = document.querySelector('.tuning-status-bar');
    if (!bar) return;
    const count = getActiveCount();
    bar.innerHTML = `
        <span class="status-count ${count > 3 ? 'warn' : ''}">${count > 0 ? '已调整 ' + count + ' 项' : '全部默认'}</span>
        ${count > 3 ? '<span class="status-warn">⚠ 调整过多，结果可能不稳定</span>' : ''}
    `;
}

function getUserTuning() {
    return Object.keys(currentTuning).length > 0 ? currentTuning : null;
}

const btnReset = document.getElementById('btn-reset-weights');
if (btnReset) {
    btnReset.addEventListener('click', () => {
        currentTuning = {};
        saveTuning(currentTuning);
        renderTuningUI();
    });
}

const btnSave = document.getElementById('btn-save-weights');
if (btnSave) {
    btnSave.addEventListener('click', () => {
        saveTuning(currentTuning);
        const bar = document.querySelector('.tuning-status-bar');
        if (bar) {
            const count = getActiveCount();
            bar.innerHTML = `<span class="status-count">✓ 已保存${count > 0 ? '（' + count + ' 项）' : ''}</span>`;
        }
    });
}

window.getUserTuning = getUserTuning;
renderTuningUI();
