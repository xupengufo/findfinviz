import { state, API_BASE } from './state.js';
import { translations, onLanguageChange } from './i18n.js';
import { escapeHtml, formatNumber, formatMarketCap, parseChange, updateTimestamp } from './utils.js';
import { openModal } from './modal.js';

/**
 * Main dispatcher to load data for the active sub-tab in Smart Money
 */
export async function loadInsider(force = false) {
    if (state.activeInsiderSubTab === 'inst_flow') {
        return loadInstFlow(force);
    } else if (state.activeInsiderSubTab === 'super_investors') {
        return loadSuperInvestors(force);
    } else {
        return loadInsiderTrades(force);
    }
}

/**
 * 1. Load Executive & Insider Trades (SEC Form 4)
 */
export async function loadInsiderTrades(force = false) {
    if (state.tabLoaded.insider && !force && state.currentInsiderList.length > 0) return;

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
        console.error('Failed to load insider trades:', error);
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

        tr.addEventListener('click', (e) => {
            if (e.target.tagName !== 'A' && !e.target.closest('a')) {
                openModal(item['Ticker']);
            }
        });
        tbody.appendChild(tr);
    });

    if (window.lucide) window.lucide.createIcons();
}

/**
 * 2. Load Institutional Flow & Accumulation
 */
export async function loadInstFlow(force = false) {
    const option = state.activeInstFlowOption || 'accumulation';

    if (!force && state.instFlowCache[option]) {
        state.currentInstFlowList = state.instFlowCache[option];
        renderInstFlow(state.currentInstFlowList);
        return;
    }

    const tbody = document.getElementById('inst-flow-table-body');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted);">${translations[state.activeLang].loading_opps || 'Loading institutional flow...'}</td></tr>`;

    try {
        const res = await fetch(`${API_BASE}/api/institutional/flow?type=${encodeURIComponent(option)}`);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const payload = await res.json();
        updateTimestamp(payload);
        state.instFlowCache[option] = payload.data || [];
        state.currentInstFlowList = state.instFlowCache[option];
        renderInstFlow(state.currentInstFlowList);
    } catch (error) {
        console.error('Failed to load institutional flow:', error);
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--bearish);">${translations[state.activeLang].err_opps || 'Error loading institutional flow records.'}</td></tr>`;
    }
}

export function renderInstFlow(list) {
    const tbody = document.getElementById('inst-flow-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!list || list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center;">${translations[state.activeLang].no_opps || 'No institutional records found.'}</td></tr>`;
        return;
    }

    list.forEach(item => {
        const tr = document.createElement('tr');
        const { formatted: changeText, isBullish } = parseChange(item['Change']);
        const changeClass = isBullish ? 'bullish' : 'bearish';

        // Parse Inst Own %
        let instOwnRaw = item['Inst Own'] || item['Institutional Ownership'] || '-';
        let instOwnText = instOwnRaw;
        if (typeof instOwnRaw === 'number') {
            instOwnText = (instOwnRaw * 100).toFixed(1) + '%';
        }

        // Parse Inst Trans %
        let instTransRaw = item['Inst Trans'] || item['Institutional Transactions'] || '-';
        let instTransText = instTransRaw;
        let transClass = 'trans-neutral';
        if (typeof instTransRaw === 'number') {
            const transVal = (instTransRaw * 100);
            instTransText = (transVal > 0 ? '+' : '') + transVal.toFixed(2) + '%';
            transClass = transVal > 0 ? 'trans-positive' : (transVal < 0 ? 'trans-negative' : 'trans-neutral');
        } else if (typeof instTransRaw === 'string' && instTransRaw.trim()) {
            if (instTransRaw.includes('+') || parseFloat(instTransRaw) > 0) {
                transClass = 'trans-positive';
            } else if (instTransRaw.includes('-') || parseFloat(instTransRaw) < 0) {
                transClass = 'trans-negative';
            }
        }

        tr.innerHTML = `
            <td class="table-ticker font-mono">${escapeHtml(item['Ticker']) || '-'}</td>
            <td class="table-company font-semibold" title="${escapeHtml(item['Company']) || '-'}">${escapeHtml(item['Company']) || '-'}</td>
            <td class="table-sector">${escapeHtml(item['Sector']) || '-'}</td>
            <td class="font-data">${formatMarketCap(item['Market Cap'] || item['Market Cap.'])}</td>
            <td class="font-data font-semibold text-brand-gold">${escapeHtml(instOwnText)}</td>
            <td><span class="inst-trans-chip ${transClass} font-data">${escapeHtml(instTransText)}</span></td>
            <td class="font-data">$${formatNumber(item['Price'])}</td>
            <td class="font-data ${changeClass}">${changeText}</td>
            <td class="font-data">${formatNumber(item['Volume'])}</td>
        `;

        tr.addEventListener('click', () => {
            openModal(item['Ticker']);
        });
        tbody.appendChild(tr);
    });

    if (window.lucide) window.lucide.createIcons();
}

/**
 * 3. Load 13F Super Investors & Top Fund Portfolios
 */
