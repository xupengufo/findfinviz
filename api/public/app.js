document.addEventListener('DOMContentLoaded', () => {
    // State management
    let activeTab = 'opportunities';
    let activeSignal = 'oversold';
    let activeInsiderOption = 'top owner trade';
    
    // API URL configuration (works for both local development and Vercel)
    const API_BASE = window.location.origin;

    // Cache to prevent duplicate loads within the session
    const tabLoaded = {
        opportunities: false,
        insider: false,
        sectors: false
    };

    // Cache for stock details to allow instant modal transitions
    const stockCache = {};

    // Helper to robustly parse and format FinViz percent/float changes
    function parseChange(val) {
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

    // Initializations
    lucide.createIcons();
    initTabs();
    initSelectors();
    loadOpportunities(); // Load default view

    // 1. Navigation & Tab Switching
    function initTabs() {
        const navButtons = document.querySelectorAll('.nav-btn');
        navButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetTab = btn.getAttribute('data-tab');
                if (targetTab === activeTab) return;

                // Toggle nav classes
                navButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // Toggle section classes
                document.querySelectorAll('.tab-content').forEach(sect => {
                    sect.classList.remove('active');
                });
                document.getElementById(`${targetTab}-tab`).classList.add('active');

                activeTab = targetTab;
                
                // Lazy load tab data
                if (activeTab === 'opportunities') {
                    loadOpportunities();
                } else if (activeTab === 'insider') {
                    loadInsider();
                } else if (activeTab === 'sectors') {
                    loadSectors();
                }
            });
        });
    }

    // 2. Selectors (Signals & Insider Options)
    function initSelectors() {
        // Signal selectors for Opportunities
        const signalButtons = document.querySelectorAll('.signal-btn');
        signalButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                signalButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                activeSignal = btn.getAttribute('data-signal');
                loadOpportunities(true); // Force reload
            });
        });

        // Option selectors for Insider
        const optionButtons = document.querySelectorAll('.option-btn');
        optionButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                optionButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                activeInsiderOption = btn.getAttribute('data-option');
                loadInsider(true); // Force reload
            });
        });

        // Close Modal events
        document.querySelector('.close-modal-btn').addEventListener('click', closeModal);
        document.getElementById('ticker-modal').addEventListener('click', (e) => {
            if (e.target.id === 'ticker-modal') closeModal();
        });
    }

    // 3. Loading Functions
    async function loadOpportunities(force = false) {
        if (tabLoaded.opportunities && !force) return;
        
        const grid = document.getElementById('opps-grid');
        // Render Skeletons while loading
        grid.innerHTML = `
            <div class="skeleton-card"></div>
            <div class="skeleton-card"></div>
            <div class="skeleton-card"></div>
            <div class="skeleton-card"></div>
        `;

        try {
            const res = await fetch(`${API_BASE}/api/opportunities?signal=${activeSignal}`);
            const payload = await res.json();
            const list = payload.data || [];
            
            grid.innerHTML = '';
            if (list.length === 0) {
                grid.innerHTML = `<div class="no-data"><i data-lucide="info"></i> No stocks matching this signal at the moment.</div>`;
                lucide.createIcons();
                return;
            }

            list.forEach(item => {
                const card = document.createElement('div');
                card.className = 'opp-card';
                
                const { formatted: changeText, isBullish } = parseChange(item['Change']);
                const changeClass = isBullish ? 'bullish' : 'bearish';

                card.innerHTML = `
                    <div class="card-header">
                        <span class="card-ticker">${item['Ticker'] || '-'}</span>
                        <span class="card-change ${changeClass}">${changeText}</span>
                    </div>
                    <div class="card-company">${item['Company'] || '-'}</div>
                    <div class="card-footer">
                        <div class="card-footer-item">
                            <span class="item-label">Industry</span>
                            <span class="item-value" title="${item['Industry'] || '-'}">${item['Industry'] || '-'}</span>
                        </div>
                        <div class="card-footer-item">
                            <span class="item-label">Market Cap</span>
                            <span class="item-value">${item['Market Cap'] || '-'}</span>
                        </div>
                        <div class="card-footer-item">
                            <span class="item-label">Price</span>
                            <span class="item-value">${item['Price'] || '-'}</span>
                        </div>
                        <div class="card-footer-item">
                            <span class="item-label">P/E</span>
                            <span class="item-value">${item['P/E'] || '-'}</span>
                        </div>
                    </div>
                `;

                // Card click loads detail sheet
                card.addEventListener('click', () => {
                    openModal(item['Ticker']);
                });
                grid.appendChild(card);
            });

            tabLoaded.opportunities = true;
        } catch (error) {
            console.error('Failed to load opportunities:', error);
            grid.innerHTML = `<div class="error-msg">Error: Failed to fetch opportunities from the API.</div>`;
        }
    }

    async function loadInsider(force = false) {
        if (tabLoaded.insider && !force) return;

        const tbody = document.getElementById('insider-table-body');
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted);">Loading transactions...</td></tr>`;

        try {
            const res = await fetch(`${API_BASE}/api/insiders?option=${encodeURIComponent(activeInsiderOption)}`);
            const payload = await res.json();
            const list = payload.data || [];

            tbody.innerHTML = '';
            if (list.length === 0) {
                tbody.innerHTML = `<tr><td colspan="9" style="text-align: center;">No transactions found.</td></tr>`;
                return;
            }

            list.forEach(item => {
                const tr = document.createElement('tr');
                const rawVal = item['Value ($)'] || 0;
                
                // Format transaction Type (Buy / Sell)
                const isBuy = (item['Relationship'] && item['Transaction'].toLowerCase().includes('buy')) || rawVal > 0;
                const txnText = isBuy ? 'BUY' : 'SELL';
                const txnClass = isBuy ? 'txn-buy' : 'txn-sell';

                tr.innerHTML = `
                    <td class="table-ticker">${item['Ticker'] || '-'}</td>
                    <td title="${item['Relationship'] || '-'}">${item['Relationship'] || '-'}</td>
                    <td>${item['Date'] || '-'}</td>
                    <td class="${txnClass}">${txnText}</td>
                    <td>${formatNumber(item['Cost'])}</td>
                    <td>${formatNumber(item['#Shares'])}</td>
                    <td>$${formatNumber(rawVal)}</td>
                    <td>${formatNumber(item['#Shares Total'])}</td>
                    <td>
                        <a href="https://finviz.com/${item['SEC Form 4 Link']}" target="_blank" class="sec-link">
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

            lucide.createIcons();
            tabLoaded.insider = true;
        } catch (error) {
            console.error('Failed to load insider:', error);
            tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--bearish);">Error loading transaction records.</td></tr>`;
        }
    }

    async function loadSectors(force = false) {
        if (tabLoaded.sectors && !force) return;

        const grid = document.getElementById('sectors-grid');
        grid.innerHTML = `
            <div class="skeleton-card"></div>
            <div class="skeleton-card"></div>
            <div class="skeleton-card"></div>
        `;

        try {
            const res = await fetch(`${API_BASE}/api/sectors`);
            const payload = await res.json();
            const list = payload.data || [];

            grid.innerHTML = '';
            list.forEach(item => {
                const card = document.createElement('div');
                card.className = 'sector-card';

                const { formatted: changeText, isBullish, percentVal } = parseChange(item['Change']);
                const barColor = isBullish ? 'bullish' : 'bearish';

                card.innerHTML = `
                    <div class="sector-name">${item['Name'] || '-'}</div>
                    <div class="sector-metric">
                        <span class="item-label">Stocks Count</span>
                        <span class="item-value">${item['Stocks'] || '-'}</span>
                    </div>
                    <div class="sector-metric">
                        <span class="item-label">Market Cap</span>
                        <span class="item-value">${item['Market Cap'] || '-'}</span>
                    </div>
                    <div class="sector-metric">
                        <span class="item-label">Recom</span>
                        <span class="item-value">${item['Recom'] || '-'}</span>
                    </div>
                    <div class="sector-metric">
                        <span class="item-label">Avg Change</span>
                        <span class="item-value" style="color: var(--${barColor}); font-weight:600;">${changeText}</span>
                    </div>
                    <div class="sector-perf-bar">
                        <div class="sector-perf-fill ${barColor}" style="width: ${percentVal}%"></div>
                    </div>
                `;
                grid.appendChild(card);
            });

            tabLoaded.sectors = true;
        } catch (error) {
            console.error('Failed to load sectors:', error);
            grid.innerHTML = `<div class="error-msg">Error loading sector strength matrix.</div>`;
        }
    }

    // 4. Detail Modal Sheet management
    async function openModal(ticker) {
        if (!ticker) return;
        ticker = ticker.toUpperCase();

        const modal = document.getElementById('ticker-modal');
        modal.classList.add('active');

        // Set Loading state on elements
        document.getElementById('modal-ticker').innerText = ticker;
        document.getElementById('modal-company').innerText = 'Loading company details...';
        document.getElementById('modal-sector').innerText = '-';
        document.getElementById('modal-industry').innerText = '-';
        document.getElementById('modal-desc').innerText = 'Downloading profile description...';
        document.getElementById('modal-peers').innerHTML = '';
        document.getElementById('modal-etfs').innerHTML = '';
        document.getElementById('modal-news-list').innerHTML = '<div style="color: var(--text-dark)">Loading news...</div>';
        
        // Setup initial static FinViz Chart
        const chartImg = document.getElementById('modal-chart-img');
        chartImg.src = `https://finviz.com/chart.ashx?t=${ticker}&ty=c&ta=1&p=d`;
        document.getElementById('tv-link').href = `https://www.tradingview.com/symbols/${ticker}`;

        // Reset metrics
        ['mcap', 'pe', 'sfloat', 'rsi', 'price', 'change'].forEach(id => {
            document.getElementById(`m-${id}`).innerText = '-';
        });

        try {
            let stockData;
            
            // Check cache
            if (stockCache[ticker]) {
                stockData = stockCache[ticker];
            } else {
                const res = await fetch(`${API_BASE}/api/stock/${ticker}`);
                const payload = await res.json();
                stockData = payload.data;
                stockCache[ticker] = stockData;
            }

            if (!stockData) throw new Error('No details returned');

            const f = stockData.fundament || {};
            
            // Populate basic info
            document.getElementById('modal-company').innerText = f['Company'] || ticker;
            document.getElementById('modal-sector').innerText = f['Sector'] || '-';
            document.getElementById('modal-industry').innerText = f['Industry'] || '-';
            document.getElementById('modal-desc').innerText = stockData.description || 'No description available.';

            // Populate metrics
            document.getElementById('m-mcap').innerText = f['Market Cap'] || '-';
            document.getElementById('m-pe').innerText = f['P/E'] || '-';
            document.getElementById('m-sfloat').innerText = f['Short Float'] || '-';
            document.getElementById('m-rsi').innerText = f['RSI (14)'] || '-';
            document.getElementById('m-price').innerText = f['Price'] || '-';
            
            const { formatted: changeText, isBullish } = parseChange(f['Change']);
            const mChange = document.getElementById('m-change');
            mChange.innerText = changeText;
            mChange.className = 'm-value ' + (isBullish ? 'bullish' : 'bearish');

            // Render Peers
            const peersContainer = document.getElementById('modal-peers');
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
                peersContainer.innerText = 'No peers identified.';
            }

            // Render ETFs
            const etfsContainer = document.getElementById('modal-etfs');
            etfsContainer.innerHTML = '';
            if (stockData.etfs && stockData.etfs.length > 0) {
                stockData.etfs.forEach(etf => {
                    const tag = document.createElement('span');
                    tag.className = 'etf-tag';
                    tag.innerText = etf;
                    etfsContainer.appendChild(tag);
                });
            } else {
                etfsContainer.innerText = 'No ETF records.';
            }

            // Render News Feed
            const newsContainer = document.getElementById('modal-news-list');
            newsContainer.innerHTML = '';
            if (stockData.news && stockData.news.length > 0) {
                stockData.news.slice(0, 10).forEach(news => {
                    const item = document.createElement('a');
                    item.className = 'news-item';
                    item.href = news.Link;
                    item.target = '_blank';

                    // Parse date string for display
                    let displayDate = news.Date;
                    if (displayDate && displayDate.includes('T')) {
                        displayDate = displayDate.split('T')[1].slice(0, 5) + ' ' + displayDate.split('T')[0].slice(5);
                    }

                    item.innerHTML = `
                        <div class="news-item-title">${news.Title}</div>
                        <div class="news-item-meta">
                            <span>${news.Source}</span> • 
                            <span>${displayDate}</span>
                        </div>
                    `;
                    newsContainer.appendChild(item);
                });
            } else {
                newsContainer.innerHTML = '<div style="color: var(--text-dark)">No recent news coverage found.</div>';
            }

        } catch (error) {
            console.error('Failed to load stock details:', error);
            document.getElementById('modal-company').innerText = 'Error loading company data';
            document.getElementById('modal-desc').innerText = 'Could not load profile description from the API.';
        }
    }

    function closeModal() {
        document.getElementById('ticker-modal').classList.remove('active');
    }

    // 5. Utility Helper Functions
    function formatNumber(num) {
        if (!num || isNaN(num)) return num;
        return parseFloat(num).toLocaleString(undefined, { maximumFractionDigits: 2 });
    }
});
