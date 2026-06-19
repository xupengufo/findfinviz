import { state } from './state.js';
import { translations, onLanguageChange } from './i18n.js';
import { escapeHtml } from './utils.js';
import { openModal } from './modal.js';

export function toggleWatchlist(ticker, company, sector, industry) {
    if (!ticker) return;
    ticker = ticker.toUpperCase();
    if (state.watchlist[ticker]) {
        delete state.watchlist[ticker];
    } else {
        state.watchlist[ticker] = {
            company: company || '',
            sector: sector || '',
            industry: industry || '',
            note: '',
            addedAt: new Date().toISOString()
        };
    }
    localStorage.setItem('watchlist', JSON.stringify(state.watchlist));
    
    // Update star icons on visible cards
    document.querySelectorAll('.watchlist-star-btn').forEach(btn => {
        const btnTicker = btn.getAttribute('data-ticker');
        if (btnTicker === ticker) {
            btn.classList.toggle('active', !!state.watchlist[ticker]);
        }
    });
    
    // Re-render watchlist tab if it was loaded
    if (state.tabLoaded.watchlist) renderWatchlist();
}

export function isInWatchlist(ticker) {
    if (!ticker) return false;
    return !!state.watchlist[ticker.toUpperCase()];
}

export function updateWatchlistNote(ticker, note) {
    if (!ticker) return;
    ticker = ticker.toUpperCase();
    if (state.watchlist[ticker]) {
        state.watchlist[ticker].note = note;
        localStorage.setItem('watchlist', JSON.stringify(state.watchlist));
    }
}

export function renderWatchlist() {
    const grid = document.getElementById('watchlist-grid');
    if (!grid) return;
    grid.innerHTML = '';

    const tickers = Object.keys(state.watchlist);
    if (tickers.length === 0) {
        grid.innerHTML = `<div class="no-data"><i data-lucide="star"></i> ${translations[state.activeLang].watchlist_empty}</div>`;
        if (window.lucide) window.lucide.createIcons();
        return;
    }

    tickers.forEach(ticker => {
        const info = state.watchlist[ticker];
        const card = document.createElement('div');
        card.className = 'opp-card watchlist-card';

        const addedDate = info.addedAt ? new Date(info.addedAt).toLocaleDateString() : '';

        card.innerHTML = `
            <div class="card-header">
                <span class="card-ticker">${escapeHtml(ticker)}</span>
                <button class="watchlist-remove-btn" data-ticker="${escapeHtml(ticker)}" title="${translations[state.activeLang].watchlist_remove}">
                    <i data-lucide="x" style="width:14px;height:14px;"></i>
                </button>
            </div>
            <div class="card-company">${escapeHtml(info.company || '-')}</div>
            <div class="card-footer" style="margin-top: 6px;">
                <div class="card-footer-item">
                    <span class="item-label">${state.activeLang === 'zh' ? '板块' : 'Sector'}</span>
                    <span class="item-value">${escapeHtml(info.sector || '-')}</span>
                </div>
                <div class="card-footer-item">
                    <span class="item-label">${state.activeLang === 'zh' ? '行业' : 'Industry'}</span>
                    <span class="item-value">${escapeHtml(info.industry || '-')}</span>
                </div>
                <div class="card-footer-item">
                    <span class="item-label">${state.activeLang === 'zh' ? '添加日期' : 'Added'}</span>
                    <span class="item-value">${addedDate}</span>
                </div>
            </div>
            <div class="watchlist-note-wrap">
                <input type="text" class="watchlist-note-input" 
                    placeholder="${translations[state.activeLang].watchlist_note_placeholder}" 
                    value="${escapeHtml(info.note || '')}" 
                    data-ticker="${escapeHtml(ticker)}">
            </div>
        `;

        // Click card to open modal (but not when clicking remove or note input)
        card.addEventListener('click', (e) => {
            if (e.target.closest('.watchlist-remove-btn') || e.target.closest('.watchlist-note-input')) return;
            openModal(ticker);
        });

        // Remove button
        const removeBtn = card.querySelector('.watchlist-remove-btn');
        if (removeBtn) {
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleWatchlist(ticker);
            });
        }

        // Note input
        const noteInput = card.querySelector('.watchlist-note-input');
        if (noteInput) {
            noteInput.addEventListener('click', (e) => e.stopPropagation());
            noteInput.addEventListener('change', (e) => {
                updateWatchlistNote(ticker, e.target.value);
            });
        }

        grid.appendChild(card);
    });

    if (window.lucide) window.lucide.createIcons();
}

onLanguageChange(() => {
    if (state.tabLoaded.watchlist) {
        renderWatchlist();
    }
});
