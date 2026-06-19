import { state, API_BASE } from './state.js';
import { translations, sectorZhMapping, onLanguageChange } from './i18n.js';
import { escapeHtml, parseChange, formatMarketCap, getSectorZhName, updateTimestamp } from './utils.js';
import { openModal } from './modal.js';

export async function loadSectors(force = false) {
    if (state.tabLoaded.sectors && !force) return;

    const grid = document.getElementById('sectors-grid');
    if (!grid) return;
    grid.innerHTML = `
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
    `;

    try {
        const res = await fetch(`${API_BASE}/api/sectors`);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const payload = await res.json();
        updateTimestamp(payload);
        const list = payload.data || [];

        // Sort sectors by daily change descending (highest change/strongest first)
        const sortedList = [...list].sort((a, b) => {
            const valA = a['Change'] !== undefined && a['Change'] !== null ? parseFloat(a['Change']) : -999;
            const valB = b['Change'] !== undefined && b['Change'] !== null ? parseFloat(b['Change']) : -999;
            return valB - valA;
        });

        // Calculate summary statistics
        let strongest = null;
        let weakest = null;
        let upCount = 0;
        let downCount = 0;
        
        sortedList.forEach(item => {
            const changeVal = parseFloat(item['Change']) || 0;
            if (changeVal >= 0) {
                upCount++;
            } else {
                downCount++;
            }
            
            if (!strongest || changeVal > parseFloat(strongest['Change'])) {
                strongest = item;
            }
            if (!weakest || changeVal < parseFloat(weakest['Change'])) {
                weakest = item;
            }
        });

        const getSectorName = (name) => {
            if (state.activeLang === 'zh') {
                return sectorZhMapping[name] || name;
            }
            return name;
        };

        const summaryContainer = document.getElementById('sectors-summary');
        if (summaryContainer && strongest && weakest) {
            const strongName = getSectorName(strongest['Name']);
            const strongChange = parseChange(strongest['Change']).formatted;
            
            const weakName = getSectorName(weakest['Name']);
            const weakChange = parseChange(weakest['Change']).formatted;
            
            const totalSectors = sortedList.length;
            const ratioText = state.activeLang === 'zh' 
                ? `${upCount} 板块上涨 / ${downCount} 下跌` 
                : `${upCount} Up / ${downCount} Down`;

            summaryContainer.innerHTML = `
                <div class="summary-chip">
                    <span class="summary-chip-title">${state.activeLang === 'zh' ? '今日最强板块' : 'Top Performing Sector'}</span>
                    <span class="summary-chip-val" style="color: var(--positive);">${strongName}</span>
                    <span class="summary-chip-sub">${strongChange}</span>
                </div>
                <div class="summary-chip">
                    <span class="summary-chip-title">${state.activeLang === 'zh' ? '今日最弱板块' : 'Worst Performing Sector'}</span>
                    <span class="summary-chip-val" style="color: var(--negative);">${weakName}</span>
                    <span class="summary-chip-sub">${weakChange}</span>
                </div>
                <div class="summary-chip">
                    <span class="summary-chip-title">${state.activeLang === 'zh' ? '板块上涨下跌比' : 'Market Breadth'}</span>
                    <span class="summary-chip-val">${ratioText}</span>
                    <span class="summary-chip-sub">${state.activeLang === 'zh' ? `共 ${totalSectors} 个板块` : `Total ${totalSectors} Sectors`}</span>
                </div>
            `;
        }

        state.currentSectorsList = sortedList;
        renderSectors(state.currentSectorsList);
        state.tabLoaded.sectors = true;
    } catch (error) {
        console.error('Failed to load sectors:', error);
        grid.innerHTML = `<div class="error-msg"><i data-lucide="alert-triangle"></i> ${translations[state.activeLang].err_sectors}</div>`;
        if (window.lucide) window.lucide.createIcons();
    }
}

export function renderSectors(list) {
    const grid = document.getElementById('sectors-grid');
    if (!grid) return;
    grid.innerHTML = '';

    if (!list || list.length === 0) return;

    const getSectorName = (name) => {
        if (state.activeLang === 'zh') {
            return sectorZhMapping[name] || name;
        }
        return name;
    };

    list.forEach(item => {
        const card = document.createElement('div');
        card.className = 'sector-card';
        card.addEventListener('click', () => {
            openSectorModal(item['Name']);
        });

        const { formatted: changeText, isBullish } = parseChange(item['Change']);
        const barColor = isBullish ? 'bullish' : 'bearish';
        const textValColor = isBullish ? 'positive' : 'negative';

        // Map sector names if Chinese is active
        const sectorName = getSectorName(item['Name']);

        // Calculate bidirectional width based on max range of ±3%
        let changeNum = parseFloat(item['Change']);
        if (isNaN(changeNum)) changeNum = 0;
        
        const changePct = changeNum * 100;
        const maxPct = 3.0; // limit scale at ±3%
        const barWidthPct = Math.min(Math.abs(changePct) / maxPct, 1.0) * 50; // max 50% of the bar width
        
        let barStyle = '';
        if (isBullish) {
            barStyle = `left: 50%; width: ${barWidthPct}%;`;
        } else {
            barStyle = `left: ${50 - barWidthPct}%; width: ${barWidthPct}%;`;
        }

        card.innerHTML = `
            <div class="sector-name">${escapeHtml(sectorName)}</div>
            <div class="sector-metric">
                <span class="item-label">${translations[state.activeLang].metric_stocks}</span>
                <span class="item-value">${item['Stocks'] || '-'}</span>
            </div>
            <div class="sector-metric">
                <span class="item-label">${translations[state.activeLang].metric_mcap}</span>
                <span class="item-value">${formatMarketCap(item['Market Cap'])}</span>
            </div>
            <div class="sector-metric">
                <span class="item-label">${translations[state.activeLang].metric_recom}</span>
                <span class="item-value">${item['Recom'] || '-'}</span>
            </div>
            <div class="sector-metric">
                <span class="item-label">${translations[state.activeLang].metric_avg_change}</span>
                <span class="item-value" style="color: var(--${textValColor}); font-weight:600;">${changeText}</span>
            </div>
            <div class="sector-perf-bar">
                <div class="sector-perf-center"></div>
                <div class="sector-perf-fill ${barColor}" style="${barStyle}"></div>
            </div>
        `;
        grid.appendChild(card);
    });
}