export async function loadSuperInvestors(force = false) {
    const fund = state.activeSuperInvestor || 'berkshire';

    if (!force && state.superInvestorsCache[fund]) {
        state.currentSuperInvestorData = state.superInvestorsCache[fund];
        renderSuperInvestors(state.currentSuperInvestorData);
        return;
    }

    const tbody = document.getElementById('super-investors-table-body');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Loading 13F portfolio...</td></tr>`;

    try {
        const res = await fetch(`${API_BASE}/api/institutional/super-investors?fund=${encodeURIComponent(fund)}`);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const payload = await res.json();
        state.superInvestorsCache[fund] = payload.data || null;
        state.currentSuperInvestorData = state.superInvestorsCache[fund];
        renderSuperInvestors(state.currentSuperInvestorData);
    } catch (error) {
        console.error('Failed to load super investors:', error);
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--bearish);">Error loading 13F portfolio.</td></tr>`;
    }
}

export function renderSuperInvestors(fundData) {
    const tbody = document.getElementById('super-investors-table-body');
    if (!tbody || !fundData) return;
    tbody.innerHTML = '';

    // Update Fund Profile Banner
    const titleEl = document.getElementById('fund-info-title');
    const descEl = document.getElementById('fund-info-desc');
    const valEl = document.getElementById('fund-portfolio-val');
    const countEl = document.getElementById('fund-top-count');

    if (titleEl) {
        const name = state.activeLang === 'zh' ? fundData.fund_name_zh : fundData.fund_name_en;
        const manager = state.activeLang === 'zh' ? fundData.manager_zh : fundData.manager_en;
        titleEl.innerText = `${fundData.avatar || ''} ${name} - ${manager}`;
    }
    if (descEl) {
        descEl.innerText = state.activeLang === 'zh' ? fundData.style_zh : fundData.style_en;
    }
    if (valEl) {
        valEl.innerText = `13F AUM: ${fundData.portfolio_value || '-'}`;
    }
    if (countEl) {
        countEl.innerText = `${fundData.holdings?.length || 0} Core Holdings`;
    }

    const holdings = fundData.holdings || [];
    if (holdings.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center;">No 13F holdings recorded.</td></tr>`;
        return;
    }

    holdings.forEach(item => {
        const tr = document.createElement('tr');

        // Action badge (buy / reduce / hold / new)
        const action = (item.action || 'hold').toLowerCase();
        let actionClass = 'action-hold';
        let actionText = translations[state.activeLang].action_hold || 'HOLD';
        if (action === 'buy' || action === 'add') {
            actionClass = 'action-buy';
            actionText = translations[state.activeLang].action_buy || 'BUY / ADD';
        } else if (action === 'reduce' || action === 'sell') {
            actionClass = 'action-reduce';
            actionText = translations[state.activeLang].action_reduce || 'REDUCE';
        } else if (action === 'new') {
            actionClass = 'action-new';
            actionText = translations[state.activeLang].action_new || 'NEW ENTRY';
        }

        tr.innerHTML = `
            <td class="table-ticker font-mono">${escapeHtml(item.ticker) || '-'}</td>
            <td class="table-company font-semibold">${escapeHtml(item.company) || '-'}</td>
            <td class="table-sector">${escapeHtml(item.sector) || '-'}</td>
            <td class="font-data font-bold text-brand-gold">${escapeHtml(item.weight) || '-'}</td>
            <td class="font-data">${escapeHtml(item.shares) || '-'}</td>
            <td class="font-data font-semibold">$${escapeHtml(item.value) || '-'}</td>
            <td><span class="action-chip ${actionClass}">${actionText}</span></td>
        `;

        tr.addEventListener('click', () => {
            openModal(item.ticker);
        });
        tbody.appendChild(tr);
    });

    if (window.lucide) window.lucide.createIcons();
}

/**
 * Sub-tab switcher handler
 */
export function switchInsiderSubTab(subtab) {
    state.activeInsiderSubTab = subtab;

    // Toggle panels
    const panels = {
        'insider': document.getElementById('subpanel-insider'),
        'inst_flow': document.getElementById('subpanel-inst-flow'),
        'super_investors': document.getElementById('subpanel-super-investors')
    };

    Object.keys(panels).forEach(key => {
        const p = panels[key];
        if (p) {
            if (key === subtab) {
                p.style.display = 'block';
                p.classList.add('active');
            } else {
                p.style.display = 'none';
                p.classList.remove('active');
            }
        }
    });

    // Load subtab content
    if (subtab === 'inst_flow') {
        loadInstFlow();
    } else if (subtab === 'super_investors') {
        loadSuperInvestors();
    } else {
        loadInsiderTrades();
    }
}

onLanguageChange(() => {
    if (state.activeInsiderSubTab === 'inst_flow' && state.currentInstFlowList.length > 0) {
        renderInstFlow(state.currentInstFlowList);
    } else if (state.activeInsiderSubTab === 'super_investors' && state.currentSuperInvestorData) {
        renderSuperInvestors(state.currentSuperInvestorData);
    } else if (state.currentInsiderList.length > 0) {
        renderInsider(state.currentInsiderList);
    }
});

