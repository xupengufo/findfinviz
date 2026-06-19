import { state, API_BASE } from './state.js';
import { translations, translateReason, onLanguageChange } from './i18n.js';
import { 
    escapeHtml, 
    parseChange, 
    formatMarketCap, 
    filterByMarketCap, 
    getBadgesHtml, 
    updateTimestamp 
} from './utils.js';
import { openModal } from './modal.js';

export async function loadConfluences(force = false) {
    if (state.tabLoaded.confluences && !force) return;
    
    const grid = document.getElementById('confluences-grid');
    if (!grid) return;
    grid.innerHTML = `
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
    `;

    try {
        const res = await fetch(`${API_BASE}/api/confluences`);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const payload = await res.json();
        updateTimestamp(payload);
        if (payload.status === 'empty') {
            grid.innerHTML = `<div class="no-data"><i data-lucide="alert-circle"></i> ${translations[state.activeLang].confluence_cache_empty || payload.message}</div>`;
            if (window.lucide) window.lucide.createIcons();
            state.tabLoaded.confluences = false;
            return;
        }
        state.currentConfluencesList = payload.data || [];
        
        renderConfluences(state.currentConfluencesList);
        state.tabLoaded.confluences = true;
    } catch (error) {
        console.error('Failed to load confluences:', error);
        grid.innerHTML = `<div class="error-msg"><i data-lucide="alert-triangle"></i> ${translations[state.activeLang].err_confluences}</div>`;
        if (window.lucide) window.lucide.createIcons();
    }
}

