import { state, API_BASE } from './state.js';
import { translations, sectorZhMapping } from './i18n.js';
import { escapeHtml, parseChange, formatMarketCap } from './utils.js';

export async function openModal(ticker) {
    if (!ticker) return;
    ticker = ticker.toUpperCase();

    const modal = document.getElementById('ticker-modal');
    if (!modal) return;
    modal.classList.add('active');

    // Set Loading state on elements
    document.getElementById('modal-ticker').innerText = ticker;
    document.getElementById('modal-company').innerText = translations[state.activeLang].modal_loading_company;
    document.getElementById('modal-sector').innerText = '-';
    document.getElementById('modal-industry').innerText = '-';
    document.getElementById('modal-desc').innerText = translations[state.activeLang].modal_loading_desc;
    document.getElementById('modal-peers').innerHTML = '';
    document.getElementById('modal-etfs').innerHTML = '';
    document.getElementById('modal-news-list').innerHTML = `<div style="color: var(--text-dark)">${translations[state.activeLang].modal_loading_news}</div>`;
    
    // Reset chart type selector back to static default view
    const chartStaticBtn = document.getElementById('chart-static-btn');
    const chartTvBtn = document.getElementById('chart-tv-btn');
    if (chartStaticBtn && chartTvBtn) {
        chartStaticBtn.classList.add('active');
        chartTvBtn.classList.remove('active');
        document.getElementById('modal-chart-img').style.display = 'block';
        document.getElementById('tradingview-chart-container').style.display = 'none';
    }

    // Setup initial static FinViz Chart
    const chartImg = document.getElementById('modal-chart-img');
    if (chartImg) {
        chartImg.style.opacity = '0';
        chartImg.style.transition = 'opacity 0.2s ease-in-out';
        chartImg.src = `https://finviz.com/chart.ashx?t=${ticker}&ty=c&ta=1&p=d`;
        chartImg.onload = () => {
            chartImg.style.opacity = '1';
        };
        chartImg.onerror = () => {
            chartImg.style.opacity = '1';
        };
    }
    const tvLink = document.getElementById('tv-link');
    if (tvLink) {
        tvLink.href = `https://www.tradingview.com/symbols/${ticker}`;
    }

    // Reset metrics
    ['mcap', 'pe', 'sfloat', 'rsi', 'price', 'change'].forEach(id => {
        const el = document.getElementById(`m-${id}`);
        if (el) el.innerText = '-';
    });

    // Preload confluences if not loaded yet
    if (state.currentConfluencesList.length === 0) {
        try {
            const res = await fetch(`${API_BASE}/api/confluences`);
            if (res.ok) {
                const payload = await res.json();
                if (payload.data) {
                    state.currentConfluencesList = payload.data;
                }
            }
        } catch (e) {
            console.error("Failed to preload confluences in modal:", e);
        }
    }

    // Check for score breakdown
    const confluenceItem = state.currentConfluencesList.find(x => x.Ticker === ticker);
    const breakdownPanel = document.getElementById('score-breakdown-panel');
    if (breakdownPanel) {
        if (confluenceItem && confluenceItem.ScoreBreakdown) {
            breakdownPanel.style.display = 'block';
            const techScore = confluenceItem.ScoreBreakdown.tech || 0;
            const fundScore = confluenceItem.ScoreBreakdown.fund || 0;
            const sentScore = confluenceItem.ScoreBreakdown.sent || 0;
            const valScore = confluenceItem.ScoreBreakdown.val || 0;
            const rsScore = confluenceItem.ScoreBreakdown.rs || 0;

            document.getElementById('breakdown-tech-val').innerText = `${techScore} / 30`;
            document.getElementById('breakdown-tech-bar').style.width = `${(techScore / 30) * 100}%`;

            document.getElementById('breakdown-fund-val').innerText = `${fundScore} / 30`;
            document.getElementById('breakdown-fund-bar').style.width = `${(fundScore / 30) * 100}%`;

            document.getElementById('breakdown-sent-val').innerText = `${sentScore} / 15`;
            document.getElementById('breakdown-sent-bar').style.width = `${(sentScore / 15) * 100}%`;

            const breakdownValText = document.getElementById('breakdown-val-val');
            const breakdownValBar = document.getElementById('breakdown-val-bar');
            if (breakdownValText && breakdownValBar) {
                breakdownValText.innerText = `${valScore} / 5`;
                breakdownValBar.style.width = `${(valScore / 5) * 100}%`;
            }

            const breakdownRsText = document.getElementById('breakdown-rs-val');
            const breakdownRsBar = document.getElementById('breakdown-rs-bar');
            if (breakdownRsText && breakdownRsBar) {
                breakdownRsText.innerText = `${rsScore} / 20`;
                breakdownRsBar.style.width = `${(rsScore / 20) * 100}%`;
            }
        } else {
            breakdownPanel.style.display = 'none';
        }
    }

    try {
        let stockData;
        
        // Check cache
        if (state.stockCache[ticker]) {
            stockData = state.stockCache[ticker];
        } else {
            const res = await fetch(`${API_BASE}/api/stock/${ticker}`);
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const payload = await res.json();
            stockData = payload.data;
            state.stockCache[ticker] = stockData;
        }

        if (!stockData) throw new Error('No details returned');

        const f = stockData.fundament || {};
        
        // Populate basic info
        document.getElementById('modal-company').innerText = f['Company'] || ticker;
        
        let sectorVal = f['Sector'] || '-';
        let industryVal = f['Industry'] || '-';
        if (state.activeLang === 'zh') {
            sectorVal = sectorZhMapping[sectorVal] || sectorVal;
        }
        
        document.getElementById('modal-sector').innerText = sectorVal;
        document.getElementById('modal-industry').innerText = industryVal;
        document.getElementById('modal-desc').innerText = stockData.description || translations[state.activeLang].modal_no_desc;

        // Populate metrics
        document.getElementById('m-mcap').innerText = formatMarketCap(f['Market Cap']);
        document.getElementById('m-pe').innerText = f['P/E'] || '-';
        document.getElementById('m-sfloat').innerText = f['Short Float'] || '-';
        document.getElementById('m-rsi').innerText = f['RSI (14)'] || '-';
        document.getElementById('m-roe').innerText = f['ROE'] || '-';
        document.getElementById('m-debteq').innerText = f['Debt/Eq'] || '-';
        document.getElementById('m-dividend').innerText = f['Dividend TTM'] || f['Dividend Est.'] || '-';
        document.getElementById('m-peg').innerText = f['PEG'] || '-';
        document.getElementById('m-profitmargin').innerText = f['Profit Margin'] || '-';
        document.getElementById('m-targetprice').innerText = f['Target Price'] || '-';
        document.getElementById('m-price').innerText = f['Price'] || '-';
        
        const { formatted: changeText, isBullish } = parseChange(f['Change']);
        const mChange = document.getElementById('m-change');
        if (mChange) {
            mChange.innerText = changeText;
            mChange.className = 'm-value ' + (isBullish ? 'bullish' : 'bearish');
        }

        // Render Peers
        const peersContainer = document.getElementById('modal-peers');
        if (peersContainer) {
            peersContainer.innerHTML = '';
            if (stockData.peers && stockData.peers.length > 0) {
                stockData.peers.forEach(peer => {
                    const btn = document.createElement('button');
                    btn.className = 'peer-tag';
                    btn.innerText = peer;
                    btn.addEventListener('click', () => {
                        openModal(peer);
                    });
                    peersContainer.appendChild(btn);
                });
            } else {
                peersContainer.innerText = translations[state.activeLang].modal_no_peers;
            }
        }

        // Render ETFs
        const etfsContainer = document.getElementById('modal-etfs');
        if (etfsContainer) {
            etfsContainer.innerHTML = '';
            if (stockData.etfs && stockData.etfs.length > 0) {
                stockData.etfs.forEach(etf => {
                    const tag = document.createElement('span');
                    tag.className = 'etf-tag';
                    tag.innerText = etf;
                    etfsContainer.appendChild(tag);
                });
            } else {
                etfsContainer.innerText = translations[state.activeLang].modal_no_etfs;
            }
        }

        // Render News Feed
        const newsContainer = document.getElementById('modal-news-list');
        if (newsContainer) {
            newsContainer.innerHTML = '';
            if (stockData.news && stockData.news.length > 0) {
                stockData.news.slice(0, 10).forEach(news => {
                    const item = document.createElement('a');
                    item.className = 'news-item';
                    item.href = escapeHtml(news.Link);
                    item.target = '_blank';

                    // Parse date string for display
                    let displayDate = news.Date;
                    if (displayDate && displayDate.includes('T')) {
                        displayDate = displayDate.split('T')[1].slice(0, 5) + ' ' + displayDate.split('T')[0].slice(5);
                    }

                    item.innerHTML = `
                        <div class="news-item-title">${escapeHtml(news.Title)}</div>
                        <div class="news-item-meta">
                            <span>${escapeHtml(news.Source)}</span> • 
                            <span>${displayDate}</span>
                        </div>
                    `;
                    newsContainer.appendChild(item);
                });
            } else {
                newsContainer.innerHTML = `<div style="color: var(--text-dark)">${translations[state.activeLang].modal_no_news}</div>`;
            }
        }

    } catch (error) {
        console.error('Failed to load stock details:', error);
        const compEl = document.getElementById('modal-company');
        const descEl = document.getElementById('modal-desc');
        if (compEl) compEl.innerText = translations[state.activeLang].modal_err_company;
        if (descEl) descEl.innerText = translations[state.activeLang].modal_err_desc;
    }
}

export function closeModal() {
    const modal = document.getElementById('ticker-modal');
    if (modal) modal.classList.remove('active');
}

export function loadTradingViewWidget(ticker) {
    const container = document.getElementById('tradingview-chart-container');
    if (!container) return;
    container.innerHTML = `<div id="tradingview_widget_instance" style="width:100%; height:100%;"></div>`;

    const renderWidget = () => {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
        if (window.TradingView) {
            new window.TradingView.widget({
                width: "100%",
                height: "100%",
                symbol: ticker,
                interval: "D",
                timezone: "Etc/UTC",
                theme: currentTheme,
                style: "1",
                locale: state.activeLang === 'zh' ? "zh_CN" : "en",
                toolbar_bg: currentTheme === 'dark' ? "#1e1e1e" : "#f1f3f6",
                enable_publishing: false,
                hide_side_toolbar: false,
                allow_symbol_change: false,
                container_id: "tradingview_widget_instance"
            });
        }
    };

    if (!window.TradingView) {
        const script = document.createElement('script');
        script.src = 'https://s3.tradingview.com/tv.js';
        script.type = 'text/javascript';
        script.onload = renderWidget;
        document.head.appendChild(script);
    } else {
        renderWidget();
    }
}
