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

    // Translations Dictionary
    const translations = {
        en: {
            tab_opps: "Opportunities",
            tab_insider: "Insider Sentiment",
            tab_sectors: "Sector Strengths",
            live_cache: "Live Cache",
            scanner_title: "Technical Scanner",
            insider_title: "Executive & Insider Trades",
            sectors_title: "Sector Strength & Performance Matrix",
            sig_oversold: "Oversold",
            sig_double_bottom: "Double Bottom",
            sig_wedge_down: "Wedge Down",
            sig_triangle_ascending: "Triangle Ascending",
            sig_top_gainers: "Top Gainers",
            sig_new_high: "New High",
            opt_top_owner: "Top Owner Trades",
            opt_latest: "Latest Transactions",
            opt_top_week: "Top Week",
            th_ticker: "Ticker",
            th_relation: "Relationship",
            th_date: "Date",
            th_txn: "Transaction",
            th_cost: "Cost ($)",
            th_shares: "Shares",
            th_value: "Value ($)",
            th_total_shares: "Total Shares",
            th_sec_form: "SEC Form 4",
            metric_stocks: "Stocks Count",
            metric_mcap: "Market Cap",
            metric_recom: "Recom",
            metric_avg_change: "Avg Change",
            modal_mcap: "Market Cap",
            modal_pe: "P/E Ratio",
            modal_sfloat: "Short Float",
            modal_rsi: "RSI (14)",
            modal_price: "Price",
            modal_change: "Change",
            modal_profile: "Company Profile",
            modal_peers: "Sector Peers",
            modal_etfs: "Top ETF Holders",
            modal_chart: "Technical Chart (Daily Candles)",
            modal_tv: "View on TradingView",
            modal_news: "Recent News Feed",
            
            // Dynamic content
            loading_opps: "Loading opportunities...",
            no_opps: "No stocks matching this signal at the moment.",
            err_opps: "Error: Failed to fetch opportunities from the API.",
            loading_insider: "Loading transactions...",
            no_insider: "No transactions found.",
            err_insider: "Error loading transaction records.",
            loading_sectors: "Loading sector performance...",
            err_sectors: "Error loading sector strength matrix.",
            txn_buy: "BUY",
            txn_sell: "SELL",
            modal_loading_company: "Loading company details...",
            modal_loading_desc: "Downloading profile description...",
            modal_no_desc: "No description available.",
            modal_no_peers: "No peers identified.",
            modal_no_etfs: "No ETF records.",
            modal_loading_news: "Loading news...",
            modal_no_news: "No recent news coverage found.",
            modal_err_company: "Error loading company data",
            modal_err_desc: "Could not load profile description from the API."
        },
        zh: {
            tab_opps: "技术选股",
            tab_insider: "大股东动向",
            tab_sectors: "板块热力",
            live_cache: "云端缓存",
            scanner_title: "技术选股指标",
            insider_title: "大股东与高管交易流",
            sectors_title: "美股板块强弱表现",
            sig_oversold: "超卖突破 (RSI < 30)",
            sig_double_bottom: "双底构筑",
            sig_wedge_down: "下降楔形",
            sig_triangle_ascending: "上升三角形",
            sig_top_gainers: "最大涨幅",
            sig_new_high: "创历史新高",
            opt_top_owner: "大股东交易排行",
            opt_latest: "最新交易快讯",
            opt_top_week: "本周大额排行",
            th_ticker: "代码",
            th_relation: "交易人职位",
            th_date: "交易日期",
            th_txn: "交易性质",
            th_cost: "交易单价",
            th_shares: "股数",
            th_value: "总金额 ($)",
            th_total_shares: "持股总量",
            th_sec_form: "备案申报",
            metric_stocks: "成份股数",
            metric_mcap: "行业总市值",
            metric_recom: "买入评级",
            metric_avg_change: "平均涨跌",
            modal_mcap: "市值",
            modal_pe: "市盈率 P/E",
            modal_sfloat: "空头占比",
            modal_rsi: "RSI 指标 (14)",
            modal_price: "当前价",
            modal_change: "今日变动",
            modal_profile: "公司简介",
            modal_peers: "同板块股票 Peers",
            modal_etfs: "持股主要 ETF",
            modal_chart: "日线 K 线图 (技术分析)",
            modal_tv: "在 TradingView 中查看",
            modal_news: "最新财经新闻",
            
            // Dynamic content
            loading_opps: "正在加载选股列表...",
            no_opps: "当前该信号下无匹配的股票。",
            err_opps: "错误：无法从 API 获取股票数据。",
            loading_insider: "正在加载高管交易流...",
            no_insider: "未找到交易记录。",
            err_insider: "错误：无法加载交易记录。",
            loading_sectors: "正在加载板块热力图...",
            err_sectors: "错误：无法加载板块表现矩阵。",
            txn_buy: "买入",
            txn_sell: "卖出",
            modal_loading_company: "正在加载公司基本面...",
            modal_loading_desc: "正在下载公司简介...",
            modal_no_desc: "暂无公司简介数据。",
            modal_no_peers: "暂无同业股票推荐。",
            modal_no_etfs: "暂无持股 ETF 记录。",
            modal_loading_news: "正在加载新闻报道...",
            modal_no_news: "暂无相关新闻报道。",
            modal_err_company: "加载公司数据错误",
            modal_err_desc: "无法从接口下载公司简介描述。"
        }
    };

    // Language Management
    let activeLang = localStorage.getItem('lang');
    if (!activeLang) {
        const navLang = navigator.language || navigator.userLanguage || 'en';
        activeLang = navLang.startsWith('zh') ? 'zh' : 'en';
    }

    function setLanguage(lang) {
        activeLang = lang;
        localStorage.setItem('lang', lang);
        document.documentElement.setAttribute('lang', lang);

        // Update static elements with data-i18n
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const text = translations[lang][key];
            if (text) {
                el.textContent = text;
            }
        });

        // Update Toggle button UI
        const langBtn = document.getElementById('lang-toggle');
        if (langBtn) {
            langBtn.textContent = lang === 'zh' ? '中' : 'EN';
        }

        // Force reload active data elements to update dynamic texts
        if (tabLoaded.opportunities) loadOpportunities(true);
        if (tabLoaded.insider) loadInsider(true);
        if (tabLoaded.sectors) loadSectors(true);
    }

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

    // Theme Management
    let savedTheme = localStorage.getItem('theme');
    if (!savedTheme) {
        savedTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    
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

    // Initializations
    lucide.createIcons();
    setTheme(savedTheme);
    setLanguage(activeLang);

    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setTheme(nextTheme);
        });
    }

    const langToggleBtn = document.getElementById('lang-toggle');
    if (langToggleBtn) {
        langToggleBtn.addEventListener('click', () => {
            const nextLang = activeLang === 'zh' ? 'en' : 'zh';
            setLanguage(nextLang);
        });
    }

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
                grid.innerHTML = `<div class="no-data"><i data-lucide="info"></i> ${translations[activeLang].no_opps}</div>`;
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
                            <span class="item-label">${activeLang === 'zh' ? '行业' : 'Industry'}</span>
                            <span class="item-value" title="${item['Industry'] || '-'}">${item['Industry'] || '-'}</span>
                        </div>
                        <div class="card-footer-item">
                            <span class="item-label">${activeLang === 'zh' ? '市值' : 'Market Cap'}</span>
                            <span class="item-value">${item['Market Cap'] || '-'}</span>
                        </div>
                        <div class="card-footer-item">
                            <span class="item-label">${activeLang === 'zh' ? '最新价' : 'Price'}</span>
                            <span class="item-value">${item['Price'] || '-'}</span>
                        </div>
                        <div class="card-footer-item">
                            <span class="item-label">${activeLang === 'zh' ? '市盈率' : 'P/E'}</span>
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
            grid.innerHTML = `<div class="error-msg"><i data-lucide="alert-triangle"></i> ${translations[activeLang].err_opps}</div>`;
            lucide.createIcons();
        }
    }

    async function loadInsider(force = false) {
        if (tabLoaded.insider && !force) return;

        const tbody = document.getElementById('insider-table-body');
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted);">${translations[activeLang].loading_insider}</td></tr>`;

        try {
            const res = await fetch(`${API_BASE}/api/insiders?option=${encodeURIComponent(activeInsiderOption)}`);
            const payload = await res.json();
            const list = payload.data || [];

            tbody.innerHTML = '';
            if (list.length === 0) {
                tbody.innerHTML = `<tr><td colspan="9" style="text-align: center;">${translations[activeLang].no_insider}</td></tr>`;
                return;
            }

            list.forEach(item => {
                const tr = document.createElement('tr');
                const rawVal = item['Value ($)'] || 0;
                
                // Format transaction Type (Buy / Sell)
                const isBuy = (item['Relationship'] && item['Transaction'].toLowerCase().includes('buy')) || rawVal > 0;
                const txnText = isBuy ? translations[activeLang].txn_buy : translations[activeLang].txn_sell;
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
            tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--bearish);">${translations[activeLang].err_insider}</td></tr>`;
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

                // Map sector names if Chinese is active
                let sectorName = item['Name'] || '-';
                if (activeLang === 'zh') {
                    const sectorMapping = {
                        'Technology': '科技',
                        'Financial': '金融',
                        'Healthcare': '医疗保健',
                        'Consumer Cyclical': '周期性消费',
                        'Industrials': '工业',
                        'Communication Services': '通讯服务',
                        'Consumer Defensive': '防御性消费',
                        'Energy': '能源',
                        'Real Estate': '房地产',
                        'Basic Materials': '基础材料',
                        'Utilities': '公用事业'
                    };
                    sectorName = sectorMapping[sectorName] || sectorName;
                }

                card.innerHTML = `
                    <div class="sector-name">${sectorName}</div>
                    <div class="sector-metric">
                        <span class="item-label">${translations[activeLang].metric_stocks}</span>
                        <span class="item-value">${item['Stocks'] || '-'}</span>
                    </div>
                    <div class="sector-metric">
                        <span class="item-label">${translations[activeLang].metric_mcap}</span>
                        <span class="item-value">${item['Market Cap'] || '-'}</span>
                    </div>
                    <div class="sector-metric">
                        <span class="item-label">${translations[activeLang].metric_recom}</span>
                        <span class="item-value">${item['Recom'] || '-'}</span>
                    </div>
                    <div class="sector-metric">
                        <span class="item-label">${translations[activeLang].metric_avg_change}</span>
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
            grid.innerHTML = `<div class="error-msg"><i data-lucide="alert-triangle"></i> ${translations[activeLang].err_sectors}</div>`;
            lucide.createIcons();
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
        document.getElementById('modal-company').innerText = translations[activeLang].modal_loading_company;
        document.getElementById('modal-sector').innerText = '-';
        document.getElementById('modal-industry').innerText = '-';
        document.getElementById('modal-desc').innerText = translations[activeLang].modal_loading_desc;
        document.getElementById('modal-peers').innerHTML = '';
        document.getElementById('modal-etfs').innerHTML = '';
        document.getElementById('modal-news-list').innerHTML = `<div style="color: var(--text-dark)">${translations[activeLang].modal_loading_news}</div>`;
        
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
            
            let sectorVal = f['Sector'] || '-';
            let industryVal = f['Industry'] || '-';
            if (activeLang === 'zh') {
                const sectorMapping = {
                    'Technology': '科技',
                    'Financial': '金融',
                    'Healthcare': '医疗保健',
                    'Consumer Cyclical': '周期性消费',
                    'Industrials': '工业',
                    'Communication Services': '通讯服务',
                    'Consumer Defensive': '防御性消费',
                    'Energy': '能源',
                    'Real Estate': '房地产',
                    'Basic Materials': '基础材料',
                    'Utilities': '公用事业'
                };
                sectorVal = sectorMapping[sectorVal] || sectorVal;
            }
            
            document.getElementById('modal-sector').innerText = sectorVal;
            document.getElementById('modal-industry').innerText = industryVal;
            document.getElementById('modal-desc').innerText = stockData.description || translations[activeLang].modal_no_desc;

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
                peersContainer.innerText = translations[activeLang].modal_no_peers;
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
                etfsContainer.innerText = translations[activeLang].modal_no_etfs;
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
                newsContainer.innerHTML = `<div style="color: var(--text-dark)">${translations[activeLang].modal_no_news}</div>`;
            }

        } catch (error) {
            console.error('Failed to load stock details:', error);
            document.getElementById('modal-company').innerText = translations[activeLang].modal_err_company;
            document.getElementById('modal-desc').innerText = translations[activeLang].modal_err_desc;
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
