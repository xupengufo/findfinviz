import { state, API_BASE } from './state.js';
import { translations, onLanguageChange } from './i18n.js';
import { escapeHtml, formatNumber } from './utils.js';
import { openModal } from './modal.js';
import { loadWsbCalendar } from './wsb-calendar.js';

export async function loadReddit(force = false) {
    // Trigger calendar loading in parallel
    loadWsbCalendar(force);

    if (state.tabLoaded.reddit && !force) return;

    const tbody = document.getElementById('reddit-table-body');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">${translations[state.activeLang].loading_reddit}</td></tr>`;

    try {
        const res = await fetch(`${API_BASE}/api/reddit`);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const payload = await res.json();
        state.currentRedditList = payload.data || [];

        renderReddit(state.currentRedditList);
        state.tabLoaded.reddit = true;
    } catch (error) {
        console.error('Failed to load Reddit sentiment:', error);
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--negative);">${translations[state.activeLang].err_reddit}</td></tr>`;
    }
}

export function renderReddit(list) {
    const tbody = document.getElementById('reddit-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!list || list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center;">${state.activeLang === 'zh' ? '暂无数据。' : 'No data found.'}</td></tr>`;
        return;
    }

    // Slice to show top 50
    const displayList = list.slice(0, 50);

    displayList.forEach(item => {
        const tr = document.createElement('tr');
        
        const rank = item['rank'] || '-';
        const ticker = item['ticker'] || '-';
        const name = item['name'] || '-';
        const mentions = item['mentions'] || 0;
        const upvotes = item['upvotes'] || 0;
        const rank24h = item['rank_24h_ago'];

        let trendText = '-';
        let trendClass = 'trend-neutral';
        let trendIcon = 'minus';
        
        if (rank24h !== undefined && rank24h !== null && rank24h !== '') {
            const rToday = parseInt(rank);
            const r24h = parseInt(rank24h);
            if (!isNaN(rToday) && !isNaN(r24h)) {
                const diff = r24h - rToday; // if today is 1 and 24h ago was 4, diff is +3 (climbed)
                if (diff > 0) {
                    trendText = `+${diff}`;
                    trendClass = 'trend-up';
                    trendIcon = 'arrow-up';
                } else if (diff < 0) {
                    trendText = `${diff}`;
                    trendClass = 'trend-down';
                    trendIcon = 'arrow-down';
                }
            }
        }

        tr.innerHTML = `
            <td class="table-rank">${escapeHtml(rank)}</td>
            <td class="table-ticker">${escapeHtml(ticker)}</td>
            <td>${escapeHtml(name)}</td>
            <td>${formatNumber(mentions)}</td>
            <td>${formatNumber(upvotes)}</td>
            <td class="${trendClass}">
                <span class="trend-badge">
                    <i data-lucide="${trendIcon}" style="width:12px; height:12px; display:inline-block; vertical-align:middle; margin-right:2px;"></i>
                    ${trendText}
                </span>
            </td>
        `;

        // Clicking rows opens ticker details modal
        tr.addEventListener('click', () => {
            openModal(ticker);
        });
        tbody.appendChild(tr);
    });

    if (window.lucide) window.lucide.createIcons();
}

onLanguageChange(() => {
    if (state.tabLoaded.reddit) {
        renderReddit(state.currentRedditList);
    }
});
