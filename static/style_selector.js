// ================================================================
// 全局推荐风格选择器（左上角下拉菜单）
// 由 index.html 和 quiz.html 共享加载
// 使用 localStorage 持久化，以便跨页面生效
// ================================================================

const STYLE_STORAGE_KEY = 'nep_recommend_style';

const styleConfig = {
    explore:      { icon: '🔭', name: '探索型' },
    standard:     { icon: '⚖️', name: '标准型' },
    conservative: { icon: '🎯', name: '保守型' }
};

// 从 localStorage 读取上次选择，默认 standard
let currentStyle = (() => {
    try {
        const saved = localStorage.getItem(STYLE_STORAGE_KEY);
        if (saved && styleConfig[saved]) return saved;
    } catch (e) { /* 忽略 localStorage 异常 */ }
    return 'standard';
})();

// 切换下拉菜单显示/隐藏
function toggleStyleMenu() {
    const dropdown = document.getElementById('style-dropdown');
    const menu = document.getElementById('style-menu');
    if (!dropdown || !menu) return;
    const willOpen = menu.style.display === 'none';
    menu.style.display = willOpen ? 'block' : 'none';
    dropdown.classList.toggle('open', willOpen);
}

// 点击其他地方关闭下拉菜单 + 委托处理菜单项点击
document.addEventListener('click', function(e) {
    const dropdown = document.getElementById('style-dropdown');
    if (!dropdown) return;

    // 点击菜单项 → 切换风格
    const item = e.target.closest('.style-menu-item');
    if (item && dropdown.contains(item)) {
        const style = item.dataset.style;
        if (style) {
            e.stopPropagation();
            switchStyle(style);
            return;
        }
    }

    // 点击其他区域 → 关闭下拉
    if (!dropdown.contains(e.target)) {
        const menu = document.getElementById('style-menu');
        if (menu) menu.style.display = 'none';
        dropdown.classList.remove('open');
    }
});

// 更新左上角指示器（图标 + 名称）
function updateStyleIndicator() {
    const config = styleConfig[currentStyle];
    const icon = document.getElementById('style-icon');
    const name = document.getElementById('style-name');
    if (icon) icon.textContent = config.icon;
    if (name) name.textContent = config.name;
}

// 更新下拉菜单中的选中状态
function updateStyleMenuActive(style) {
    const items = document.querySelectorAll('.style-menu-item');
    const styleIndex = { explore: 0, standard: 1, conservative: 2 };
    items.forEach((item, i) => item.classList.remove('active'));
    if (items[styleIndex[style]]) items[styleIndex[style]].classList.add('active');
}

// 切换推荐风格（保存到 localStorage）
function switchStyle(style) {
    if (!styleConfig[style]) return;
    currentStyle = style;
    try { localStorage.setItem(STYLE_STORAGE_KEY, style); } catch (e) {}

    updateStyleIndicator();
    updateStyleMenuActive(style);

    const menu = document.getElementById('style-menu');
    if (menu) menu.style.display = 'none';
    const dropdown = document.getElementById('style-dropdown');
    if (dropdown) dropdown.classList.remove('open');

    // 通知业务侧：推荐风格已变更
    document.dispatchEvent(new CustomEvent('recommendStyleChanged', { detail: { style } }));

    // quiz 页面：重置测试状态（如果有的话）
    if (typeof onStyleChangedForQuiz === 'function') {
        onStyleChangedForQuiz(style);
    }
}

// 初始化：在 DOMContentLoaded 时绑定下拉按钮的点击
document.addEventListener('DOMContentLoaded', function() {
    const toggle = document.getElementById('style-toggle');
    if (toggle) toggle.addEventListener('click', toggleStyleMenu);
    updateStyleIndicator();
    updateStyleMenuActive(currentStyle);
});
