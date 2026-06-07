document.addEventListener('DOMContentLoaded', () => {
    // HTML entity escaping to prevent XSS
    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Debounce helper to prevent rapid API calls
    function debounce(fn, delay = 300) {
        let timer;
        return function(...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    }

    // State management
    let activeTab = 'opportunities';
    let activeSignal = 'oversold';
    let activeInsiderOption = 'top owner trade';
    let activeSortField = 'marketcap';
    let activeSortDirection = 'desc';
    let activeMcapFilter = 'all';
    let activeConfluenceMcapFilter = 'all';
    let currentOppsList = [];
    let currentInsiderList = [];
    let currentSectorsList = [];
    let currentRedditList = [];
    let currentConfluencesList = [];
    let currentWsbCalendar = null;
    let currentTurbulenceData = null;
    let turbulenceChartInstance = null;
    let watchlist = JSON.parse(localStorage.getItem('watchlist') || '{}');
    
    // API URL configuration (works for both local development and Vercel)
    const API_BASE = window.location.origin;

    // Cache to prevent duplicate loads within the session
    const tabLoaded = {
        opportunities: false,
        confluences: false,
        insider: false,
        sectors: false,
        reddit: false,
        watchlist: false,
        turbulence: false
    };

    // Cache for stock details to allow instant modal transitions
    const stockCache = {};

    // Track last data update timestamp for freshness display
    let lastDataUpdate = null;

    function updateTimestamp(payload) {
        const tsEl = document.getElementById('data-timestamp');
        if (tsEl && payload && payload.updated_at) {
            try {
                const d = new Date(payload.updated_at);
                lastDataUpdate = d;
                const timeStr = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
                tsEl.textContent = timeStr;
                updateFreshnessIndicator(d);
            } catch(e) {
                tsEl.textContent = '';
            }
        }
    }

    function updateFreshnessIndicator(updateTime) {
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

    // Translations Dictionary
    // Shared sector name mapping (used across loadSectors, renderSectors, openModal, getSectorZhName)
    const sectorZhMapping = {
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

    // Confluence reason key translations
    const reasonTranslations = {
        en: {
            reason_reversal: "Technical Reversal (Oversold/Double Bottom)",
            reason_pullback: "Trend Pullback (SMA Support)",
            reason_breakout: "Technical Breakout (New High/Wedge)",
            reason_breakout_candidate: "Breakout Candidate (High Volume Near ATH)",
            reason_volume_spike: "Unusual Volume (Institutional Activity)",
            reason_high_volatility: "High Volatility",
            reason_strong_sector: "Strong Sector (Today's Top Performer)",
            reason_insider_buying: "Insider Buying (Executive Net Purchase)",
            reason_quality_compounder: "Quality Compounder (High ROE, Low Debt)",
            reason_analyst_upgrade: "Analyst Upgrade",
            reason_earnings_catalyst: "Earnings Catalyst",
            reason_analyst_downgrade: "⚠️ Analyst Downgrade",
            reason_momentum_leader: "Market Leader (Institutional Focus)",
            reason_reddit_popular: "Reddit Popular (Retail Buzz)",
            reason_squeeze_play: "Squeeze Play (High Short + Attention)",
            reason_high_short_float: "High Short Float",
            reason_bearish_momentum: "⚠️ Bearish Momentum (Top Loser)",
            conflict_overbought_reversal: "⚠️ Overbought vs Reversal/Pullback conflict",
            conflict_overbought_breakout: "⚠️ Breakout + Overbought — high chase risk",
            conflict_reversal_bearish: "⚠️ Reversal vs Bearish Momentum — possible continuation",
            conflict_quality_downgrade: "⚠️ Quality stock downgraded — check fundamentals"
        },
        zh: {
            reason_reversal: "技术面反转 (超卖/双底构筑)",
            reason_pullback: "趋势回调 (均线支撑)",
            reason_breakout: "技术面突破 (新高/楔形)",
            reason_breakout_candidate: "突破候选 (放量临近历史高点)",
            reason_volume_spike: "异常放量 (主力异动)",
            reason_high_volatility: "高波动率",
            reason_strong_sector: "强势板块 (今日领涨板块)",
            reason_insider_buying: "高管增持 (内部人净买入)",
            reason_quality_compounder: "优质复利 (高ROE低负债)",
            reason_analyst_upgrade: "分析师上调评级",
            reason_earnings_catalyst: "财报催化剂",
            reason_analyst_downgrade: "⚠️ 分析师下调评级",
            reason_momentum_leader: "主力关注 (市场焦点)",
            reason_reddit_popular: "散户热议 (Reddit 高讨论度)",
            reason_squeeze_play: "逼空机会 (高空头比+关注度)",
            reason_high_short_float: "高卖空比例",
            reason_bearish_momentum: "⚠️ 跌幅居前 (空头势头)",
            conflict_overbought_reversal: "⚠️ 超买 vs 反转/回调 — 信号矛盾",
            conflict_overbought_breakout: "⚠️ 突破+超买 — 高追风险",
            conflict_reversal_bearish: "⚠️ 反转 vs 持续下跌 — 可能是下跌中继",
            conflict_quality_downgrade: "⚠️ 绩优股被下调 — 需确认基本面"
        }
    };

    function translateReason(key) {
        return (reasonTranslations[activeLang] || reasonTranslations.en)[key] || key;
    }

    const translations = {
        en: {
            tab_opps: "Opportunities",
            tab_insider: "Insider Sentiment",
            tab_sectors: "Sector Strengths",
            tab_reddit: "Reddit Sentiment",
            live_cache: "Live Cache",
            scanner_title: "Technical Scanner",
            insider_title: "Executive & Insider Trades",
            sectors_title: "Sector Strength & Performance Matrix",
            reddit_title: "Reddit & WSB Retail Sentiment",
            sig_oversold: "Oversold",
            sig_double_bottom: "Double Bottom",
            sig_wedge_down: "Wedge Down",
            sig_triangle_ascending: "Triangle Ascending",
            sig_top_gainers: "Top Gainers",
            sig_new_high: "New High",
            sig_pullback: "Trend Pullback",
            sig_breakout_candidate: "Breakout Candidate",
            sig_quality_compounder: "Quality Compounder",
            opt_top_owner: "Top Owner Trades",
            opt_latest: "Latest Transactions",
            opt_top_week: "Top Week",
            th_rank: "Rank",
            th_ticker: "Ticker",
            th_name: "Name",
            th_relation: "Relationship",
            th_date: "Date",
            th_txn: "Transaction",
            th_cost: "Cost ($)",
            th_shares: "Shares",
            th_value: "Value ($)",
            th_total_shares: "Total Shares",
            th_sec_form: "SEC Form 4",
            th_mentions: "Mentions",
            th_upvotes: "Upvotes",
            th_trend: "24H Trend",
            metric_stocks: "Stocks Count",
            metric_mcap: "Market Cap",
            metric_recom: "Recom",
            metric_avg_change: "Avg Change",
            modal_mcap: "Market Cap",
            modal_pe: "P/E Ratio",
            modal_sfloat: "Short Float",
            modal_rsi: "RSI (14)",
            modal_roe: "ROE",
            modal_debt_eq: "Debt/Equity",
            modal_dividend: "Dividend Yield",
            modal_peg: "PEG Ratio",
            modal_profit_margin: "Profit Margin",
            modal_target_price: "Target Price",
            modal_price: "Price",
            modal_change: "Change",
            modal_profile: "Company Profile",
            modal_peers: "Sector Peers",
            modal_etfs: "Top ETF Holders",
            modal_chart: "Technical Chart (Daily Candles)",
            modal_tv: "View on TradingView",
            modal_news: "Recent News Feed",
            sort_mcap: "Market Cap",
            sort_change: "Change",
            sort_price: "Price",
            sort_ticker: "Ticker",
            mcap_all: "All Caps",
            mcap_large: "Large (>$10B)",
            mcap_mid: "Mid ($2B-$10B)",
            mcap_small: "Small ($300M-$2B)",
            mcap_micro: "Micro (<$300M)",
            
            // Dynamic content
            loading_opps: "Loading opportunities...",
            no_opps: "No stocks matching this signal at the moment.",
            err_opps: "Error: Failed to fetch opportunities from the API.",
            loading_insider: "Loading transactions...",
            no_insider: "No transactions found.",
            err_insider: "Error loading transaction records.",
            loading_sectors: "Loading sector performance...",
            err_sectors: "Error loading sector strength matrix.",
            loading_reddit: "Loading Reddit sentiment...",
            err_reddit: "Error: Failed to fetch Reddit sentiment from the API.",
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
            modal_err_desc: "Could not load profile description from the API.",
            
            tab_confluences: "Smart Picks",
            confluences_title: "Smart Confluence Picks",
            confluences_subtitle: "Stocks aligning technical reversals/breakouts, institutional volume, insider buying, and retail sentiment.",
            sig_unusual_volume: "Unusual Volume",
            sig_high_short_interest: "High Short Float",
            sig_top_losers: "Top Losers",
            sig_most_active: "Most Active",
            sig_most_volatile: "Most Volatile",
            sig_upgrades: "Upgrades",
            sig_downgrades: "Downgrades",
            sig_earnings_before: "Earnings Before",
            sig_earnings_after: "Earnings After",
            sig_recent_insider_buying: "Recent Insider Buying",
            chart_static: "Static",
            chart_tv: "TradingView",
            loading_confluences: "Computing smart setups...",
            no_confluences: "No confluence setups matching criteria right now.",
            err_confluences: "Error: Failed to fetch confluences from API.",
            confluence_cache_empty: "The Smart Picks cache is empty. Please run sync first to populate it.",
            modal_score_breakdown: "Resonance Score Breakdown",
            breakdown_tech: "Technical Structure",
            breakdown_fund: "Fundamentals & Insiders",
            breakdown_sent: "Market Sentiment & Flow",
            sector_industries_title: "Industries in Sector",
            sector_top_opportunities: "Top Confluence Opportunities",
            industry_name: "Industry",
            industry_change: "Change",
            industry_stocks: "Stocks",
            wsb_calendar_title: "WSB Important Events Calendar",
            reddit_trending_title: "Trending Tickers (ApeWisdom)",
            th_calendar_date: "Date",
            th_calendar_event: "Event",
            th_calendar_focus: "Community Focus",
            loading_wsb_calendar: "Loading WSB Important Events Calendar...",
            err_wsb_calendar: "Error: Failed to load WSB Important Events Calendar.",
            data_fresh: "Fresh",
            data_stale: "Stale",
            data_age_min: "m ago",
            data_age_hour: "h ago",
            refresh_btn: "Refresh",
            tab_watchlist: "My Picks",
            watchlist_title: "My Watchlist",
            watchlist_subtitle: "Your saved stocks for tracking. Data stored locally in your browser.",
            watchlist_empty: "No stocks saved yet. Click the ★ button on any stock card to add it here.",
            watchlist_remove: "Remove",
            watchlist_note_placeholder: "Add a note...",
            tab_turbulence: "Risk Radar",
            turb_title: "Market Risk Radar & Turbulence Index",
            turb_subtitle: "Based on Kritzman-Li (2010) Mahalanobis Distance model with Danger Zone divergence alerts.",
            turb_current_state: "Risk Regime",
            turb_pos_size: "Suggested Position",
            turb_checklist: "Danger Zone Checklist",
            turb_cond_dist: "1. Cross-Asset Turbulence Elevated",
            turb_cond_spx: "2. S&P 500 above 50-day SMA",
            turb_cond_vix: "3. VIX Complacent (< 25)",
            turb_state_normal_desc: "Turbulence is normal. No structural threat detected.",
            turb_state_elevated_desc: "Turbulence is elevated. Systemic risk is building up.",
            turb_state_high_desc: "Danger Zone active! Divergence between price and structural risk is high.",
            turb_state_critical_desc: "Extreme turbulence! Underlying cross-asset correlations are breaking down.",
            turb_pos_desc: "Scale portfolio size dynamically according to systemic stress.",
            turb_chart_title: "Historical Turbulence Index vs S&P 500 (SPY)",
            turb_verdict_loading: "Checking conditions...",
            turb_verdict_active: "🔥 Danger Zone active — High-conviction risk divergence alert!",
            turb_verdict_inactive: "✓ Danger Zone inactive — Checklist conditions not met simultaneously.",
            loading_turbulence: "Loading market risk metrics...",
            err_turbulence: "Error: Failed to fetch market turbulence metrics from API."
        },
        zh: {
            tab_opps: "技术选股",
            tab_insider: "大股东动向",
            tab_sectors: "板块热力",
            tab_reddit: "散户热度",
            live_cache: "云端缓存",
            scanner_title: "技术选股指标",
            insider_title: "大股东与高管交易流",
            sectors_title: "美股板块强弱表现",
            reddit_title: "Reddit 散户讨论舆情",
            sig_oversold: "超卖突破 (RSI < 30)",
            sig_double_bottom: "双底构筑",
            sig_wedge_down: "下降楔形",
            sig_triangle_ascending: "上升三角形",
            sig_top_gainers: "最大涨幅",
            sig_new_high: "创历史新高",
            sig_pullback: "均线回调 (Low Risk)",
            sig_breakout_candidate: "放量突破候选",
            sig_quality_compounder: "高质量复利股",
            opt_top_owner: "大股东交易排行",
            opt_latest: "最新交易快讯",
            opt_top_week: "本周大额排行",
            th_rank: "排名",
            th_ticker: "代码",
            th_name: "公司名称",
            th_relation: "交易人职位",
            th_date: "交易日期",
            th_txn: "交易性质",
            th_cost: "交易单价",
            th_shares: "股数",
            th_value: "总金额 ($)",
            th_total_shares: "持股总量",
            th_sec_form: "备案申报",
            th_mentions: "提及次数",
            th_upvotes: "点赞数",
            th_trend: "24H 趋势",
            metric_stocks: "成份股数",
            metric_mcap: "行业总市值",
            metric_recom: "买入评级",
            metric_avg_change: "平均涨跌",
            modal_mcap: "市值",
            modal_pe: "市盈率 P/E",
            modal_sfloat: "空头占比",
            modal_rsi: "RSI 指标 (14)",
            modal_roe: "净资产收益率 ROE",
            modal_debt_eq: "资产负债率 Debt/Eq",
            modal_dividend: "股息率 Dividend",
            modal_peg: "PEG 指标",
            modal_profit_margin: "净利率 Profit Margin",
            modal_target_price: "目标价 Target Price",
            modal_price: "当前价",
            modal_change: "今日变动",
            modal_profile: "公司简介",
            modal_peers: "同板块股票 Peers",
            modal_etfs: "持股主要 ETF",
            modal_chart: "日线 K 线图 (技术分析)",
            modal_tv: "在 TradingView 中查看",
            modal_news: "最新财经新闻",
            sort_mcap: "市值排行",
            sort_change: "涨跌排行",
            sort_price: "股价排行",
            sort_ticker: "代码首字母",
            mcap_all: "全部市值",
            mcap_large: "大盘 (>$100亿)",
            mcap_mid: "中盘 ($20亿-$100亿)",
            mcap_small: "小盘 ($3亿-$20亿)",
            mcap_micro: "微盘 (<$3亿)",
            
            // Dynamic content
            loading_opps: "正在加载选股列表...",
            no_opps: "当前该信号下无匹配的股票。",
            err_opps: "错误：无法从 API 获取股票数据。",
            loading_insider: "正在加载高管交易流...",
            no_insider: "未找到交易记录。",
            err_insider: "错误：无法加载交易记录。",
            loading_sectors: "正在加载板块热力图...",
            err_sectors: "错误：无法加载板块表现矩阵。",
            loading_reddit: "正在加载 Reddit 散户热度...",
            err_reddit: "错误：无法加载 Reddit 散户舆情。",
            txn_buy: "买入",
            txn_sell: "卖出",
            modal_loading_company: "正在加载公司基本面...",
            modal_loading_desc: "正在下载公司简介...",
            modal_no_desc: "暂无公司简介数据。",
            modal_no_peers: "暂无同业股票推荐。",
            modal_no_etfs: "暂无持股 ETF 记录。",
            modal_loading_news: "正在加载新闻报道。",
            modal_no_news: "暂无相关新闻报道。",
            modal_err_company: "加载公司数据错误",
            modal_err_desc: "无法从接口下载公司简介描述。",
            
            tab_confluences: "智能共振",
            confluences_title: "智能多重共振选股",
            confluences_subtitle: "自动挖掘在技术面、机构资金（放量）、高管增持及散户讨论度多维度产生共振的高胜率股票。",
            sig_unusual_volume: "异常放量",
            sig_high_short_interest: "高空头占比",
            sig_top_losers: "最大跌幅",
            sig_most_active: "最活跃交易",
            sig_most_volatile: "最高波动",
            sig_upgrades: "分析师上调",
            sig_downgrades: "分析师下调",
            sig_earnings_before: "盘前财报",
            sig_earnings_after: "盘后财报",
            sig_recent_insider_buying: "近期高管增持",
            chart_static: "静态走势图",
            chart_tv: "TradingView 动态图",
            loading_confluences: "正在挖掘多维共振股票...",
            no_confluences: "当前未发现符合共振筛选标准的股票。",
            err_confluences: "错误：无法加载智能共振选股数据。",
            confluence_cache_empty: "智能共振选股缓存为空。请运行数据同步以生成共振推荐列表。",
            modal_score_breakdown: "多维共振得分拆解",
            breakdown_tech: "技术形态结构",
            breakdown_fund: "基本面与内部人",
            breakdown_sent: "市场情绪与资金流",
            sector_industries_title: "板块细分行业表现",
            sector_top_opportunities: "板块内共振机会个股",
            industry_name: "细分行业",
            industry_change: "今日涨跌",
            industry_stocks: "成份股数",
            wsb_calendar_title: "WSB 重要事件日历",
            reddit_trending_title: "ApeWisdom 散户热度榜",
            th_calendar_date: "日期",
            th_calendar_event: "事件",
            th_calendar_focus: "社区关注点",
            loading_wsb_calendar: "正在加载 WSB 重要事件日历...",
            err_wsb_calendar: "错误：无法加载 WSB 重要事件日历。",
            data_fresh: "实时",
            data_stale: "可能过期",
            data_age_min: "分钟前",
            data_age_hour: "小时前",
            refresh_btn: "刷新",
            tab_watchlist: "自选股",
            watchlist_title: "我的自选股",
            watchlist_subtitle: "您收藏的关注标的。数据存储在本地浏览器中。",
            watchlist_empty: "暂无收藏。点击任意股票卡片上的 ★ 按钮即可添加。",
            watchlist_remove: "移除",
            watchlist_note_placeholder: "添加备注...",
            tab_turbulence: "风险雷达",
            turb_title: "美股风险雷达与大类资产湍流指数",
            turb_subtitle: "基于 Kritzman-Li (2010) 马氏距离跨资产协方差模型，检测大盘高位麻痹期与系统性风险。",
            turb_current_state: "风险状态等级",
            turb_pos_size: "最优推荐仓位",
            turb_checklist: "Danger Zone 预警三联灯",
            turb_cond_dist: "1. 跨资产阻尼指数突破警戒线",
            turb_cond_spx: "2. 标普500指数处于50日均线上方",
            turb_cond_vix: "3. VIX波动率低于25 (无恐慌)",
            turb_state_normal_desc: "跨资产联动模式正常。未检测到明显的系统性结构威胁。",
            turb_state_elevated_desc: "跨资产协方差异常。联动结构偏离正常态，结构性风险正在蓄积。",
            turb_state_high_desc: "Danger Zone 预警信号已激活！股价高位但底层协方差已高度异常，市场进入麻痹窗口。",
            turb_state_critical_desc: "极端风险警戒！底层大类资产联动结构正发生极其罕见的剧烈断裂。",
            turb_pos_desc: "根据全市场系统性压力指标，动态调整大盘权益与对冲防御类资产的分配比率。",
            turb_chart_title: "历史湍流指数与标普500 (SPY) 价格走势对比",
            turb_verdict_loading: "正在验证三联指标达成状态...",
            turb_verdict_active: "🔥 Danger Zone 预警信号已激活！模型发出最高置信度风险警示",
            turb_verdict_inactive: "✓ Danger Zone 预警暂未激活 (三项条件未同时满足)",
            loading_turbulence: "正在抓取并加载市场湍流指标...",
            err_turbulence: "错误：无法从后台拉取市场协方差湍流数据。"
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

        // Re-render from cached data instead of re-fetching
        if (tabLoaded.opportunities) renderOpportunities(currentOppsList);
        if (tabLoaded.confluences) renderConfluences(currentConfluencesList);
        if (tabLoaded.insider) renderInsider(currentInsiderList);
        if (tabLoaded.sectors) renderSectors(currentSectorsList);
        if (tabLoaded.reddit) {
            renderReddit(currentRedditList);
            if (currentWsbCalendar) {
                renderWsbCalendar(currentWsbCalendar);
            }
        }
        if (tabLoaded.watchlist) renderWatchlist();
        if (tabLoaded.turbulence) loadTurbulence();

        // Reload TradingView widget if modal is open and TradingView chart is active
        const modal = document.getElementById('ticker-modal');
        const tvBtn = document.getElementById('chart-tv-btn');
        if (modal && modal.classList.contains('active') && tvBtn && tvBtn.classList.contains('active')) {
            const currentTicker = document.getElementById('modal-ticker').innerText;
            if (currentTicker) {
                loadTradingViewWidget(currentTicker);
            }
        }
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

    // Ticker Search
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
                } else if (activeTab === 'confluences') {
                    loadConfluences();
                } else if (activeTab === 'insider') {
                    loadInsider();
                } else if (activeTab === 'sectors') {
                    loadSectors();
                } else if (activeTab === 'reddit') {
                    loadReddit();
                } else if (activeTab === 'turbulence') {
                    loadTurbulence();
                } else if (activeTab === 'watchlist') {
                    renderWatchlist();
                    tabLoaded.watchlist = true;
                }
            });
        });
    }

    // Debounced loaders for button click handlers
    const debouncedLoadOpportunities = debounce(() => loadOpportunities(true), 300);
    const debouncedLoadInsider = debounce(() => loadInsider(true), 300);

    // 2. Selectors (Signals & Insider Options)
    function initSelectors() {
        // Signal selectors for Opportunities
        const signalButtons = document.querySelectorAll('.signal-btn');
        signalButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                signalButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                activeSignal = btn.getAttribute('data-signal');
                debouncedLoadOpportunities(); // Force reload (debounced)
            });
        });

        // Option selectors for Insider
        const optionButtons = document.querySelectorAll('.option-btn');
        optionButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                optionButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                activeInsiderOption = btn.getAttribute('data-option');
                debouncedLoadInsider(); // Force reload (debounced)
            });
        });

        // Sort selectors for Opportunities
        const sortButtons = document.querySelectorAll('.sort-btn');
        sortButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const sortField = btn.getAttribute('data-sort');
                if (sortField === activeSortField) {
                    activeSortDirection = activeSortDirection === 'asc' ? 'desc' : 'asc';
                } else {
                    activeSortField = sortField;
                    activeSortDirection = sortField === 'ticker' ? 'asc' : 'desc';
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
                if (iconWrap) {
                    iconWrap.innerHTML = `<i data-lucide="${activeSortDirection === 'asc' ? 'arrow-up-narrow-wide' : 'arrow-down-narrow-wide'}"></i>`;
                }
                
                renderOpportunities(currentOppsList);
            });
        });

        // Market Cap Filter selectors for Opportunities
        const mcapButtonsAll = document.querySelectorAll('.mcap-filter-btn:not([data-context])');
        mcapButtonsAll.forEach(btn => {
            btn.addEventListener('click', () => {
                mcapButtonsAll.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                activeMcapFilter = btn.getAttribute('data-mcap');
                renderOpportunities(currentOppsList);
            });
        });

        // Market Cap Filter selectors for Confluences
        const mcapConfButtons = document.querySelectorAll('.mcap-filter-btn[data-context="confluences"]');
        mcapConfButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                mcapConfButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                activeConfluenceMcapFilter = btn.getAttribute('data-mcap');
                renderConfluences(currentConfluencesList);
            });
        });

        // Close Modal events
        document.querySelector('.close-modal-btn').addEventListener('click', closeModal);
        document.getElementById('ticker-modal').addEventListener('click', (e) => {
            if (e.target.id === 'ticker-modal') closeModal();
        });

        // Close Sector Modal events
        const closeSectorBtn = document.getElementById('close-sector-modal-btn');
        if (closeSectorBtn) {
            closeSectorBtn.addEventListener('click', () => {
                document.getElementById('sector-modal').classList.remove('active');
            });
        }
        document.getElementById('sector-modal').addEventListener('click', (e) => {
            if (e.target.id === 'sector-modal') {
                document.getElementById('sector-modal').classList.remove('active');
            }
        });

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
                        const newKey = prompt(activeLang === 'zh' ? '请输入同步 API Key:' : 'Please enter Sync API Key:');
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
                        alert(activeLang === 'zh' ? '同步任务已在后台启动，数据将在 1-2 分钟内更新！' : 'Sync task triggered in the background! Data will update in 1-2 minutes.');
                        setTimeout(() => {
                            window.location.reload();
                        }, 2000);
                    } else {
                        const err = await res.json();
                        alert((activeLang === 'zh' ? '同步失败: ' : 'Sync failed: ') + (err.detail || 'Unknown error'));
                    }
                } catch(e) {
                    alert((activeLang === 'zh' ? '请求失败: ' : 'Request failed: ') + e.message);
                } finally {
                    if (icon) icon.classList.remove('spin-animation');
                }
            });
        }
    }

    // 3. Loading Functions
    function getBadgesHtml(item) {
        let badges = [];
        
        // Relative Volume RVOL
        const rvolVal = parseFloat(item['Rel Volume']);
        if (!isNaN(rvolVal) && rvolVal > 0) {
            const label = activeLang === 'zh' ? `量能 ${rvolVal.toFixed(1)}x` : `RVOL ${rvolVal.toFixed(1)}x`;
            const cssClass = rvolVal > 2.0 ? 'card-badge card-badge-rvol' : 'card-badge';
            const icon = rvolVal > 2.0 ? '<i data-lucide="zap" style="width:10px;height:10px;"></i> ' : '';
            badges.push(`<span class="${cssClass}">${icon}${label}</span>`);
        }

        // Float Short
        const shortFloatStr = String(item['Short Float'] || '');
        if (shortFloatStr && shortFloatStr !== '-') {
            const shortVal = parseFloat(shortFloatStr.replace('%', ''));
            if (!isNaN(shortVal) && shortVal > 0) {
                const label = activeLang === 'zh' ? `空头 ${shortVal.toFixed(1)}%` : `Short ${shortVal.toFixed(1)}%`;
                const isHighShort = shortVal >= 15.0;
                
                // If high short interest and Reddit mentions, show SQUEEZE alert!
                const isRedditPopular = item['Factors'] && item['Factors']['reddit_popular'];
                if (isHighShort && isRedditPopular) {
                    const alertLabel = activeLang === 'zh' ? `🔥 逼空警告 ${shortVal.toFixed(0)}%` : `🔥 SQUEEZE ALERT ${shortVal.toFixed(0)}%`;
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
                const label = activeLang === 'zh' ? `ROE ${roeStr}` : `ROE ${roeStr}`;
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
                const label = activeLang === 'zh' ? `负债 ${debtStr}` : `Debt/Eq ${debtStr}`;
                const cssClass = isLowDebt ? 'card-badge card-badge-debt' : 'card-badge';
                const icon = isLowDebt ? '<i data-lucide="shield" style="width:10px;height:10px;"></i> ' : '';
                badges.push(`<span class="${cssClass}">${icon}${label}</span>`);
            }
        }

        // Strategy Badges (for Confluence tab and signal overlays)
        if (item['Factors']) {
            if (item['Factors']['pullback']) {
                const label = activeLang === 'zh' ? '趋势回调' : 'Pullback Play';
                badges.push(`<span class="card-badge card-badge-strategy-pullback"><i data-lucide="arrow-down-to-line" style="width:10px;height:10px;"></i> ${label}</span>`);
            }
            if (item['Factors']['breakout_candidate']) {
                const label = activeLang === 'zh' ? '放量突破候选' : 'Breakout Candidate';
                badges.push(`<span class="card-badge card-badge-strategy-breakout"><i data-lucide="arrow-up-right" style="width:10px;height:10px;"></i> ${label}</span>`);
            }
            if (item['Factors']['quality_compounder']) {
                const label = activeLang === 'zh' ? '优质复利' : 'Quality Compounder';
                badges.push(`<span class="card-badge card-badge-strategy-quality"><i data-lucide="award" style="width:10px;height:10px;"></i> ${label}</span>`);
            }
            if (item['Factors']['analyst_upgrade']) {
                const label = activeLang === 'zh' ? '分析师上调' : 'Analyst Upgrade';
                badges.push(`<span class="card-badge card-badge-strategy-quality"><i data-lucide="thumbs-up" style="width:10px;height:10px;"></i> ${label}</span>`);
            }
            if (item['Factors']['earnings_catalyst']) {
                const label = activeLang === 'zh' ? '财报催化' : 'Earnings Catalyst';
                badges.push(`<span class="card-badge card-badge-rvol"><i data-lucide="calendar" style="width:10px;height:10px;"></i> ${label}</span>`);
            }
            if (item['Factors']['momentum_leader']) {
                const label = activeLang === 'zh' ? '主力关注' : 'Market Leader';
                badges.push(`<span class="card-badge"><i data-lucide="bar-chart-2" style="width:10px;height:10px;"></i> ${label}</span>`);
            }
            if (item['Factors']['analyst_downgrade']) {
                const label = activeLang === 'zh' ? '⚠️ 分析师下调' : '⚠️ Downgrade';
                badges.push(`<span class="card-badge card-badge-warning"><i data-lucide="trending-down" style="width:10px;height:10px;"></i> ${label}</span>`);
            }
            if (item['Factors']['bearish_momentum']) {
                const label = activeLang === 'zh' ? '⚠️ 跌幅居前' : '⚠️ Top Loser';
                badges.push(`<span class="card-badge card-badge-warning"><i data-lucide="arrow-down" style="width:10px;height:10px;"></i> ${label}</span>`);
            }
            if (item['Factors']['overbought']) {
                const label = activeLang === 'zh' ? '⚠️ 超买' : '⚠️ Overbought';
                badges.push(`<span class="card-badge card-badge-warning"><i data-lucide="alert-triangle" style="width:10px;height:10px;"></i> ${label}</span>`);
            }
        }

        if (badges.length === 0) return '';
        return `<div class="card-badges-row">${badges.join('')}</div>`;
    }

    async function loadConfluences(force = false) {
        if (tabLoaded.confluences && !force) return;
        
        const grid = document.getElementById('confluences-grid');
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
                grid.innerHTML = `<div class="no-data"><i data-lucide="alert-circle"></i> ${translations[activeLang].confluence_cache_empty || payload.message}</div>`;
                lucide.createIcons();
                tabLoaded.confluences = false;
                return;
            }
            currentConfluencesList = payload.data || [];
            
            renderConfluences(currentConfluencesList);
            tabLoaded.confluences = true;
        } catch (error) {
            console.error('Failed to load confluences:', error);
            grid.innerHTML = `<div class="error-msg"><i data-lucide="alert-triangle"></i> ${translations[activeLang].err_confluences}</div>`;
            lucide.createIcons();
        }
    }

    function renderConfluences(list) {
        const grid = document.getElementById('confluences-grid');
        grid.innerHTML = '';
        
        const filteredList = filterByMarketCap(list, activeConfluenceMcapFilter);
        if (!filteredList || filteredList.length === 0) {
            grid.innerHTML = `<div class="no-data"><i data-lucide="info"></i> ${translations[activeLang].no_confluences}</div>`;
            lucide.createIcons();
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
                    dominantPattern = activeLang === 'zh' ? '⚡ 强力突破' : '⚡ Breakout';
                    patternClass = 'pattern-breakout';
                } else if (item['Factors']['pullback']) {
                    dominantPattern = activeLang === 'zh' ? '📉 缩量回踩' : '📉 Pullback';
                    patternClass = 'pattern-pullback';
                } else if (item['Factors']['reversal']) {
                    dominantPattern = activeLang === 'zh' ? '🛡️ 超卖筑底' : '🛡️ Reversal';
                    patternClass = 'pattern-reversal';
                } else if (item['Factors']['breakout_candidate']) {
                    dominantPattern = activeLang === 'zh' ? '⏳ 蓄势突破' : '⏳ Consolidating';
                    patternClass = 'pattern-consolidating';
                }
            }

            // Volume intensity
            let rvolVal = parseFloat(item['Rel Volume']);
            let volumeSparkHtml = '';
            if (!isNaN(rvolVal)) {
                if (rvolVal >= 2.5) {
                    volumeSparkHtml = `<span class="vol-spark vol-spark-heavy" title="RVOL: ${rvolVal}">🔥 ${activeLang === 'zh' ? '爆量' : 'Heavy'}</span>`;
                } else if (rvolVal >= 1.5) {
                    volumeSparkHtml = `<span class="vol-spark vol-spark-active" title="RVOL: ${rvolVal}">⚡ ${activeLang === 'zh' ? '放量' : 'Active'}</span>`;
                } else if (rvolVal < 1.0) {
                    volumeSparkHtml = `<span class="vol-spark vol-spark-quiet" title="RVOL: ${rvolVal}">💤 ${activeLang === 'zh' ? '缩量' : 'Quiet'}</span>`;
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
                        <span class="confluence-reason-title">${activeLang === 'zh' ? '共振因子' : 'Confluence Factors'}</span>
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
                        <button class="watchlist-star-btn ${isInWatchlist(item['Ticker']) ? 'active' : ''}" data-ticker="${escapeHtml(item['Ticker'])}" title="Add to watchlist" style="margin-left: 6px;"><i data-lucide="star" style="width:12px;height:12px;"></i></button>
                        <div class="card-company" style="margin: 4px 0 0 0; white-space: normal; overflow: visible;">${escapeHtml(item['Company']) || '-'}</div>
                        <div class="card-tech-subrow" style="margin-top: 6px; display: flex; gap: 6px; flex-wrap: wrap;">
                            ${dominantPattern ? `<span class="pattern-badge ${patternClass}">${dominantPattern}</span>` : ''}
                            ${volumeSparkHtml}
                        </div>
                    </div>
                    <div style="display: flex; gap: 12px; align-items: flex-start;">
                        <div class="tech-score-wrap">
                            <span class="tech-score-indicator ${techScoreClass}">${item['TechScore'] || 0}</span>
                            <span class="confluence-score-label">${activeLang === 'zh' ? '技术评分' : 'Tech Score'}</span>
                        </div>
                        <div class="confluence-score-wrap">
                            <span class="confluence-score-indicator ${scoreClass}">${item['Score']}</span>
                            <span class="confluence-score-label">${activeLang === 'zh' ? '共振评分' : 'Match Score'}</span>
                        </div>
                    </div>
                </div>
                
                ${badgesHtml}

                <div class="card-footer" style="margin-top: 10px;">
                    <div class="card-footer-item">
                        <span class="item-label">${activeLang === 'zh' ? '最新价' : 'Price'}</span>
                        <span class="item-value font-data">$${escapeHtml(item['Price']) || '-'}</span>
                    </div>
                    <div class="card-footer-item">
                        <span class="item-label">${activeLang === 'zh' ? '变动' : 'Change'}</span>
                        <span class="item-value ${changeClass}">${changeText}</span>
                    </div>
                    <div class="card-footer-item">
                        <span class="item-label">${activeLang === 'zh' ? '市盈率' : 'P/E'}</span>
                        <span class="item-value">${escapeHtml(item['P/E']) || '-'}</span>
                    </div>
                    <div class="card-footer-item">
                        <span class="item-label">${activeLang === 'zh' ? '市值' : 'Market Cap'}</span>
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

        lucide.createIcons();
    }

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
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const payload = await res.json();
            updateTimestamp(payload);
            currentOppsList = payload.data || [];
            
            renderOpportunities(currentOppsList);
            tabLoaded.opportunities = true;
        } catch (error) {
            console.error('Failed to load opportunities:', error);
            grid.innerHTML = `<div class="error-msg"><i data-lucide="alert-triangle"></i> ${translations[activeLang].err_opps}</div>`;
            lucide.createIcons();
        }
    }

    function renderOpportunities(list) {
        const grid = document.getElementById('opps-grid');
        grid.innerHTML = '';
        
        const filteredList = filterByMarketCap(list, activeMcapFilter);
        if (!filteredList || filteredList.length === 0) {
            grid.innerHTML = `<div class="no-data"><i data-lucide="info"></i> ${translations[activeLang].no_opps}</div>`;
            lucide.createIcons();
            return;
        }
        
        const sortedList = sortData(filteredList, activeSortField, activeSortDirection);

        sortedList.forEach(item => {
            const card = document.createElement('div');
            card.className = 'opp-card';
            
            const { formatted: changeText, isBullish } = parseChange(item['Change']);
            const changeClass = isBullish ? 'bullish' : 'bearish';

            const badgesHtml = getBadgesHtml(item);
            card.innerHTML = `
                <div class="card-header">
                    <span class="card-ticker">${escapeHtml(item['Ticker']) || '-'}</span>
                    <div style="display:flex;align-items:center;gap:6px;">
                        <button class="watchlist-star-btn ${isInWatchlist(item['Ticker']) ? 'active' : ''}" data-ticker="${escapeHtml(item['Ticker'])}" title="Add to watchlist">
                            <i data-lucide="star" style="width:14px;height:14px;"></i>
                        </button>
                        <span class="card-change ${changeClass}">${changeText}</span>
                    </div>
                </div>
                <div class="card-company">${escapeHtml(item['Company']) || '-'}</div>
                ${badgesHtml}
                <div class="card-footer">
                    <div class="card-footer-item">
                        <span class="item-label">${activeLang === 'zh' ? '行业' : 'Industry'}</span>
                        <span class="item-value" title="${escapeHtml(item['Industry']) || '-'}">${escapeHtml(item['Industry']) || '-'}</span>
                    </div>
                    <div class="card-footer-item">
                        <span class="item-label">${activeLang === 'zh' ? '市值' : 'Market Cap'}</span>
                        <span class="item-value">${formatMarketCap(item['Market Cap'])}</span>
                    </div>
                    <div class="card-footer-item">
                        <span class="item-label">${activeLang === 'zh' ? '最新价' : 'Price'}</span>
                        <span class="item-value">${escapeHtml(item['Price']) || '-'}</span>
                    </div>
                    <div class="card-footer-item">
                        <span class="item-label">${activeLang === 'zh' ? '市盈率' : 'P/E'}</span>
                        <span class="item-value">${escapeHtml(item['P/E']) || '-'}</span>
                    </div>
                </div>
            `;

            // Card click loads detail sheet
            card.addEventListener('click', () => {
                openModal(item['Ticker']);
            });

            const starBtn = card.querySelector('.watchlist-star-btn');
            if (starBtn) {
                starBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    toggleWatchlist(item['Ticker'], item['Company'], item['Sector'], item['Industry']);
                });
            }
            grid.appendChild(card);
        });

        lucide.createIcons();
    }

    async function loadInsider(force = false) {
        if (tabLoaded.insider && !force) return;

        const tbody = document.getElementById('insider-table-body');
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted);">${translations[activeLang].loading_insider}</td></tr>`;

        try {
            const res = await fetch(`${API_BASE}/api/insiders?option=${encodeURIComponent(activeInsiderOption)}`);
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const payload = await res.json();
            updateTimestamp(payload);
            currentInsiderList = payload.data || [];
            renderInsider(currentInsiderList);
            tabLoaded.insider = true;
        } catch (error) {
            console.error('Failed to load insider:', error);
            tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--bearish);">${translations[activeLang].err_insider}</td></tr>`;
        }
    }

    function renderInsider(list) {
        const tbody = document.getElementById('insider-table-body');
        tbody.innerHTML = '';
        if (!list || list.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" style="text-align: center;">${translations[activeLang].no_insider}</td></tr>`;
            return;
        }

        list.forEach(item => {
            const tr = document.createElement('tr');
            const rawVal = item['Value ($)'] || 0;
            
            // Format transaction Type (Buy / Sell)
            const txnLower = (item['Transaction'] || '').toLowerCase();
            const isBuy = txnLower.includes('buy') || txnLower.includes('exercise') || txnLower.includes('purchase');
            const txnText = isBuy ? translations[activeLang].txn_buy : translations[activeLang].txn_sell;
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

            // Clicking rows opens ticker details modal
            tr.addEventListener('click', (e) => {
                if (e.target.tagName !== 'A' && !e.target.closest('a')) {
                    openModal(item['Ticker']);
                }
            });
            tbody.appendChild(tr);
        });

        lucide.createIcons();
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
                if (activeLang === 'zh') {
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
                const ratioText = activeLang === 'zh' 
                    ? `${upCount} 板块上涨 / ${downCount} 下跌` 
                    : `${upCount} Up / ${downCount} Down`;

                summaryContainer.innerHTML = `
                    <div class="summary-chip">
                        <span class="summary-chip-title">${activeLang === 'zh' ? '今日最强板块' : 'Top Performing Sector'}</span>
                        <span class="summary-chip-val" style="color: var(--positive);">${strongName}</span>
                        <span class="summary-chip-sub">${strongChange}</span>
                    </div>
                    <div class="summary-chip">
                        <span class="summary-chip-title">${activeLang === 'zh' ? '今日最弱板块' : 'Worst Performing Sector'}</span>
                        <span class="summary-chip-val" style="color: var(--negative);">${weakName}</span>
                        <span class="summary-chip-sub">${weakChange}</span>
                    </div>
                    <div class="summary-chip">
                        <span class="summary-chip-title">${activeLang === 'zh' ? '板块上涨下跌比' : 'Market Breadth'}</span>
                        <span class="summary-chip-val">${ratioText}</span>
                        <span class="summary-chip-sub">${activeLang === 'zh' ? `共 ${totalSectors} 个板块` : `Total ${totalSectors} Sectors`}</span>
                    </div>
                `;
            }

            currentSectorsList = sortedList;
            renderSectors(currentSectorsList);
            tabLoaded.sectors = true;
        } catch (error) {
            console.error('Failed to load sectors:', error);
            grid.innerHTML = `<div class="error-msg"><i data-lucide="alert-triangle"></i> ${translations[activeLang].err_sectors}</div>`;
            lucide.createIcons();
        }
    }

    function renderSectors(list) {
        const grid = document.getElementById('sectors-grid');
        grid.innerHTML = '';

        if (!list || list.length === 0) return;

        const getSectorName = (name) => {
            if (activeLang === 'zh') {
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
                    <span class="item-label">${translations[activeLang].metric_stocks}</span>
                    <span class="item-value">${item['Stocks'] || '-'}</span>
                </div>
                <div class="sector-metric">
                    <span class="item-label">${translations[activeLang].metric_mcap}</span>
                    <span class="item-value">${formatMarketCap(item['Market Cap'])}</span>
                </div>
                <div class="sector-metric">
                    <span class="item-label">${translations[activeLang].metric_recom}</span>
                    <span class="item-value">${item['Recom'] || '-'}</span>
                </div>
                <div class="sector-metric">
                    <span class="item-label">${translations[activeLang].metric_avg_change}</span>
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

    async function loadReddit(force = false) {
        // Trigger calendar loading in parallel
        loadWsbCalendar(force);

        if (tabLoaded.reddit && !force) return;

        const tbody = document.getElementById('reddit-table-body');
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">${translations[activeLang].loading_reddit}</td></tr>`;

        try {
            const res = await fetch(`${API_BASE}/api/reddit`);
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const payload = await res.json();
            const list = payload.data || [];

            currentRedditList = list;
            renderReddit(currentRedditList);
            tabLoaded.reddit = true;
        } catch (error) {
            console.error('Failed to load Reddit sentiment:', error);
            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--negative);">${translations[activeLang].err_reddit}</td></tr>`;
        }
    }

    function renderReddit(list) {
        const tbody = document.getElementById('reddit-table-body');
        tbody.innerHTML = '';
        if (!list || list.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center;">${activeLang === 'zh' ? '暂无数据。' : 'No data found.'}</td></tr>`;
            return;
        }

        // Slice to show top 50
        const displayList = list.slice(0, 50);

        displayList.forEach(item => {
            const tr = document.createElement('tr');
            
            const rank = item['rank'] || '-';
            const ticker = item['ticker'] || '-';
            const name = item['name'] || '-';
            const mentions = item['mentions'] || 0;
            const upvotes = item['upvotes'] || 0;
            const rank24h = item['rank_24h_ago'];

            let trendText = '-';
            let trendClass = 'trend-neutral';
            let trendIcon = 'minus';
            
            if (rank24h !== undefined && rank24h !== null && rank24h !== '') {
                const rToday = parseInt(rank);
                const r24h = parseInt(rank24h);
                if (!isNaN(rToday) && !isNaN(r24h)) {
                    const diff = r24h - rToday; // if today is 1 and 24h ago was 4, diff is +3 (climbed)
                    if (diff > 0) {
                        trendText = `+${diff}`;
                        trendClass = 'trend-up';
                        trendIcon = 'arrow-up';
                    } else if (diff < 0) {
                        trendText = `${diff}`;
                        trendClass = 'trend-down';
                        trendIcon = 'arrow-down';
                    }
                }
            }

            tr.innerHTML = `
                <td class="table-rank">${escapeHtml(rank)}</td>
                <td class="table-ticker">${escapeHtml(ticker)}</td>
                <td>${escapeHtml(name)}</td>
                <td>${formatNumber(mentions)}</td>
                <td>${formatNumber(upvotes)}</td>
                <td class="${trendClass}">
                    <span class="trend-badge">
                        <i data-lucide="${trendIcon}" style="width:12px; height:12px; display:inline-block; vertical-align:middle; margin-right:2px;"></i>
                        ${trendText}
                    </span>
                </td>
            `;

            // Clicking rows opens ticker details modal
            tr.addEventListener('click', () => {
                openModal(ticker);
            });
            tbody.appendChild(tr);
        });

        lucide.createIcons();
    }

    // Watchlist Management
    function toggleWatchlist(ticker, company, sector, industry) {
        ticker = ticker.toUpperCase();
        if (watchlist[ticker]) {
            delete watchlist[ticker];
        } else {
            watchlist[ticker] = {
                company: company || '',
                sector: sector || '',
                industry: industry || '',
                note: '',
                addedAt: new Date().toISOString()
            };
        }
        localStorage.setItem('watchlist', JSON.stringify(watchlist));
        // Update star icons on visible cards
        document.querySelectorAll('.watchlist-star-btn').forEach(btn => {
            const btnTicker = btn.getAttribute('data-ticker');
            if (btnTicker === ticker) {
                btn.classList.toggle('active', !!watchlist[ticker]);
            }
        });
        // Re-render watchlist tab if it was loaded
        if (tabLoaded.watchlist) renderWatchlist();
    }

    function isInWatchlist(ticker) {
        return !!watchlist[ticker.toUpperCase()];
    }

    function updateWatchlistNote(ticker, note) {
        ticker = ticker.toUpperCase();
        if (watchlist[ticker]) {
            watchlist[ticker].note = note;
            localStorage.setItem('watchlist', JSON.stringify(watchlist));
        }
    }

    function renderWatchlist() {
        const grid = document.getElementById('watchlist-grid');
        if (!grid) return;
        grid.innerHTML = '';

        const tickers = Object.keys(watchlist);
        if (tickers.length === 0) {
            grid.innerHTML = `<div class="no-data"><i data-lucide="star"></i> ${translations[activeLang].watchlist_empty}</div>`;
            lucide.createIcons();
            return;
        }

        tickers.forEach(ticker => {
            const info = watchlist[ticker];
            const card = document.createElement('div');
            card.className = 'opp-card watchlist-card';

            const addedDate = info.addedAt ? new Date(info.addedAt).toLocaleDateString() : '';

            card.innerHTML = `
                <div class="card-header">
                    <span class="card-ticker">${escapeHtml(ticker)}</span>
                    <button class="watchlist-remove-btn" data-ticker="${escapeHtml(ticker)}" title="${translations[activeLang].watchlist_remove}">
                        <i data-lucide="x" style="width:14px;height:14px;"></i>
                    </button>
                </div>
                <div class="card-company">${escapeHtml(info.company || '-')}</div>
                <div class="card-footer" style="margin-top: 6px;">
                    <div class="card-footer-item">
                        <span class="item-label">${activeLang === 'zh' ? '板块' : 'Sector'}</span>
                        <span class="item-value">${escapeHtml(info.sector || '-')}</span>
                    </div>
                    <div class="card-footer-item">
                        <span class="item-label">${activeLang === 'zh' ? '行业' : 'Industry'}</span>
                        <span class="item-value">${escapeHtml(info.industry || '-')}</span>
                    </div>
                    <div class="card-footer-item">
                        <span class="item-label">${activeLang === 'zh' ? '添加日期' : 'Added'}</span>
                        <span class="item-value">${addedDate}</span>
                    </div>
                </div>
                <div class="watchlist-note-wrap">
                    <input type="text" class="watchlist-note-input" 
                        placeholder="${translations[activeLang].watchlist_note_placeholder}" 
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
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleWatchlist(ticker);
            });

            // Note input
            const noteInput = card.querySelector('.watchlist-note-input');
            noteInput.addEventListener('click', (e) => e.stopPropagation());
            noteInput.addEventListener('change', (e) => {
                updateWatchlistNote(ticker, e.target.value);
            });

            grid.appendChild(card);
        });

        lucide.createIcons();
    }

    async function loadWsbCalendar(force = false) {
        if (currentWsbCalendar && !force) return;

        const tbody = document.getElementById('wsb-calendar-table-body');
        tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">${translations[activeLang].loading_wsb_calendar}</td></tr>`;

        try {
            const res = await fetch(`${API_BASE}/api/wsb-calendar`);
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const payload = await res.json();
            currentWsbCalendar = payload.data || { zh: [], en: [] };
            renderWsbCalendar(currentWsbCalendar);
        } catch (error) {
            console.error('Failed to load WSB calendar:', error);
            tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--negative);">${translations[activeLang].err_wsb_calendar}</td></tr>`;
        }
    }

    function renderWsbCalendar(calendar) {
        const tbody = document.getElementById('wsb-calendar-table-body');
        tbody.innerHTML = '';

        const list = calendar[activeLang] || [];
        if (list.length === 0) {
            tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No calendar events found. / 暂无重要事件。</td></tr>`;
            return;
        }

        list.forEach(item => {
            const tr = document.createElement('tr');

            const dateTd = document.createElement('td');
            dateTd.className = 'font-mono';
            dateTd.style.fontWeight = '600';
            dateTd.style.color = 'var(--primary)';
            dateTd.textContent = item.date || '-';

            const eventTd = document.createElement('td');
            eventTd.style.fontWeight = '500';
            eventTd.textContent = item.event || '-';

            const focusTd = document.createElement('td');
            focusTd.style.color = 'var(--text-muted)';
            focusTd.textContent = item.focus || '-';

            tr.appendChild(dateTd);
            tr.appendChild(eventTd);
            tr.appendChild(focusTd);

            tbody.appendChild(tr);
        });
    }

    async function loadTurbulence() {
        const tabEl = document.getElementById('turbulence-tab');
        if (!tabEl) return;
        
        tabLoaded.turbulence = true;
        
        // Show loading state by writing it to the verdict text
        const verdictText = document.getElementById('turb-verdict-text');
        if (verdictText) verdictText.textContent = translations[activeLang].loading_turbulence;
        
        try {
            const res = await fetch(`${API_BASE}/api/turbulence`);
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const payload = await res.json();
            currentTurbulenceData = payload;
            renderTurbulence(payload);
        } catch (error) {
            console.error('Failed to load turbulence:', error);
            if (verdictText) verdictText.textContent = translations[activeLang].err_turbulence;
            const stateText = document.getElementById('turb-state-text');
            if (stateText) stateText.textContent = 'ERROR';
        }
    }

    function renderTurbulence(payload) {
        if (!payload || payload.status === 'empty') {
            const verdictText = document.getElementById('turb-verdict-text');
            if (verdictText) verdictText.textContent = translations[activeLang].confluence_cache_empty || 'Cache empty. Please run sync.';
            return;
        }
        
        const status = payload.status;
        const latestTurb = status.turbulence;
        const latestSpx = status.spx;
        const latestVix = status.vix;
        
        // 1. Update Regime Card
        const stateText = document.getElementById('turb-state-text');
        const stateDot = document.getElementById('turb-state-dot');
        const stateDesc = document.getElementById('turb-state-desc');
        
        if (stateText) {
            stateText.textContent = status.state;
            stateText.style.color = status.state_color;
        }
        if (stateDot) {
            stateDot.className = 'turb-state-dot';
            stateDot.style.backgroundColor = status.state_color;
            if (status.state === 'CRITICAL' || status.state === 'HIGH RISK') {
                stateDot.classList.add('turb-state-dot-pulse');
            }
        }
        if (stateDesc) {
            let descKey = 'turb_state_normal_desc';
            if (status.state === 'ELEVATED RISK') descKey = 'turb_state_elevated_desc';
            else if (status.state === 'HIGH RISK') descKey = 'turb_state_high_desc';
            else if (status.state === 'CRITICAL') descKey = 'turb_state_critical_desc';
            stateDesc.textContent = translations[activeLang][descKey] || '';
        }
        
        // 2. Update Position Card
        const posVal = document.getElementById('turb-pos-val');
        const posBar = document.getElementById('turb-pos-bar');
        
        if (posVal) posVal.textContent = status.position_size_pct;
        if (posBar) {
            posBar.style.width = `${status.position_size_pct}%`;
            posBar.style.backgroundColor = status.state_color;
        }
        
        // 3. Update Checklist
        const turbIcon = document.getElementById('check-icon-turb');
        const turbVal = document.getElementById('check-val-turb');
        const spxIcon = document.getElementById('check-icon-spx');
        const spxVal = document.getElementById('check-val-spx');
        const vixIcon = document.getElementById('check-icon-vix');
        const vixVal = document.getElementById('check-val-vix');
        
        const turbMet = latestTurb.slow > latestTurb.warning_threshold;
        const spxMet = latestSpx.above_sma50;
        const vixMet = latestVix.below_25;
        
        if (turbVal) turbVal.textContent = `${latestTurb.slow.toFixed(2)} (vs ${latestTurb.warning_threshold.toFixed(2)})`;
        if (turbIcon) {
            turbIcon.outerHTML = turbMet 
                ? `<i id="check-icon-turb" class="check-icon warn-met" data-lucide="alert-triangle"></i>`
                : `<i id="check-icon-turb" class="check-icon unmet" data-lucide="circle"></i>`;
        }
        
        if (spxVal) spxVal.textContent = `${latestSpx.level.toFixed(1)} (vs SMA50 ${latestSpx.sma50.toFixed(1)})`;
        if (spxIcon) {
            spxIcon.outerHTML = spxMet 
                ? `<i id="check-icon-spx" class="check-icon met" data-lucide="check-circle-2"></i>`
                : `<i id="check-icon-spx" class="check-icon unmet" data-lucide="circle"></i>`;
        }
        
        if (vixVal) vixVal.textContent = `${latestVix.level.toFixed(2)} (vs 25.0)`;
        if (vixIcon) {
            vixIcon.outerHTML = vixMet 
                ? `<i id="check-icon-vix" class="check-icon met" data-lucide="check-circle-2"></i>`
                : `<i id="check-icon-vix" class="check-icon unmet" data-lucide="circle"></i>`;
        }
        
        // Verdict Banner
        const verdictBanner = document.getElementById('turb-verdict-banner');
        const verdictText = document.getElementById('turb-verdict-text');
        
        if (verdictBanner && verdictText) {
            if (status.divergence.active) {
                verdictBanner.className = 'verdict-banner active';
                verdictText.textContent = translations[activeLang].turb_verdict_active;
            } else {
                verdictBanner.className = 'verdict-banner';
                verdictText.textContent = translations[activeLang].turb_verdict_inactive;
            }
        }
        
        lucide.createIcons(); // Instantly compile dynamic Lucide tags
        
        // 4. Render Chart
        renderTurbulenceChart(payload.chart_series);
    }

    function renderTurbulenceChart(series) {
        const canvas = document.getElementById('turbulence-chart');
        if (!canvas) return;
        
        // Destroy existing instance to avoid duplicate overlays
        if (turbulenceChartInstance) {
            turbulenceChartInstance.destroy();
        }
        
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        const textColor = isDark ? '#a0aec0' : '#4a5568';
        const gridColor = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)';
        
        const labels = series.map(x => x.date);
        const turbSlow = series.map(x => x.turb_slow);
        const turbFast = series.map(x => x.turb_fast);
        const slowWarn = series.map(x => x.slow_warn);
        const slowExtreme = series.map(x => x.slow_extreme);
        const spxPrices = series.map(x => x.spx);
        
        const ctx = canvas.getContext('2d');
        turbulenceChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: activeLang === 'zh' ? '慢速湍流指数 (5d EMA)' : 'Slow Turbulence (5d EMA)',
                        data: turbSlow,
                        borderColor: isDark ? '#d4c196' : '#c5b086', // Brand gold matching ledger
                        borderWidth: 2,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        yAxisID: 'y'
                    },
                    {
                        label: activeLang === 'zh' ? '快速湍流指数 (2d EMA)' : 'Fast Turbulence (2d EMA)',
                        data: turbFast,
                        borderColor: isDark ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.15)',
                        borderWidth: 1,
                        pointRadius: 0,
                        pointHoverRadius: 3,
                        yAxisID: 'y'
                    },
                    {
                        label: activeLang === 'zh' ? '警戒阈值 (95%)' : 'Warning Threshold (95%)',
                        data: slowWarn,
                        borderColor: '#ff9f1c', // Vibrant warning orange
                        borderWidth: 1.5,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        yAxisID: 'y'
                    },
                    {
                        label: activeLang === 'zh' ? '极端风险阈值 (99%)' : 'Extreme Threshold (99%)',
                        data: slowExtreme,
                        borderColor: '#e71d36', // Bright red
                        borderWidth: 1.5,
                        borderDash: [3, 3],
                        pointRadius: 0,
                        yAxisID: 'y'
                    },
                    {
                        label: activeLang === 'zh' ? '标普500 (SPY)' : 'S&P 500 (SPY)',
                        data: spxPrices,
                        borderColor: isDark ? '#5fa3df' : '#2c70ab', // Blue axis
                        borderWidth: 2,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: textColor,
                            font: {
                                family: 'JetBrains Mono',
                                size: 10
                            },
                            maxTicksLimit: 12
                        }
                    },
                    y: {
                        position: 'left',
                        grid: {
                            color: gridColor
                        },
                        title: {
                            display: true,
                            text: activeLang === 'zh' ? '湍流指数 (马氏距离)' : 'Turbulence Score',
                            color: textColor,
                            font: {
                                size: 11
                            }
                        },
                        ticks: {
                            color: textColor,
                            font: {
                                family: 'JetBrains Mono',
                                size: 10
                            }
                        }
                    },
                    y1: {
                        position: 'right',
                        grid: {
                            drawOnChartArea: false // prevent grid overlaps
                        },
                        title: {
                            display: true,
                            text: 'SPY Price ($)',
                            color: textColor,
                            font: {
                                size: 11
                            }
                        },
                        ticks: {
                            color: textColor,
                            font: {
                                family: 'JetBrains Mono',
                                size: 10
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: textColor,
                            font: {
                                family: 'var(--font-sans)',
                                size: 11
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: isDark ? '#11192a' : '#ffffff',
                        titleColor: isDark ? '#e3e0d9' : '#151c26',
                        bodyColor: isDark ? '#c4ccd7' : '#394a62',
                        borderColor: 'var(--border)',
                        borderWidth: 1,
                        titleFont: {
                            family: 'var(--font-sans)',
                            weight: 'bold'
                        },
                        bodyFont: {
                            family: 'JetBrains Mono'
                        }
                    }
                }
            }
        });
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
        chartImg.style.opacity = '0';
        chartImg.style.transition = 'opacity 0.2s ease-in-out';
        chartImg.src = `https://finviz.com/chart.ashx?t=${ticker}&ty=c&ta=1&p=d`;
        chartImg.onload = () => {
            chartImg.style.opacity = '1';
        };
        chartImg.onerror = () => {
            chartImg.style.opacity = '1';
        };
        document.getElementById('tv-link').href = `https://www.tradingview.com/symbols/${ticker}`;

        // Reset metrics
        ['mcap', 'pe', 'sfloat', 'rsi', 'price', 'change'].forEach(id => {
            document.getElementById(`m-${id}`).innerText = '-';
        });

        // Preload confluences if not loaded yet
        if (currentConfluencesList.length === 0) {
            try {
                const res = await fetch(`${API_BASE}/api/confluences`);
                if (res.ok) {
                    const payload = await res.json();
                    if (payload.data) {
                        currentConfluencesList = payload.data;
                    }
                }
            } catch (e) {
                console.error("Failed to preload confluences in modal:", e);
            }
        }

        // Check for score breakdown
        const confluenceItem = currentConfluencesList.find(x => x.Ticker === ticker);
        const breakdownPanel = document.getElementById('score-breakdown-panel');
        if (breakdownPanel) {
            if (confluenceItem && confluenceItem.ScoreBreakdown) {
                breakdownPanel.style.display = 'block';
                const techScore = confluenceItem.ScoreBreakdown.tech || 0;
                const fundScore = confluenceItem.ScoreBreakdown.fund || 0;
                const sentScore = confluenceItem.ScoreBreakdown.sent || 0;

                document.getElementById('breakdown-tech-val').innerText = `${techScore} / 40`;
                document.getElementById('breakdown-tech-bar').style.width = `${(techScore / 40) * 100}%`;

                document.getElementById('breakdown-fund-val').innerText = `${fundScore} / 35`;
                document.getElementById('breakdown-fund-bar').style.width = `${(fundScore / 35) * 100}%`;

                document.getElementById('breakdown-sent-val').innerText = `${sentScore} / 25`;
                document.getElementById('breakdown-sent-bar').style.width = `${(sentScore / 25) * 100}%`;
            } else {
                breakdownPanel.style.display = 'none';
            }
        }

        try {
            let stockData;
            
            // Check cache
            if (stockCache[ticker]) {
                stockData = stockCache[ticker];
            } else {
                const res = await fetch(`${API_BASE}/api/stock/${ticker}`);
                if (!res.ok) throw new Error(`API error: ${res.status}`);
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
                sectorVal = sectorZhMapping[sectorVal] || sectorVal;
            }
            
            document.getElementById('modal-sector').innerText = sectorVal;
            document.getElementById('modal-industry').innerText = industryVal;
            document.getElementById('modal-desc').innerText = stockData.description || translations[activeLang].modal_no_desc;

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

    // Escape key to close modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
            const sectorModal = document.getElementById('sector-modal');
            if (sectorModal) sectorModal.classList.remove('active');
        }
    });

    // 5. Utility Helper Functions
    function formatNumber(num) {
        if (!num || isNaN(num)) return num;
        return parseFloat(num).toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    function formatMarketCap(val) {
        if (val === undefined || val === null || val === '') return '-';
        
        let num = typeof val === 'number' ? val : parseFloat(val);
        if (isNaN(num)) return val;
        
        let strVal = String(val).trim();
        if (/[a-zA-Z%]$/.test(strVal)) return val;

        if (activeLang === 'zh') {
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

    function filterByMarketCap(list, filter) {
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

    function sortData(list, field, direction) {
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

    function loadTradingViewWidget(ticker) {
        const container = document.getElementById('tradingview-chart-container');
        if (!container) return;
        container.innerHTML = `<div id="tradingview_widget_instance" style="width:100%; height:100%;"></div>`;

        const renderWidget = () => {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            new TradingView.widget({
                width: "100%",
                height: "100%",
                symbol: ticker,
                interval: "D",
                timezone: "Etc/UTC",
                theme: currentTheme,
                style: "1",
                locale: activeLang === 'zh' ? "zh_CN" : "en",
                toolbar_bg: currentTheme === 'dark' ? "#1e1e1e" : "#f1f3f6",
                enable_publishing: false,
                hide_side_toolbar: false,
                allow_symbol_change: false,
                container_id: "tradingview_widget_instance"
            });
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

    function getSectorZhName(name) {
        return sectorZhMapping[name] || name;
    }

    async function openSectorModal(sectorName) {
        if (!sectorName) return;

        const modal = document.getElementById('sector-modal');
        if (!modal) return;
        modal.classList.add('active');

        // Set loading states
        document.getElementById('sector-modal-title').innerText = activeLang === 'zh' ? getSectorZhName(sectorName) : sectorName;
        document.getElementById('sector-modal-change').innerText = '...';
        document.getElementById('sector-modal-change').className = 'change-badge';
        document.getElementById('sector-modal-industries-list').innerHTML = `
            <tr><td colspan="3" style="text-align: center; color: var(--text-muted);">${translations[activeLang].loading_sectors}</td></tr>
        `;
        document.getElementById('sector-modal-stocks-grid').innerHTML = `
            <div style="text-align: center; color: var(--text-muted); padding: 20px;">${translations[activeLang].loading_confluences}</div>
        `;

        try {
            const res = await fetch(`${API_BASE}/api/sectors/${encodeURIComponent(sectorName)}`);
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const payload = await res.json();
            
            // Populate Sector Name & Change Badge
            const metrics = payload.metrics || {};
            const { formatted: changeText, isBullish } = parseChange(metrics['Change']);
            const changeBadge = document.getElementById('sector-modal-change');
            changeBadge.innerText = changeText;
            changeBadge.className = 'change-badge ' + (isBullish ? 'positive' : 'negative');
            
            // Populate industries performance
            const industriesList = document.getElementById('sector-modal-industries-list');
            industriesList.innerHTML = '';
            const industries = payload.industries || [];
            
            if (industries.length === 0) {
                industriesList.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No industries found.</td></tr>`;
            } else {
                industries.forEach(ind => {
                    const tr = document.createElement('tr');
                    const indChange = parseChange(ind['Change']);
                    tr.innerHTML = `
                        <td>${escapeHtml(ind['Name'])}</td>
                        <td style="text-align: right; color: var(--${indChange.isBullish ? 'positive' : 'negative'}); font-weight: 600;">${indChange.formatted}</td>
                        <td style="text-align: right;">${ind['Stocks'] || 0}</td>
                    `;
                    industriesList.appendChild(tr);
                });
            }
            
            // Populate stocks list
            const stocksGrid = document.getElementById('sector-modal-stocks-grid');
            stocksGrid.innerHTML = '';
            const confluences = payload.confluences || [];
            
            if (confluences.length === 0) {
                stocksGrid.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 20px;">${translations[activeLang].no_confluences}</div>`;
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
                                <span class="sector-stock-score-label">${activeLang === 'zh' ? '共振分' : 'Score'}</span>
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
        } catch (e) {
            console.error("Failed to load sector details:", e);
            document.getElementById('sector-modal-industries-list').innerHTML = `
                <tr><td colspan="3" style="text-align: center; color: var(--negative);">${translations[activeLang].err_sectors}</td></tr>
            `;
        }
    }
});