export async function openSectorModal(sectorName) {
    if (!sectorName) return;

    const modal = document.getElementById('sector-modal');
    if (!modal) return;
    modal.classList.add('active');

    // Set loading states
    const titleEl = document.getElementById('sector-modal-title');
    const changeBadge = document.getElementById('sector-modal-change');
    const indList = document.getElementById('sector-modal-industries-list');
    const stocksGrid = document.getElementById('sector-modal-stocks-grid');

    if (titleEl) titleEl.innerText = state.activeLang === 'zh' ? getSectorZhName(sectorName) : sectorName;
    if (changeBadge) {
        changeBadge.innerText = '...';
        changeBadge.className = 'change-badge';
    }
    if (indList) {
        indList.innerHTML = `
            <tr><td colspan="3" style="text-align: center; color: var(--text-muted);">${translations[state.activeLang].loading_sectors}</td></tr>
        `;
    }
    if (stocksGrid) {
        stocksGrid.innerHTML = `
            <div style="text-align: center; color: var(--text-muted); padding: 20px;">${translations[state.activeLang].loading_confluences}</div>
        `;
    }

    try {
        const res = await fetch(`${API_BASE}/api/sectors/${encodeURIComponent(sectorName)}`);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const payload = await res.json();
        
        // Populate Sector Name & Change Badge
        const metrics = payload.metrics || {};
        const { formatted: changeText, isBullish } = parseChange(metrics['Change']);
        if (changeBadge) {
            changeBadge.innerText = changeText;
            changeBadge.className = 'change-badge ' + (isBullish ? 'positive' : 'negative');
        }
        
        // Populate industries performance
        if (indList) {
            indList.innerHTML = '';
            const industries = payload.industries || [];
            
            if (industries.length === 0) {
                indList.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No industries found.</td></tr>`;
            } else {
                industries.forEach(ind => {
                    const tr = document.createElement('tr');
                    const indChange = parseChange(ind['Change']);
                    tr.innerHTML = `
                        <td>${escapeHtml(ind['Name'])}</td>
                        <td style="text-align: right; color: var(--${indChange.isBullish ? 'positive' : 'negative'}); font-weight: 600;">${indChange.formatted}</td>
                        <td style="text-align: right;">${ind['Stocks'] || 0}</td>
                    `;
                    indList.appendChild(tr);
                });
            }
        }
        
        // Populate stocks list
        if (stocksGrid) {
            stocksGrid.innerHTML = '';
            const confluences = payload.confluences || [];
            
            if (confluences.length === 0) {
                stocksGrid.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 20px;">${translations[state.activeLang].no_confluences}</div>`;
            } else {
                confluences.forEach(s => {
                    const div = document.createElement('div');
                    div.className = 'sector-stock-card';
                    const changeVal = parseChange(s['Change']);
                    
                    div.innerHTML = `
                        <div class="sector-stock-info">
                            <span class="sector-stock-ticker">${escapeHtml(s['Ticker'])}</span>
                            <span class="sector-stock-company">${escapeHtml(s['Company'])}</span>
                        </div>
                        <div class="sector-stock-metrics">
                            <span style="color: var(--${changeVal.isBullish ? 'positive' : 'negative'}); font-weight: 600; font-size: 0.8rem;">${changeVal.formatted}</span>
                            <div class="sector-stock-score-wrap">
                                <span class="sector-stock-score">${s['Score']}</span>
                                <span class="sector-stock-score-label">${state.activeLang === 'zh' ? '共振分' : 'Score'}</span>
                            </div>
                        </div>
                    `;
                    div.addEventListener('click', () => {
                        modal.classList.remove('active');
                        openModal(s['Ticker']);
                    });
                    stocksGrid.appendChild(div);
                });
            }
        }
    } catch (e) {
        console.error("Failed to load sector details:", e);
        if (indList) {
            indList.innerHTML = `
                <tr><td colspan="3" style="text-align: center; color: var(--negative);">${translations[state.activeLang].err_sectors}</td></tr>
            `;
        }
    }
}

onLanguageChange(() => {
    if (state.tabLoaded.sectors) {
        loadSectors(true); // sectors summary chip has translations
    }
});
