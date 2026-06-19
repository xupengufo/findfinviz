import { state } from './state.js';
import { translations, sectorZhMapping } from './i18n.js';

// HTML entity escaping to prevent XSS
export function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Debounce helper to prevent rapid API calls
export function debounce(fn, delay = 300) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

// Helper to robustly parse and format FinViz percent/float changes
export function parseChange(val) {
    if (val === undefined || val === null || val === '') {
        return { formatted: '0.00%', isBullish: true, percentVal: 0 };
    }
    
    let num = 0;
    let formatted = '';
    
    if (typeof val === 'number') {
        num = val * 100;
        const sign = num >= 0 ? '+' : '';
        formatted = `${sign}${num.toFixed(2)}%`;
    } else {
        let str = String(val).trim();
        if (str.endsWith('%')) {
            formatted = str;
            num = parseFloat(str);
            if (!str.startsWith('-') && !str.startsWith('+') && num > 0) {
                formatted = '+' + str;
            }
        } else {
            const parsed = parseFloat(str);
            if (!isNaN(parsed)) {
                num = parsed * 100;
                const sign = num >= 0 ? '+' : '';
                formatted = `${sign}${num.toFixed(2)}%`;
            } else {
                formatted = str;
                num = 0;
            }
        }
    }
    
    const isBullish = num >= 0;
    const percentVal = Math.min(Math.abs(num), 100);
    
    return { formatted, isBullish, percentVal };
}

