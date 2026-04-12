import { state } from './state.js';

const STORAGE_KEY = 'cocosearch-theme';
export const THEME_CHANGE_EVENT = 'cocosearch:theme-change';

export function getCurrentTheme() {
    return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    state.currentTheme = theme;

    // Swap Prism syntax theme
    const dark = document.getElementById('prismThemeDark');
    const light = document.getElementById('prismThemeLight');
    if (dark) dark.disabled = (theme === 'light');
    if (light) light.disabled = (theme !== 'light');

    // Update toggle button label (action-oriented: shows what clicking will do)
    const btn = document.getElementById('themeToggleBtn');
    if (btn) btn.textContent = (theme === 'dark') ? '[LIGHT]' : '[DARK]';

    // Notify listeners (charts, etc.) so they can re-read CSS vars
    document.dispatchEvent(new CustomEvent(THEME_CHANGE_EVENT, { detail: { theme } }));
}

export function setTheme(theme) {
    try {
        localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) { /* ignore quota / private mode */ }
    applyTheme(theme);
}

export function toggleTheme() {
    setTheme(getCurrentTheme() === 'dark' ? 'light' : 'dark');
}

export function initTheme() {
    // FOUC script in <head> already set data-theme; sync state + button label
    // and wire interactions. Do NOT touch localStorage here — keeping the
    // system default implicit until the user explicitly chooses preserves
    // the "follow OS" behavior.
    applyTheme(getCurrentTheme());

    const btn = document.getElementById('themeToggleBtn');
    if (btn) btn.addEventListener('click', toggleTheme);

    // Follow OS preference changes when the user has not made an explicit choice.
    try {
        const mq = window.matchMedia('(prefers-color-scheme: light)');
        const handler = (e) => {
            if (!localStorage.getItem(STORAGE_KEY)) {
                applyTheme(e.matches ? 'light' : 'dark');
            }
        };
        if (mq.addEventListener) {
            mq.addEventListener('change', handler);
        } else if (mq.addListener) {
            // Safari < 14
            mq.addListener(handler);
        }
    } catch (e) { /* matchMedia unavailable — ignore */ }
}
