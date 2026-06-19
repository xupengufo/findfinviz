import './styles.css';

import { state } from './state.js';
import { translations, setLanguage } from './i18n.js';
import { debounce } from './utils.js';
import { openModal, closeModal, loadTradingViewWidget } from './modal.js';
import { loadOpportunities, renderOpportunities } from './opportunities.js';
import { loadConfluences, renderConfluences } from './confluences.js';
import { loadInsider } from './insider.js';
import { loadSectors } from './sectors.js';
import { loadReddit } from './reddit.js';
import { renderWatchlist } from './watchlist.js';
import { loadTurbulence, renderTurbulenceChart, updateProbitModalData } from './turbulence.js';

// Theme Management
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    const sun = document.querySelector('.theme-icon-sun');
    const moon = document.querySelector('.theme-icon-moon');
    if (sun && moon) {
        if (theme === 'dark') {
            sun.style.display = 'block';
            moon.style.display = 'none';
        } else {
            sun.style.display = 'none';
            moon.style.display = 'block';
        }
    }
}

// Debounced loaders for button click handlers
const debouncedLoadOpportunities = debounce(() => loadOpportunities(true), 300);
const debouncedLoadInsider = debounce(() => loadInsider(true), 300);

// Tab switching registration
function initTabs() {
    const navButtons = document.querySelectorAll('.nav-btn');
    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            if (targetTab === state.activeTab) return;

            // Toggle nav classes
            navButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Toggle section classes
            document.querySelectorAll('.tab-content').forEach(sect => {
                sect.classList.remove('active');
            });
            const targetSect = document.getElementById(`${targetTab}-tab`);
            if (targetSect) targetSect.classList.add('active');

            state.activeTab = targetTab;
            
            // Lazy load tab data
            if (state.activeTab === 'opportunities') {
                loadOpportunities();
            } else if (state.activeTab === 'confluences') {
                loadConfluences();
            } else if (state.activeTab === 'insider') {
                loadInsider();
            } else if (state.activeTab === 'sectors') {
                loadSectors();
            } else if (state.activeTab === 'reddit') {
                loadReddit();
            } else if (state.activeTab === 'turbulence') {
                loadTurbulence();
            } else if (state.activeTab === 'watchlist') {
                renderWatchlist();
                state.tabLoaded.watchlist = true;
            }
        });
    });
}