// Format numbers with thousands separators and decimals
export function formatNumber(num) {
    if (!num || isNaN(num)) return num;
    return parseFloat(num).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

// Format market capitalization with localized abbreviations
export function formatMarketCap(val) {
    if (val === undefined || val === null || val === '') return '-';
    
    let num = typeof val === 'number' ? val : parseFloat(val);
    if (isNaN(num)) return val;
    
    let strVal = String(val).trim();
    if (/[a-zA-Z%]$/.test(strVal)) return val;

    if (state.activeLang === 'zh') {
        if (num >= 1e12) {
            return (num / 1e12).toFixed(2) + '万亿';
        } else if (num >= 1e8) {
            return (num / 1e8).toFixed(2) + '亿';
        } else if (num >= 1e4) {
            return (num / 1e4).toFixed(2) + '万';
        }
        return num.toLocaleString(undefined, { maximumFractionDigits: 2 });
    } else {
        if (num >= 1e12) {
            return (num / 1e12).toFixed(2) + 'T';
        } else if (num >= 1e9) {
            return (num / 1e9).toFixed(2) + 'B';
        } else if (num >= 1e6) {
            return (num / 1e6).toFixed(2) + 'M';
        } else if (num >= 1e3) {
            return (num / 1e3).toFixed(2) + 'K';
        }
        return num.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }
}

// Filter lists by market capitalization
export function filterByMarketCap(list, filter) {
    if (filter === 'all') return list;
    return list.filter(item => {
        const mcap = parseFloat(item['Market Cap']);
        if (isNaN(mcap)) return false;
        switch (filter) {
            case 'large': return mcap >= 10e9;
            case 'mid': return mcap >= 2e9 && mcap < 10e9;
            case 'small': return mcap >= 300e6 && mcap < 2e9;
            case 'micro': return mcap < 300e6;
            default: return true;
        }
    });
}

// Sort lists by specified fields
export function sortData(list, field, direction) {
    const sorted = [...list];
    sorted.sort((a, b) => {
        let valA, valB;
        
        if (field === 'marketcap') {
            valA = a['Market Cap'] !== undefined && a['Market Cap'] !== null ? parseFloat(a['Market Cap']) : 0;
            valB = b['Market Cap'] !== undefined && b['Market Cap'] !== null ? parseFloat(b['Market Cap']) : 0;
            if (isNaN(valA)) valA = 0;
            if (isNaN(valB)) valB = 0;
        } else if (field === 'change') {
            valA = a['Change'] !== undefined && a['Change'] !== null ? parseFloat(a['Change']) : 0;
            valB = b['Change'] !== undefined && b['Change'] !== null ? parseFloat(b['Change']) : 0;
            if (isNaN(valA)) valA = 0;
            if (isNaN(valB)) valB = 0;
        } else if (field === 'price') {
            valA = a['Price'] !== undefined && a['Price'] !== null ? parseFloat(a['Price']) : 0;
            valB = b['Price'] !== undefined && b['Price'] !== null ? parseFloat(b['Price']) : 0;
            if (isNaN(valA)) valA = 0;
            if (isNaN(valB)) valB = 0;
        } else {
            valA = String(a['Ticker'] || '').toUpperCase();
            valB = String(b['Ticker'] || '').toUpperCase();
        }
        
        if (valA < valB) return direction === 'asc' ? -1 : 1;
        if (valA > valB) return direction === 'asc' ? 1 : -1;
        return 0;
    });
    return sorted;
}

// Map sector English names to Chinese names
export function getSectorZhName(name) {
    return sectorZhMapping[name] || name;
}

// Update the cache data timestamp display
export function updateTimestamp(payload) {
    const tsEl = document.getElementById('data-timestamp');
    if (tsEl && payload && payload.updated_at) {
        try {
            const d = new Date(payload.updated_at);
            state.lastDataUpdate = d;
            const timeStr = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
            tsEl.textContent = timeStr;
            updateFreshnessIndicator(d);
        } catch(e) {
            tsEl.textContent = '';
        }
    }
}

// Update the cache freshness chip class according to last update time
export function updateFreshnessIndicator(updateTime) {
    const chip = document.querySelector('.status-chip');
    if (!chip || !updateTime) return;
    const ageMs = Date.now() - updateTime.getTime();
    const ageMin = Math.floor(ageMs / 60000);
    
    if (ageMin < 30) {
        chip.className = 'status-chip status-chip-positive';
    } else if (ageMin < 120) {
        chip.className = 'status-chip status-chip-warning';
    } else {
        chip.className = 'status-chip status-chip-stale';
    }
}

// Generate badges HTML for stock card display
export function getBadgesHtml(item) {
    let badges = [];
    
    // Relative Volume RVOL
    const rvolVal = parseFloat(item['Rel Volume']);
    if (!isNaN(rvolVal) && rvolVal > 0) {
        const label = state.activeLang === 'zh' ? `量能 ${rvolVal.toFixed(1)}x` : `RVOL ${rvolVal.toFixed(1)}x`;
        const cssClass = rvolVal > 2.0 ? 'card-badge card-badge-rvol' : 'card-badge';
        const icon = rvolVal > 2.0 ? '<i data-lucide="zap" style="width:10px;height:10px;"></i> ' : '';
        badges.push(`<span class="${cssClass}">${icon}${label}</span>`);
    }

    // Float Short
    const shortFloatStr = String(item['Short Float'] || '');
    if (shortFloatStr && shortFloatStr !== '-') {
        const shortVal = parseFloat(shortFloatStr.replace('%', ''));
        if (!isNaN(shortVal) && shortVal > 0) {
            const label = state.activeLang === 'zh' ? `空头 ${shortVal.toFixed(1)}%` : `Short ${shortVal.toFixed(1)}%`;
            const isHighShort = shortVal >= 15.0;
            
            // If high short interest and Reddit mentions, show SQUEEZE alert!
            const isRedditPopular = item['Factors'] && item['Factors']['reddit_popular'];
            if (isHighShort && isRedditPopular) {
                const alertLabel = state.activeLang === 'zh' ? `🔥 逼空警告 ${shortVal.toFixed(0)}%` : `🔥 SQUEEZE ALERT ${shortVal.toFixed(0)}%`;
                badges.push(`<span class="card-badge card-badge-squeeze">${alertLabel}</span>`);
            } else {
                const cssClass = isHighShort ? 'card-badge card-badge-squeeze' : 'card-badge card-badge-short';
                const icon = isHighShort ? '<i data-lucide="flame" style="width:10px;height:10px;"></i> ' : '';
                badges.push(`<span class="${cssClass}">${icon}${label}</span>`);
            }
        }
    }

    // ROE Badge
    const roeStr = String(item['Return on Equity'] || '');
    if (roeStr && roeStr !== '-') {
        const roeVal = parseFloat(roeStr.replace('%', ''));
        if (!isNaN(roeVal)) {
            const isHighRoe = roeVal >= 15.0;
            const label = state.activeLang === 'zh' ? `ROE ${roeStr}` : `ROE ${roeStr}`;
            const cssClass = isHighRoe ? 'card-badge card-badge-roe' : 'card-badge';
            const icon = isHighRoe ? '<i data-lucide="trending-up" style="width:10px;height:10px;"></i> ' : '';
            badges.push(`<span class="${cssClass}">${icon}${label}</span>`);
        }
    }

    // Debt/Equity Badge
    const debtStr = String(item['Total Debt/Equity'] || '');
    if (debtStr && debtStr !== '-') {
        const debtVal = parseFloat(debtStr);
        if (!isNaN(debtVal)) {
            const isLowDebt = debtVal <= 1.0;
            const label = state.activeLang === 'zh' ? `负债 ${debtStr}` : `Debt/Eq ${debtStr}`;
            const cssClass = isLowDebt ? 'card-badge card-badge-debt' : 'card-badge';
            const icon = isLowDebt ? '<i data-lucide="shield" style="width:10px;height:10px;"></i> ' : '';
            badges.push(`<span class="${cssClass}">${icon}${label}</span>`);
        }
    }

    // Strategy Badges (for Confluence tab and signal overlays)
    if (item['Factors']) {
        if (item['Factors']['pullback']) {
            const label = state.activeLang === 'zh' ? '趋势回调' : 'Pullback Play';
            badges.push(`<span class="card-badge card-badge-strategy-pullback"><i data-lucide="arrow-down-to-line" style="width:10px;height:10px;"></i> ${label}</span>`);
        }
        if (item['Factors']['breakout_candidate']) {
            const label = state.activeLang === 'zh' ? '放量突破候选' : 'Breakout Candidate';
            badges.push(`<span class="card-badge card-badge-strategy-breakout"><i data-lucide="arrow-up-right" style="width:10px;height:10px;"></i> ${label}</span>`);
        }
        if (item['Factors']['quality_compounder']) {
            const label = state.activeLang === 'zh' ? '优质复利' : 'Quality Compounder';
            badges.push(`<span class="card-badge card-badge-strategy-quality"><i data-lucide="award" style="width:10px;height:10px;"></i> ${label}</span>`);
        }
        if (item['Factors']['analyst_upgrade']) {
            const label = state.activeLang === 'zh' ? '分析师上调' : 'Analyst Upgrade';
            badges.push(`<span class="card-badge card-badge-strategy-quality"><i data-lucide="thumbs-up" style="width:10px;height:10px;"></i> ${label}</span>`);
        }
        if (item['Factors']['earnings_catalyst']) {
            const label = state.activeLang === 'zh' ? '财报催化' : 'Earnings Catalyst';
            badges.push(`<span class="card-badge card-badge-rvol"><i data-lucide="calendar" style="width:10px;height:10px;"></i> ${label}</span>`);
        }
        if (item['Factors']['momentum_leader']) {
            const label = state.activeLang === 'zh' ? '主力关注' : 'Market Leader';
            badges.push(`<span class="card-badge"><i data-lucide="bar-chart-2" style="width:10px;height:10px;"></i> ${label}</span>`);
        }
        if (item['Factors']['analyst_downgrade']) {
            const label = state.activeLang === 'zh' ? '⚠️ 分析师下调' : '⚠️ Downgrade';
            badges.push(`<span class="card-badge card-badge-warning"><i data-lucide="trending-down" style="width:10px;height:10px;"></i> ${label}</span>`);
        }
        if (item['Factors']['bearish_momentum']) {
            const label = state.activeLang === 'zh' ? '⚠️ 跌幅居前' : '⚠️ Top Loser';
            badges.push(`<span class="card-badge card-badge-warning"><i data-lucide="arrow-down" style="width:10px;height:10px;"></i> ${label}</span>`);
        }
        if (item['Factors']['overbought']) {
            const label = state.activeLang === 'zh' ? '⚠️ 超买' : '⚠️ Overbought';
            badges.push(`<span class="card-badge card-badge-warning"><i data-lucide="alert-triangle" style="width:10px;height:10px;"></i> ${label}</span>`);
        }
    }

    if (badges.length === 0) return '';
    return `<div class="card-badges-row">${badges.join('')}</div>`;
}
