// State management and API base configuration

export const state = {
    activeTab: 'opportunities',
    activeSignal: 'oversold',
    activeInsiderOption: 'top owner trade',
    activeSortField: 'marketcap',
    activeSortDirection: 'desc',
    activeMcapFilter: 'all',
    activeConfluenceMcapFilter: 'all',
    currentOppsList: [],
    currentInsiderList: [],
    currentSectorsList: [],
    currentRedditList: [],
    currentConfluencesList: [],
    currentWsbCalendar: null,
    currentTurbulenceData: null,
    currentTurbulenceRange: 'all',
    turbulenceChartInstance: null,
    watchlist: JSON.parse(localStorage.getItem('watchlist') || '{}'),
    tabLoaded: {
        opportunities: false,
        confluences: false,
        insider: false,
        sectors: false,
        reddit: false,
        watchlist: false,
        turbulence: false
    },
    stockCache: {},
    lastDataUpdate: null,
    activeLang: localStorage.getItem('lang') || (navigator.language && navigator.language.startsWith('zh') ? 'zh' : 'en')
};

export const API_BASE = window.location.origin;