export function renderConfluences(list) {
    const grid = document.getElementById('confluences-grid');
    if (!grid) return;
    grid.innerHTML = '';
    
    const filteredList = filterByMarketCap(list, state.activeConfluenceMcapFilter);
    if (!filteredList || filteredList.length === 0) {
        grid.innerHTML = `<div class="no-data"><i data-lucide="info"></i> ${translations[state.activeLang].no_confluences}</div>`;
        if (window.lucide) window.lucide.createIcons();
        return;
    }

    filteredList.forEach(item => {
        const card = document.createElement('div');
        card.className = 'opp-card';

        const { formatted: changeText, isBullish } = parseChange(item['Change']);
        const changeClass = isBullish ? 'bullish' : 'bearish';

        // Dominant technical pattern
        let dominantPattern = '';
        let patternClass = '';
        if (item['Factors']) {
            if (item['Factors']['breakout']) {
                dominantPattern = state.activeLang === 'zh' ? '⚡ 强力突破' : '⚡ Breakout';
                patternClass = 'pattern-breakout';
            } else if (item['Factors']['pullback']) {
                dominantPattern = state.activeLang === 'zh' ? '📉 缩量回踩' : '📉 Pullback';
                patternClass = 'pattern-pullback';
            } else if (item['Factors']['reversal']) {
                dominantPattern = state.activeLang === 'zh' ? '🛡️ 超卖筑底' : '🛡️ Reversal';
                patternClass = 'pattern-reversal';
            } else if (item['Factors']['breakout_candidate']) {
                dominantPattern = state.activeLang === 'zh' ? '⏳ 蓄势突破' : '⏳ Consolidating';
                patternClass = 'pattern-consolidating';
            }
        }

        // Volume intensity
        let rvolVal = parseFloat(item['Rel Volume']);
        let volumeSparkHtml = '';
        if (!isNaN(rvolVal)) {
            if (rvolVal >= 2.5) {
                volumeSparkHtml = `<span class="vol-spark vol-spark-heavy" title="RVOL: ${rvolVal}">🔥 ${state.activeLang === 'zh' ? '爆量' : 'Heavy'}</span>`;
            } else if (rvolVal >= 1.5) {
                volumeSparkHtml = `<span class="vol-spark vol-spark-active" title="RVOL: ${rvolVal}">⚡ ${state.activeLang === 'zh' ? '放量' : 'Active'}</span>`;
            } else if (rvolVal < 1.0) {
                volumeSparkHtml = `<span class="vol-spark vol-spark-quiet" title="RVOL: ${rvolVal}">💤 ${state.activeLang === 'zh' ? '缩量' : 'Quiet'}</span>`;
            }
        }

        let scoreClass = '';
        if (item['Score'] >= 85) {
            scoreClass = 'score-veryhigh';
        } else if (item['Score'] >= 75) {
            scoreClass = 'score-high';
        } else if (item['Score'] < 55) {
            scoreClass = 'score-low';
        }

        let techScoreClass = 'tech-score-normal';
        if (item['TechScore'] >= 80) {
            techScoreClass = 'tech-score-veryhigh';
        } else if (item['TechScore'] >= 60) {
            techScoreClass = 'tech-score-high';
        } else if (item['TechScore'] < 50) {
            techScoreClass = 'tech-score-low';
        }

        let reasonsHtml = '';
        const allReasons = (item['Reasons'] || []).map(r => translateReason(r));
        const conflicts = (item['Conflicts'] || []).map(r => translateReason(r));
        
        if (allReasons.length > 0 || conflicts.length > 0) {
            const reasonTags = allReasons.map(r => `<span class="confluence-reason-tag">${escapeHtml(r)}</span>`).join('');
            const conflictTags = conflicts.map(r => `<span class="confluence-reason-tag conflict-tag">${escapeHtml(r)}</span>`).join('');
            reasonsHtml = `
                <div class="confluence-reasons-container">
                    <span class="confluence-reason-title">${state.activeLang === 'zh' ? '共振因子' : 'Confluence Factors'}</span>
                    <div class="confluence-reason-tags">
                        ${reasonTags}${conflictTags}
                    </div>
                </div>
            `;
        }

        const badgesHtml = getBadgesHtml(item);

        card.innerHTML = `
            <div class="confluence-header">
                <div>
                    <span class="card-ticker">${escapeHtml(item['Ticker']) || '-'}</span>
                    <div class="card-company" style="margin: 4px 0 0 0; white-space: normal; overflow: visible;">${escapeHtml(item['Company']) || '-'}</div>
                    <div class="card-tech-subrow" style="margin-top: 6px; display: flex; gap: 6px; flex-wrap: wrap;">
                        ${dominantPattern ? `<span class="pattern-badge ${patternClass}">${dominantPattern}</span>` : ''}
                        ${volumeSparkHtml}
                    </div>
                </div>
                <div style="display: flex; gap: 12px; align-items: flex-start;">
                    <div class="tech-score-wrap">
                        <span class="tech-score-indicator ${techScoreClass}">${item['TechScore'] || 0}</span>
                        <span class="confluence-score-label">${state.activeLang === 'zh' ? '技术评分' : 'Tech Score'}</span>
                    </div>
                    <div class="confluence-score-wrap">
                        <span class="confluence-score-indicator ${scoreClass}">${item['Score']}</span>
                        <span class="confluence-score-label">${state.activeLang === 'zh' ? '共振评分' : 'Match Score'}</span>
                    </div>
                </div>
            </div>
            
            ${badgesHtml}

            <div class="card-footer" style="margin-top: 10px;">
                <div class="card-footer-item">
                    <span class="item-label">${state.activeLang === 'zh' ? '最新价' : 'Price'}</span>
                    <span class="item-value font-data">$${escapeHtml(item['Price']) || '-'}</span>
                </div>
                <div class="card-footer-item">
                    <span class="item-label">${state.activeLang === 'zh' ? '变动' : 'Change'}</span>
                    <span class="item-value ${changeClass}">${changeText}</span>
                </div>
                <div class="card-footer-item">
                    <span class="item-label">${state.activeLang === 'zh' ? '市盈率' : 'P/E'}</span>
                    <span class="item-value">${escapeHtml(item['P/E']) || '-'}</span>
                </div>
                <div class="card-footer-item">
                    <span class="item-label">${state.activeLang === 'zh' ? '市值' : 'Market Cap'}</span>
                    <span class="item-value">${formatMarketCap(item['Market Cap'])}</span>
                </div>
            </div>

            ${reasonsHtml}
        `;

        card.addEventListener('click', () => {
            openModal(item['Ticker']);
        });

        grid.appendChild(card);
    });

    if (window.lucide) window.lucide.createIcons();
}

onLanguageChange(() => {
    if (state.tabLoaded.confluences) {
        renderConfluences(state.currentConfluencesList);
    }
});
