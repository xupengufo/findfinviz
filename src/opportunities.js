import { state, API_BASE } from './state.js';
import { translations, onLanguageChange } from './i18n.js';
import { 
    escapeHtml, 
    parseChange, 
    formatMarketCap, 
    filterByMarketCap, 
    sortData, 
    getBadgesHtml, 
    updateTimestamp 
} from './utils.js';
import { openModal } from './modal.js';

export async function loadOpportunities(force = false) {
    if (state.tabLoaded.opportunities && !force) return;
    
    const grid = document.getElementById('opps-grid');
    if (!grid) return;
    
    // Render Skeletons while loading
    grid.innerHTML = `
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
    `;

    try {
        const res = await fetch(`${API_BASE}/api/opportunities?signal=${state.activeSignal}`);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const payload = await res.json();
        updateTimestamp(payload);
        state.currentOppsList = payload.data || [];
        
        renderOpportunities(state.currentOppsList);
        state.tabLoaded.opportunities = true;
    } catch (error) {
        console.error('Failed to load opportunities:', error);
        grid.innerHTML = `<div class="error-msg"><i data-lucide="alert-triangle"></i> ${translations[state.activeLang].err_opps}</div>`;
        if (window.lucide) window.lucide.createIcons();
    }
}

export function renderOpportunities(list) {
    const grid = document.getElementById('opps-grid');
    if (!grid) return;
    grid.innerHTML = '';
    
    const filteredList = filterByMarketCap(list, state.activeMcapFilter);
    if (!filteredList || filteredList.length === 0) {
        grid.innerHTML = `<div class="no-data"><i data-lucide="info"></i> ${translations[state.activeLang].no_opps}</div>`;
        if (window.lucide) window.lucide.createIcons();
        return;
    }
    
    const sortedList = sortData(filteredList, state.activeSortField, state.activeSortDirection);

    sortedList.forEach(item => {
        const card = document.createElement('div');
        card.className = 'opp-card';

        // P0-3: Compute ADTV from raw FinViz fields (Avg Volume × Price) + low-liquidity flag
        const avgVol = parseFloat(item['Average Volume'] || item['Avg Volume'] || 0);
        const priceNum = parseFloat(item['Price'] || 0);
        const adtvVal = (avgVol > 0 && priceNum > 0) ? avgVol * priceNum : 0;
        const adtvText = adtvVal > 0 ? formatMarketCap(adtvVal) : '-';
        const isLowLiquidity = adtvVal > 0 && adtvVal < 5_000_000;
        if (isLowLiquidity) card.classList.add('card-low-liquidity');

        const { formatted: changeText, isBullish } = parseChange(item['Change']);
        const changeClass = isBullish ? 'bullish' : 'bearish';

        const badgesHtml = getBadgesHtml(item);
        card.innerHTML = `
            <div class="card-header">
                <span class="card-ticker">${escapeHtml(item['Ticker']) || '-'}</span>
                <span class="card-change ${changeClass}">${changeText}</span>
            </div>
            <div class="card-company">${escapeHtml(item['Company']) || '-'}</div>
            ${badgesHtml}
            <div class="card-footer">
                <div class="card-footer-item">
                    <span class="item-label">${state.activeLang === 'zh' ? '行业' : 'Industry'}</span>
                    <span class="item-value" title="${escapeHtml(item['Industry']) || '-'}">${escapeHtml(item['Industry']) || '-'}</span>
                </div>
                <div class="card-footer-item">
                    <span class="item-label">${state.activeLang === 'zh' ? '市值' : 'Market Cap'}</span>
                    <span class="item-value">${formatMarketCap(item['Market Cap'])}</span>
                </div>
                <div class="card-footer-item">
                    <span class="item-label">${state.activeLang === 'zh' ? '最新价' : 'Price'}</span>
                    <span class="item-value">${escapeHtml(item['Price']) || '-'}</span>
                </div>
                <div class="card-footer-item">
                    <span class="item-label">${state.activeLang === 'zh' ? '日均成交额' : 'ADTV'}</span>
                    <span class="item-value ${isLowLiquidity ? 'text-warning' : ''}">$${adtvText}</span>
                </div>
            </div>
        `;

        // Card click loads detail sheet
        card.addEventListener('click', () => {
            openModal(item['Ticker']);
        });

        grid.appendChild(card);
    });

    if (window.lucide) window.lucide.createIcons();
}

onLanguageChange(() => {
    if (state.tabLoaded.opportunities) {
        renderOpportunities(state.currentOppsList);
    }
});
