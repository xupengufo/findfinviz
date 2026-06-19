import { state, API_BASE } from './state.js';
import { translations, onLanguageChange } from './i18n.js';
import { escapeHtml, formatNumber, updateTimestamp } from './utils.js';
import { openModal } from './modal.js';

export async function loadInsider(force = false) {
    if (state.tabLoaded.insider && !force) return;

    const tbody = document.getElementById('insider-table-body');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted);">${translations[state.activeLang].loading_insider}</td></tr>`;

    try {
        const res = await fetch(`${API_BASE}/api/insiders?option=${encodeURIComponent(state.activeInsiderOption)}`);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const payload = await res.json();
        updateTimestamp(payload);
        state.currentInsiderList = payload.data || [];
        renderInsider(state.currentInsiderList);
        state.tabLoaded.insider = true;
    } catch (error) {
        console.error('Failed to load insider:', error);
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--bearish);">${translations[state.activeLang].err_insider}</td></tr>`;
    }
}

export function renderInsider(list) {
    const tbody = document.getElementById('insider-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!list || list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center;">${translations[state.activeLang].no_insider}</td></tr>`;
        return;
    }

    list.forEach(item => {
        const tr = document.createElement('tr');
        const rawVal = item['Value ($)'] || 0;
        
        // Format transaction Type (Buy / Sell)
        const txnLower = (item['Transaction'] || '').toLowerCase();
        const isBuy = txnLower.includes('buy') || txnLower.includes('exercise') || txnLower.includes('purchase');
        const txnText = isBuy ? translations[state.activeLang].txn_buy : translations[state.activeLang].txn_sell;
        const txnClass = isBuy ? 'txn-buy' : 'txn-sell';

        tr.innerHTML = `
            <td class="table-ticker">${escapeHtml(item['Ticker']) || '-'}</td>
            <td title="${escapeHtml(item['Relationship']) || '-'}">${escapeHtml(item['Relationship']) || '-'}</td>
            <td>${escapeHtml(item['Date']) || '-'}</td>
            <td class="${txnClass}">${txnText}</td>
            <td>${formatNumber(item['Cost'])}</td>
            <td>${formatNumber(item['#Shares'])}</td>
            <td>$${formatNumber(rawVal)}</td>
            <td>${formatNumber(item['#Shares Total'])}</td>
            <td>
                <a href="https://finviz.com/${escapeHtml(item['SEC Form 4 Link'])}" target="_blank" class="sec-link">
                    Form 4 <i data-lucide="external-link"></i>
                </a>
            </td>
        `;

        // Clicking rows opens ticker details modal
        tr.addEventListener('click', (e) => {
            if (e.target.tagName !== 'A' && !e.target.closest('a')) {
                openModal(item['Ticker']);
            }
        });
        tbody.appendChild(tr);
    });

    if (window.lucide) window.lucide.createIcons();
}

onLanguageChange(() => {
    if (state.tabLoaded.insider) {
        renderInsider(state.currentInsiderList);
    }
});