// Selectors (Signals & Insider Options)
function initSelectors() {
    // Signal selectors for Opportunities
    const signalButtons = document.querySelectorAll('.signal-btn');
    signalButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            signalButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.activeSignal = btn.getAttribute('data-signal');
            debouncedLoadOpportunities(); // Force reload (debounced)
        });
    });

    // Option selectors for Insider
    const optionButtons = document.querySelectorAll('.option-btn');
    optionButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            optionButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.activeInsiderOption = btn.getAttribute('data-option');
            debouncedLoadInsider(); // Force reload (debounced)
        });
    });

    // Sort selectors for Opportunities
    const sortButtons = document.querySelectorAll('.sort-btn');
    sortButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const sortField = btn.getAttribute('data-sort');
            if (sortField === state.activeSortField) {
                state.activeSortDirection = state.activeSortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                state.activeSortField = sortField;
                state.activeSortDirection = sortField === 'ticker' ? 'asc' : 'desc';
            }
            
            sortButtons.forEach(b => {
                b.classList.remove('active');
                if (b !== btn) {
                    const wrap = b.querySelector('.sort-icon-wrap');
                    if (wrap) {
                        wrap.innerHTML = `<i data-lucide="arrow-down-narrow-wide"></i>`;
                    }
                }
            });
            
            btn.classList.add('active');
            const iconWrap = btn.querySelector('.sort-icon-wrap');
            if (iconWrap && window.lucide) {
                iconWrap.innerHTML = `<i data-lucide="${state.activeSortDirection === 'asc' ? 'arrow-up-narrow-wide' : 'arrow-down-narrow-wide'}"></i>`;
                window.lucide.createIcons();
            }
            
            renderOpportunities(state.currentOppsList);
        });
    });

    // Market Cap Filter selectors for Opportunities
    const mcapButtonsAll = document.querySelectorAll('.mcap-filter-btn:not([data-context])');
    mcapButtonsAll.forEach(btn => {
        btn.addEventListener('click', () => {
            mcapButtonsAll.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.activeMcapFilter = btn.getAttribute('data-mcap');
            renderOpportunities(state.currentOppsList);
        });
    });

    // Market Cap Filter selectors for Confluences
    const mcapConfButtons = document.querySelectorAll('.mcap-filter-btn[data-context="confluences"]');
    mcapConfButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            mcapConfButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.activeConfluenceMcapFilter = btn.getAttribute('data-mcap');
            renderConfluences(state.currentConfluencesList);
        });
    });

    // Range selectors for Turbulence
    const rangeButtons = document.querySelectorAll('.turb-range-btn');
    rangeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            rangeButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.currentTurbulenceRange = btn.getAttribute('data-range');
            if (state.currentTurbulenceData) {
                renderTurbulenceChart(state.currentTurbulenceData.chart_series);
            }
        });
    });

    // Close Modal events
    const closeBtn = document.querySelector('.close-modal-btn');
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    
    const tickerModal = document.getElementById('ticker-modal');
    if (tickerModal) {
        tickerModal.addEventListener('click', (e) => {
            if (e.target.id === 'ticker-modal') closeModal();
        });
    }

    // Close Sector Modal events
    const closeSectorBtn = document.getElementById('close-sector-modal-btn');
    if (closeSectorBtn) {
        closeSectorBtn.addEventListener('click', () => {
            const sectorModal = document.getElementById('sector-modal');
            if (sectorModal) sectorModal.classList.remove('active');
        });
    }
    const sectorModal = document.getElementById('sector-modal');
    if (sectorModal) {
        sectorModal.addEventListener('click', (e) => {
            if (e.target.id === 'sector-modal') {
                sectorModal.classList.remove('active');
            }
        });
    }

    // Close Probit Modal events
    const closeProbitBtn = document.getElementById('close-probit-modal-btn');
    if (closeProbitBtn) {
        closeProbitBtn.addEventListener('click', () => {
            const probitModal = document.getElementById('probit-modal');
            if (probitModal) probitModal.classList.remove('active');
        });
    }
    const probitModalEl = document.getElementById('probit-modal');
    if (probitModalEl) {
        probitModalEl.addEventListener('click', (e) => {
            if (e.target.id === 'probit-modal') {
                probitModalEl.classList.remove('active');
            }
        });
    }

    // Open Probit Modal event
    const probitTrigger = document.querySelector('.probit-tooltip-trigger');
    if (probitTrigger) {
        probitTrigger.addEventListener('click', () => {
            const probitModal = document.getElementById('probit-modal');
            if (probitModal) {
                probitModal.classList.add('active');
                updateProbitModalData();
            }
        });
    }

    // Chart Type Switcher events
    const chartStaticBtn = document.getElementById('chart-static-btn');
    const chartTvBtn = document.getElementById('chart-tv-btn');
    if (chartStaticBtn && chartTvBtn) {
        chartStaticBtn.addEventListener('click', () => {
            chartStaticBtn.classList.add('active');
            chartTvBtn.classList.remove('active');
            document.getElementById('modal-chart-img').style.display = 'block';
            document.getElementById('tradingview-chart-container').style.display = 'none';
        });
        chartTvBtn.addEventListener('click', () => {
            chartTvBtn.classList.add('active');
            chartStaticBtn.classList.remove('active');
            document.getElementById('modal-chart-img').style.display = 'none';
            document.getElementById('tradingview-chart-container').style.display = 'block';
            const currentTicker = document.getElementById('modal-ticker').innerText;
            loadTradingViewWidget(currentTicker);
        });
    }

    // Refresh button event listener
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            const icon = refreshBtn.querySelector('i');
            if (icon) icon.classList.add('spin-animation');
            
            try {
                let key = localStorage.getItem('sync_api_key') || '';
                let url = `/api/sync`;
                if (key) {
                    url += `?api_key=${encodeURIComponent(key)}`;
                }
                
                let res = await fetch(url);
                if (res.status === 401) {
                    const newKey = prompt(state.activeLang === 'zh' ? '请输入同步 API Key:' : 'Please enter Sync API Key:');
                    if (newKey) {
                        localStorage.setItem('sync_api_key', newKey);
                        url = `/api/sync?api_key=${encodeURIComponent(newKey)}`;
                        res = await fetch(url);
                    } else {
                        if (icon) icon.classList.remove('spin-animation');
                        return;
                    }
                }
                
                if (res.ok) {
                    alert(state.activeLang === 'zh' ? '同步任务已在后台启动，数据将在 1-2 分钟内更新！' : 'Sync task triggered in the background! Data will update in 1-2 minutes.');
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                } else {
                    const err = await res.json();
                    alert((state.activeLang === 'zh' ? '同步失败: ' : 'Sync failed: ') + (err.detail || 'Unknown error'));
                }
            } catch(e) {
                alert((state.activeLang === 'zh' ? '请求失败: ' : 'Request failed: ') + e.message);
            } finally {
                if (icon) icon.classList.remove('spin-animation');
            }
        });
    }
}

// DOM Init
document.addEventListener('DOMContentLoaded', () => {
    // Initial theme & language setup
    let savedTheme = localStorage.getItem('theme');
    if (!savedTheme) {
        savedTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    setTheme(savedTheme);
    setLanguage(state.activeLang);

    // Lucide initialization
    if (window.lucide) window.lucide.createIcons();

    initTabs();
    initSelectors();

    // Theme toggle click binding
    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setTheme(nextTheme);
        });
    }

    // Language toggle click binding
    const langToggleBtn = document.getElementById('lang-toggle');
    if (langToggleBtn) {
        langToggleBtn.addEventListener('click', () => {
            const nextLang = state.activeLang === 'zh' ? 'en' : 'zh';
            setLanguage(nextLang);
        });
    }

    // Ticker Search binding
    const searchInput = document.getElementById('ticker-search');
    if (searchInput) {
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const ticker = searchInput.value.trim().toUpperCase();
                if (ticker) {
                    openModal(ticker);
                    searchInput.value = '';
                    searchInput.blur();
                }
            }
        });
    }

    // Escape key modal dismissing
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
            const sectorModal = document.getElementById('sector-modal');
            if (sectorModal) sectorModal.classList.remove('active');
            const probitModal = document.getElementById('probit-modal');
            if (probitModal) probitModal.classList.remove('active');
        }
    });

    // Support hash-based routing for initial tab selection
    const initialTab = window.location.hash.replace('#', '');
    const validTabs = ['opportunities', 'confluences', 'insider', 'sectors', 'reddit', 'watchlist', 'turbulence'];
    if (validTabs.includes(initialTab)) {
        const targetBtn = document.querySelector(`.nav-btn[data-tab="${initialTab}"]`);
        if (targetBtn) {
            targetBtn.click();
        } else {
            loadOpportunities();
        }
    } else {
        loadOpportunities(); // Load default view
    }
});
