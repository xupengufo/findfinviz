import { state, API_BASE } from './state.js';
import { translations, onLanguageChange } from './i18n.js';
import { escapeHtml, parseChange } from './utils.js';

export async function loadTurbulence() {
    const tabEl = document.getElementById('turbulence-tab');
    if (!tabEl) return;
    
    state.tabLoaded.turbulence = true;
    
    // Show loading state by writing it to the verdict text
    const verdictText = document.getElementById('turb-verdict-text');
    if (verdictText) verdictText.textContent = translations[state.activeLang].loading_turbulence;
    
    try {
        const res = await fetch(`${API_BASE}/api/turbulence`);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const payload = await res.json();
        state.currentTurbulenceData = payload;
        renderTurbulence(payload);
    } catch (error) {
        console.error('Failed to load turbulence:', error);
        if (verdictText) verdictText.textContent = translations[state.activeLang].err_turbulence;
        const stateText = document.getElementById('turb-state-text');
        if (stateText) stateText.textContent = 'ERROR';
    }
}

export function renderTurbulence(payload) {
    const lang = state.activeLang;
    const t = translations[lang];

    // Handle no-data / empty cache: show a clear "not synced" state on every card
    // instead of leaving stale loading placeholders or a misleading green NORMAL.
    if (!payload || payload.cache_status === 'no_data' || payload.cache_status === 'empty') {
        const warnMsg = lang === 'zh'
            ? '风险雷达数据尚未同步。请点击右上角 Refresh 拉取最新快照。'
            : 'Risk radar data not yet synced. Tap Refresh (top-right) to fetch the latest snapshot.';

        // Regime card → UNKNOWN (gray), not NORMAL (green)
        const stateText = document.getElementById('turb-state-text');
        const stateDot = document.getElementById('turb-state-dot');
        const stateDesc = document.getElementById('turb-state-desc');
        if (stateText) { stateText.textContent = lang === 'zh' ? '数据未同步' : 'NO DATA'; stateText.style.color = '#9ca3af'; }
        if (stateDot) { stateDot.className = 'turb-state-dot'; stateDot.style.backgroundColor = '#9ca3af'; }
        if (stateDesc) stateDesc.innerHTML = `<span style="color:#9ca3af">${warnMsg}</span>`;

        // Position card → "--"
        const posVal = document.getElementById('turb-pos-val');
        const posBar = document.getElementById('turb-pos-bar');
        if (posVal) posVal.textContent = '--';
        if (posBar) { posBar.style.width = '0%'; posBar.style.backgroundColor = '#9ca3af'; }

        // Probit card → "--"
        const probitVal = document.getElementById('turb-probit-val');
        const probitBar = document.getElementById('turb-probit-bar');
        const probitStatus = document.getElementById('turb-probit-status');
        if (probitVal) probitVal.textContent = '--';
        if (probitBar) { probitBar.style.width = '0%'; probitBar.style.backgroundColor = '#9ca3af'; }
        if (probitStatus) { probitStatus.textContent = lang === 'zh' ? '数据未同步' : 'NO DATA'; probitStatus.style.color = '#9ca3af'; }

        // Macro Liquidity card → "--"
        const liqVal = document.getElementById('macro-liq-val');
        const walclVal = document.getElementById('macro-walcl-val');
        const tgaVal = document.getElementById('macro-tga-val');
        const rrpVal = document.getElementById('macro-rrp-val');
        const liqBadge = document.getElementById('macro-liq-z-badge');
        if (liqVal) liqVal.textContent = '--';
        if (walclVal) walclVal.textContent = '--';
        if (tgaVal) tgaVal.textContent = '--';
        if (rrpVal) rrpVal.textContent = '--';
        if (liqBadge) {
            liqBadge.textContent = 'Z-Score: --';
            liqBadge.style.backgroundColor = 'rgba(156, 163, 175, 0.15)';
            liqBadge.style.color = '#9ca3af';
            liqBadge.style.borderColor = 'rgba(156, 163, 175, 0.35)';
        }

        // Funding card → "--"
        const sofrIorbVal = document.getElementById('macro-sofr-iorb-val');
        const sofrVal = document.getElementById('macro-sofr-val');
        const iorbVal = document.getElementById('macro-iorb-val');
        const steepeningVal = document.getElementById('macro-steepening-val');
        const curveBadge = document.getElementById('macro-curve-badge');
        if (sofrIorbVal) sofrIorbVal.textContent = '--';
        if (sofrVal) sofrVal.textContent = '--';
        if (iorbVal) iorbVal.textContent = '--';
        if (steepeningVal) steepeningVal.textContent = '--';
        if (curveBadge) {
            curveBadge.textContent = 'NO DATA';
            curveBadge.style.backgroundColor = 'rgba(156, 163, 175, 0.15)';
            curveBadge.style.color = '#9ca3af';
            curveBadge.style.borderColor = 'rgba(156, 163, 175, 0.35)';
        }

        // Labor card → "--"
        const laborVal = document.getElementById('macro-labor-val');
        const iursaVal = document.getElementById('macro-iursa-val');
        const icsaVal = document.getElementById('macro-icsa-val');
        const laborBadge = document.getElementById('macro-labor-badge');
        if (laborVal) laborVal.textContent = '--';
        if (iursaVal) iursaVal.textContent = '--';
        if (icsaVal) icsaVal.textContent = '--';
        if (laborBadge) {
            laborBadge.textContent = 'NO DATA';
            laborBadge.style.backgroundColor = 'rgba(156, 163, 175, 0.15)';
            laborBadge.style.color = '#9ca3af';
            laborBadge.style.borderColor = 'rgba(156, 163, 175, 0.35)';
        }

        const verdictText = document.getElementById('turb-verdict-text');
        if (verdictText) verdictText.textContent = warnMsg;
        return;
    }

    const status = payload.status;
    const latestMacro = status.macro_turbulence;
    const latestSector = status.sector_dispersion;
    const latestSpx = status.spx;
    const latestVix = status.vix;
    const latestMove = status.move;
    const latestCredit = status.credit;
    
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
        
        const descText = translations[state.activeLang][descKey] || '';
        
        let flagsHtml = '';
        if (status.state_flags) {
            const activeFlags = [];
            if (status.state_flags.critical) activeFlags.push({ name: state.activeLang === 'zh' ? '极端风险 (CRITICAL)' : 'CRITICAL', color: '#e71d36' });
            if (status.state_flags.high_risk) activeFlags.push({ name: state.activeLang === 'zh' ? '高风险 (HIGH RISK)' : 'HIGH RISK', color: '#d98a2b' });
            if (status.state_flags.elevated) activeFlags.push({ name: state.activeLang === 'zh' ? '预警激活 (ELEVATED)' : 'ELEVATED', color: '#ffbf00' });
            if (status.state_flags.normal && activeFlags.length === 0) activeFlags.push({ name: state.activeLang === 'zh' ? '常态机制 (NORMAL)' : 'NORMAL', color: '#2ec4b6' });
            
            flagsHtml = `<div class="state-flags-row" style="display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap;">` + 
                activeFlags.map(f => `<span style="font-size: 0.65rem; font-weight: 700; font-family: var(--font-mono); padding: 2px 6px; border-radius: 4px; background: ${f.color}15; color: ${f.color}; border: 1px solid ${f.color}35;">${f.name}</span>`).join('') + 
                `</div>`;
        }
        
        stateDesc.innerHTML = `<span>${descText}</span>${flagsHtml}`;
    }
    
    // 2. Update Position Card
    const posVal = document.getElementById('turb-pos-val');
    const posBar = document.getElementById('turb-pos-bar');
    
    if (posVal) posVal.textContent = status.position_size_pct;
    if (posBar) {
        posBar.style.width = `${status.position_size_pct}%`;
        posBar.style.backgroundColor = status.state_color;
    }
    
    // 2.5 Update Probit Card
    const probitVal = document.getElementById('turb-probit-val');
    const probitBar = document.getElementById('turb-probit-bar');
    const probitStatus = document.getElementById('turb-probit-status');
    
    if (status.probit) {
        const probPct = (status.probit.probability * 100).toFixed(1);
        if (probitVal) probitVal.textContent = probPct;
        if (probitBar) {
            probitBar.style.width = `${Math.min(100, status.probit.probability * 100)}%`;
            probitBar.style.backgroundColor = status.probit.is_warning ? '#e71d36' : '#2ec4b6';
        }
        if (probitStatus) {
            if (status.probit.is_warning) {
                probitStatus.textContent = state.activeLang === 'zh' ? '崩盘预警 (Risk-Off)' : 'CRASH WARNING (RISK-OFF)';
                probitStatus.style.color = '#e71d36';
            } else {
                probitStatus.textContent = state.activeLang === 'zh' ? '正常' : 'NORMAL';
                probitStatus.style.color = '#2ec4b6';
            }
        }
    }
    
    // 3. Probit Factor Decomposition (P0-4: replaced 6-signal Danger Zone Checklist)
    // Shows the three factors driving the Probit crash probability:
    // VIX, Yield Curve (10Y-2Y), Credit Spread — each as standardized Z-value
    // with its weighted contribution to the Probit linear combination.
    const probitFactorsEl = document.getElementById('probit-factors-list');
    if (probitFactorsEl && status.probit) {
        const p = status.probit;
        const lang = state.activeLang;

        // Probit model weights (from local_sync.py / backtest_radar.py)
        const W_VIX = 0.586576;
        const W_YC  = 0.314905;
        const W_CS  = -0.196963;
        const INTERCEPT = -2.714673;

        // Each factor: raw value, standardized Z, weighted contribution to probit_z
        const factors = [
            {
                name: lang === 'zh' ? 'VIX 波动率指数' : 'VIX (Equity Volatility)',
                raw: p.vix_raw != null ? p.vix_raw.toFixed(2) : '-',
                z: p.x_vix != null ? p.x_vix : 0,
                weight: W_VIX,
                contribution: (p.x_vix != null ? p.x_vix : 0) * W_VIX,
                hint: lang === 'zh' ? '股市恐慌情绪' : 'Stock market fear gauge'
            },
            {
                name: lang === 'zh' ? '收益率曲线 (10Y-2Y)' : 'Yield Curve (10Y-2Y)',
                raw: p.yc_raw != null ? p.yc_raw.toFixed(3) + '%' : '-',
                z: p.x_yc != null ? p.x_yc : 0,
                weight: W_YC,
                contribution: (p.x_yc != null ? p.x_yc : 0) * W_YC,
                hint: lang === 'zh' ? '衰退预警: 曲线倒挂' : 'Recession warning: inverted curve'
            },
            {
                name: lang === 'zh' ? '信用利差' : 'Credit Spread',
                raw: p.cs_raw != null ? p.cs_raw.toFixed(3) : '-',
                z: p.x_cs != null ? p.x_cs : 0,
                weight: W_CS,
                contribution: (p.x_cs != null ? p.x_cs : 0) * W_CS,
                hint: lang === 'zh' ? '债市违约风险压力' : 'Bond market default stress'
            }
        ];

        // Max abs contribution for bar scaling
        const maxAbsContrib = Math.max(0.5, ...factors.map(f => Math.abs(f.contribution)));

        probitFactorsEl.innerHTML = factors.map(f => {
            const contribPct = (f.contribution / maxAbsContrib) * 50; // bar width % (max 50% of half-width)
            const isPositive = f.contribution >= 0;
            const barColor = isPositive ? '#e71d36' : '#2ec4b6'; // red = risk-increasing, green = risk-reducing
            const zLabel = f.z >= 0 ? `+${f.z.toFixed(2)}σ` : `${f.z.toFixed(2)}σ`;
            const contribLabel = f.contribution >= 0 ? `+${f.contribution.toFixed(3)}` : `${f.contribution.toFixed(3)}`;

            return `
                <div class="probit-factor-item" style="padding: 10px 0; border-bottom: 1px dashed var(--border);">
                    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                        <div>
                            <span style="font-size: 0.8rem; font-weight: 600; color: var(--text-primary);">${f.name}</span>
                            <span style="font-size: 0.65rem; color: var(--text-muted); margin-left: 6px;">${f.hint}</span>
                        </div>
                        <div style="font-family: var(--font-mono); font-size: 0.72rem;">
                            <span style="color: var(--text-secondary);">raw: ${f.raw}</span>
                            <span style="color: ${barColor}; margin-left: 8px; font-weight: 600;">${zLabel}</span>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div style="flex: 1; height: 8px; background: var(--surface-muted); border-radius: 4px; position: relative; overflow: hidden;">
                            <div style="position: absolute; left: 50%; top: 0; bottom: 0; width: 1px; background: var(--border);"></div>
                            <div style="position: absolute; top: 0; bottom: 0; ${isPositive ? 'left: 50%' : 'right: 50%'}; width: ${Math.min(50, Math.abs(contribPct))}%; background: ${barColor}; border-radius: 4px; transition: width 0.6s ease-out;"></div>
                        </div>
                        <span style="font-family: var(--font-mono); font-size: 0.7rem; font-weight: 600; color: ${barColor}; min-width: 55px; text-align: right;">${contribLabel}</span>
                    </div>
                </div>
            `;
        }).join('') + `
            <div style="padding: 10px 0 0 0; display: flex; justify-content: space-between; font-family: var(--font-mono); font-size: 0.75rem;">
                <span style="color: var(--text-muted);">z = ${W_VIX}·VIX + ${W_YC}·YC ${W_CS}·CS ${INTERCEPT}</span>
                <span style="font-weight: 700; color: var(--text-primary);">z = ${p.z_value != null ? p.z_value.toFixed(3) : '-'}</span>
            </div>
        `;
    }

    // 2.7 Update Multi-dimensional Macro Indicators Cards (Net Liquidity, Funding, Labor SOS)
    const macroPlumbing = status.macro_plumbing || {};
    const labor = status.labor || {};

    // 2.7.1 Net Liquidity Card
    const liqVal = document.getElementById('macro-liq-val');
    const walclVal = document.getElementById('macro-walcl-val');
    const tgaVal = document.getElementById('macro-tga-val');
    const rrpVal = document.getElementById('macro-rrp-val');
    const liqBadge = document.getElementById('macro-liq-z-badge');

    if (macroPlumbing.net_liq != null) {
        if (liqVal) liqVal.textContent = `$${macroPlumbing.net_liq.toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1})}B`;
        if (walclVal) walclVal.textContent = `$${(macroPlumbing.walcl / 1000).toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1})}B`;
        if (tgaVal) tgaVal.textContent = `$${(macroPlumbing.tga / 1000).toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1})}B`;
        if (rrpVal) rrpVal.textContent = `$${macroPlumbing.rrp.toFixed(1)}B`;
        
        if (liqBadge) {
            const z = macroPlumbing.net_liq_z_score;
            if (z >= 0) {
                liqBadge.textContent = `Z-Score: +${z.toFixed(2)} (${state.activeLang === 'zh' ? '充沛' : 'AMPLE'})`;
                liqBadge.style.backgroundColor = 'rgba(46, 196, 182, 0.15)';
                liqBadge.style.color = '#2ec4b6';
                liqBadge.style.borderColor = 'rgba(46, 196, 182, 0.35)';
            } else {
                liqBadge.textContent = `Z-Score: ${z.toFixed(2)} (${state.activeLang === 'zh' ? '收缩' : 'DRAINED'})`;
                liqBadge.style.backgroundColor = 'rgba(231, 29, 54, 0.15)';
                liqBadge.style.color = '#e71d36';
                liqBadge.style.borderColor = 'rgba(231, 29, 54, 0.35)';
            }
        }
    }

    // 2.7.2 Funding & Curve Card
    const sofrIorbVal = document.getElementById('macro-sofr-iorb-val');
    const sofrVal = document.getElementById('macro-sofr-val');
    const iorbVal = document.getElementById('macro-iorb-val');
    const steepeningVal = document.getElementById('macro-steepening-val');
    const curveBadge = document.getElementById('macro-curve-badge');

    if (macroPlumbing.sofr_iorb_spread != null) {
        const spreadBps = macroPlumbing.sofr_iorb_spread * 100;
        if (sofrIorbVal) {
            const sign = spreadBps >= 0 ? '+' : '';
            sofrIorbVal.textContent = `${sign}${spreadBps.toFixed(1)}`;
            sofrIorbVal.style.color = spreadBps > 0 ? '#e71d36' : 'var(--text-primary)';
        }
        if (sofrVal) sofrVal.textContent = `${macroPlumbing.sofr.toFixed(2)}%`;
        if (iorbVal) iorbVal.textContent = `${macroPlumbing.iorb.toFixed(2)}%`;
        
        let stText = 'NORMAL';
        let stLabel = state.activeLang === 'zh' ? '正常' : 'NORMAL';
        if (macroPlumbing.steepening_type === 'BULL_STEEPENER') {
            stText = 'BULL_STEEPENER';
            stLabel = state.activeLang === 'zh' ? '牛陡 (衰退风险)' : 'BULL STEEP (RECESSION)';
        } else if (macroPlumbing.steepening_type === 'BEAR_STEEPENER') {
            stText = 'BEAR_STEEPENER';
            stLabel = state.activeLang === 'zh' ? '熊陡 (期限溢价)' : 'BEAR STEEP (INFLATION)';
        }
        
        if (steepeningVal) {
            steepeningVal.textContent = stLabel;
            if (stText === 'BULL_STEEPENER') {
                steepeningVal.style.color = '#e71d36';
            } else if (stText === 'BEAR_STEEPENER') {
                steepeningVal.style.color = '#d98a2b';
            } else {
                steepeningVal.style.color = 'var(--text-secondary)';
            }
        }
        
        if (curveBadge) {
            const isStressed = spreadBps > 0 || stText === 'BULL_STEEPENER';
            if (isStressed) {
                curveBadge.textContent = stText === 'BULL_STEEPENER' ? 'BULL STEEP' : 'FUNDING PRESSURE';
                curveBadge.style.backgroundColor = 'rgba(231, 29, 54, 0.15)';
                curveBadge.style.color = '#e71d36';
                curveBadge.style.borderColor = 'rgba(231, 29, 54, 0.35)';
            } else {
                curveBadge.textContent = 'STABLE';
                curveBadge.style.backgroundColor = 'rgba(46, 196, 182, 0.15)';
                curveBadge.style.color = '#2ec4b6';
                curveBadge.style.borderColor = 'rgba(46, 196, 182, 0.35)';
            }
        }
    }

    // 2.7.3 Labor SOS Card
    const laborVal = document.getElementById('macro-labor-val');
    const iursaVal = document.getElementById('macro-iursa-val');
    const icsaVal = document.getElementById('macro-icsa-val');
    const laborBadge = document.getElementById('macro-labor-badge');

    if (labor.sos_indicator != null) {
        if (laborVal) laborVal.textContent = `${labor.sos_indicator.toFixed(3)}%`;
        if (iursaVal) iursaVal.textContent = `${labor.iursa.toFixed(2)}%`;
        if (icsaVal) icsaVal.textContent = labor.icsa.toLocaleString();
        
        if (laborBadge) {
            const sos = labor.sos_indicator;
            if (sos >= 0.20) {
                laborBadge.textContent = state.activeLang === 'zh' ? '就业危机 (CRITICAL)' : 'CRITICAL SOS';
                laborBadge.style.backgroundColor = 'rgba(231, 29, 54, 0.15)';
                laborBadge.style.color = '#e71d36';
                laborBadge.style.borderColor = 'rgba(231, 29, 54, 0.35)';
            } else if (sos >= 0.15) {
                laborBadge.textContent = state.activeLang === 'zh' ? '弱势预警 (WARNING)' : 'WARNING SOS';
                laborBadge.style.backgroundColor = 'rgba(217, 138, 43, 0.15)';
                laborBadge.style.color = '#d98a2b';
                laborBadge.style.borderColor = 'rgba(217, 138, 43, 0.35)';
            } else {
                laborBadge.textContent = state.activeLang === 'zh' ? '充分就业 (STABLE)' : 'STABLE';
                laborBadge.style.backgroundColor = 'rgba(46, 196, 182, 0.15)';
                laborBadge.style.color = '#2ec4b6';
                laborBadge.style.borderColor = 'rgba(46, 196, 182, 0.35)';
            }
        }
    }

    // Verdict Banner
    const verdictBanner = document.getElementById('turb-verdict-banner');
    const verdictText = document.getElementById('turb-verdict-text');
    
    if (verdictBanner && verdictText) {
        if (status.divergence.active) {
            verdictBanner.className = 'verdict-banner active';
            verdictText.textContent = translations[state.activeLang].turb_verdict_active;
        } else {
            verdictBanner.className = 'verdict-banner';
            verdictText.textContent = translations[state.activeLang].turb_verdict_inactive;
        }
    }
    
    // 3.5 Render Risk Attribution Lists
    const renderAttributionList = (containerId, contributors) => {
        const container = document.getElementById(containerId);
        if (!container) return;
        if (!contributors || contributors.length === 0) {
            container.innerHTML = `<div style="font-size: 0.75rem; color: var(--text-muted); padding: 8px 0;">No diagnostic data available.</div>`;
            return;
        }
        container.innerHTML = contributors.map(item => {
            const isPositive = item.contribution >= 0;
            const barColor = isPositive ? 'linear-gradient(90deg, #e71d36, #ff9f1c)' : 'linear-gradient(90deg, #00b4d8, #90e0ef)';
            const returnText = item.return >= 0 ? `+${(item.return * 100).toFixed(2)}%` : `${(item.return * 100).toFixed(2)}%`;
            const returnColor = item.return >= 0 ? 'var(--positive)' : 'var(--negative)';
            
            return `
                <div class="attrib-item" style="display: flex; flex-direction: column; gap: 4px;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.72rem; font-weight: 500; color: var(--text-primary);">
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <span style="font-family: var(--font-mono); font-weight: 700; color: var(--brand-gold);">${item.ticker}</span>
                            <span style="font-family: var(--font-mono); font-size: 0.65rem; color: ${returnColor};">(${returnText})</span>
                        </div>
                        <span style="font-family: var(--font-mono); font-weight: 600; color: var(--text-secondary);">${item.pct.toFixed(1)}%</span>
                    </div>
                    <div style="width: 100%; height: 6px; background: var(--surface-muted); border-radius: 3px; overflow: hidden;">
                        <div style="width: ${Math.min(100, item.pct).toFixed(1)}%; height: 100%; background: ${barColor}; border-radius: 3px; transition: width 0.6s ease-out;"></div>
                    </div>
                </div>
            `;
        }).join('');
    };
    
    renderAttributionList('macro-attrib-list', status.macro_contributors);
    renderAttributionList('sector-attrib-list', status.sector_contributors);
    
    // Update data updated at time
    const updatedAtEl = document.getElementById('turb-updated-at');
    if (updatedAtEl && payload.updated_at) {
        const date = new Date(payload.updated_at);
        const formattedDate = date.toLocaleString(state.activeLang === 'zh' ? 'zh-CN' : 'en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            timeZoneName: 'short'
        });
        updatedAtEl.textContent = `${translations[state.activeLang].last_updated || 'Updated'}: ${formattedDate}`;
    }
    
    // Update Danger Zone History Panel
    // P0-4: history items now carry peak_prob (Probit crash probability),
    // not peak_turb. Also guard against missing fields defensively.
    const dzHistoryEl = document.getElementById('turb-dz-history');
    const dzHistoryListEl = document.getElementById('turb-dz-history-list');
    if (dzHistoryEl && dzHistoryListEl) {
        const history = payload.danger_zone_history || [];
        if (history.length > 0) {
            const peakLabel = state.activeLang === 'zh' ? '峰值崩盘概率' : 'Peak Crash Prob';
            const probHeader = state.activeLang === 'zh' ? '峰值崩盘概率' : 'Peak Crash Prob';
            const startDateHeader = state.activeLang === 'zh' ? '开始日期' : 'Start Date';
            const endDateHeader = state.activeLang === 'zh' ? '结束日期' : 'End Date';
            const durationHeader = state.activeLang === 'zh' ? '持续时间' : 'Duration';
            dzHistoryEl.style.display = 'block';
            dzHistoryListEl.innerHTML = `
                <table class="insider-table" style="width: 100%; font-size: 0.75rem; border-collapse: collapse;">
                    <thead>
                        <tr style="border-bottom: 1px solid var(--border); text-align: left;">
                            <th style="padding: 8px 4px; color: var(--text-muted); font-weight: 500;">${startDateHeader}</th>
                            <th style="padding: 8px 4px; color: var(--text-muted); font-weight: 500;">${endDateHeader}</th>
                            <th style="padding: 8px 4px; color: var(--text-muted); font-weight: 500;">${durationHeader}</th>
                            <th style="padding: 8px 4px; color: var(--text-muted); font-weight: 500; text-align: right;">${probHeader}</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${history.map(item => {
                            // P0-4 compat: prefer peak_prob, fall back to peak_turb for old cached data
                            const peakVal = item.peak_prob != null ? item.peak_prob : item.peak_turb;
                            const peakText = peakVal != null
                                ? (item.peak_prob != null
                                    ? `${(peakVal * 100).toFixed(1)}%`
                                    : peakVal.toFixed(2))
                                : '-';
                            const peakColor = (item.peak_prob != null && peakVal > 0.5) ? '#e71d36' : '#d98a2b';
                            return `
                            <tr style="border-bottom: 1px dashed var(--border);">
                                <td style="padding: 8px 4px; font-family: var(--font-mono); font-weight: 500; color: ${peakColor};">
                                    <i data-lucide="alert-triangle" style="width: 12px; height: 12px; display: inline-block; vertical-align: middle; margin-right: 4px; color: ${peakColor};"></i>
                                    ${item.start_date || '-'}
                                </td>
                                <td style="padding: 8px 4px; font-family: var(--font-mono);">${item.end_date || '-'}</td>
                                <td style="padding: 8px 4px;">${item.duration_days || '-'} ${state.activeLang === 'zh' ? '天' : 'days'}</td>
                                <td style="padding: 8px 4px; font-family: var(--font-mono); text-align: right; font-weight: 600; color: ${peakColor};">${peakText}</td>
                            </tr>`;
                        }).join('')}
                    </tbody>
                </table>
            `;
        } else {
            dzHistoryEl.style.display = 'none';
        }
    }
    
    // 4. Update Regime Interpretation & Actionable Guidelines Card (3-Column Playbook)
    const tipsCard = document.getElementById('turb-tips-card');
    if (tipsCard) {
        const stateName = status.state;
        let titleText = state.activeLang === 'zh' ? '当前风险状态解读与战术对冲指南' : 'Regime Interpretation & Tactical Hedging Playbook';
        let subtitleText = state.activeLang === 'zh' ? '基于当前 market 动态的量化专家系统分析与战术性配仓建议。' : 'Expert-system analysis and tactical rules-based allocation suggestions based on current market dynamics.';
        let analysisHeader = state.activeLang === 'zh' ? '市场状态诊断' : 'Market Regime Analysis';
        let allocationHeader = state.activeLang === 'zh' ? '1. 资产配置比例' : '1. Portfolio Allocation';
        let rotationHeader = state.activeLang === 'zh' ? '2. 行业轮动防御' : '2. Sector Rotation';
        let hedgingHeader = state.activeLang === 'zh' ? '3. 战术对冲对策' : '3. Option Hedging';
        
        let analysisContent = '';
        let allocHtml = '';
        let rotHtml = '';
        let hedgeHtml = '';
        
        if (stateName === 'NORMAL') {
            analysisContent = state.activeLang === 'zh' 
                ? '<strong>当前状态：常态机制（NORMAL）</strong>。系统各项多维核心宏观指标表现健康。美联储净流动性充足（Z-Score为正），银行体系超额准备金无缺口；SOFR-IORB利差在零以下波动，银行与非银机构短期拆借成本稳定，期限溢价合理；劳动力市场SOS恶化警报未激活，失业率维持良性循环。各大类资产的协方差保持稳定，传统的分散化资产配置（如 60/40 股债平衡、风险平价）极具保护效力。标普500呈健康的趋势走势。'
                : '<strong>Current Regime: NORMAL</strong>. All multi-dimensional macro leading indicators are healthy. Fed net liquidity is ample (positive Z-Score) with no reserve scarcity; SOFR-IORB spread floats below zero, signifying stable short-term funding costs and rational term premium; Labor SOS warning is inactive with initial claims in check. Covariance structures are stable. Traditional diversification (60/40, risk-parity) is highly effective.';
            
            allocHtml = state.activeLang === 'zh'
                ? `<li>仓位控制：<strong>100% 满仓（正常配置）</strong></li>
                   <li>无风险现金：<strong>0% - 10% 战术多头缓冲</strong></li>
                   <li>战术动作：流动性环境宽松，维持既定的战略配置，精选具有技术面、基本面和机构共识的科技与高Beta个股。</li>`
                : `<li>Equities Exposure: <strong>100% (Full Exposure)</strong></li>
                   <li>Cash/Risk-Free Buffer: <strong>0% - 10%</strong></li>
                   <li>Action: Liquid environment is supportive. Follow Strategic Asset Allocation (SAA), targeting high-beta, technology and growth sectors.</li>`;
                   
            rotHtml = state.activeLang === 'zh'
                ? `<li>配置行业：偏向高增长与强 Beta 行业（如科技 XLK、非必需消费 XLY 等）</li>
                   <li>规避行业：无特定板块需要强制规避，市场广度表现健康。</li>`
                : `<li>Sector Tilt: Shift toward high-growth and high-beta (XLK, XLY, XLF)</li>
                   <li>Avoid: No explicit sector exclusions; market breadth is robust.</li>`;
                   
            hedgeHtml = state.activeLang === 'zh'
                ? `<li>对冲配比：<strong>0% (无须对冲)</strong></li>
                   <li>对冲建议：尽管 VIX 保费目前非常便宜，但系统性流动性极佳，购买看跌期权通常会因时间价值衰减（Theta decay）造成正损耗。</li>`
                : `<li>Hedging Ratio: <strong>0% (No Hedges)</strong></li>
                   <li>Action: Under strong liquidity plumbing, protective options will suffer unnecessary theta decay. No options hedge required.</li>`;
                   
        } else if (stateName === 'ELEVATED RISK') {
            analysisContent = state.activeLang === 'zh'
                ? '<strong>当前状态：预警激活（ELEVATED RISK）</strong>。跨资产马氏距离阻尼慢速线突破 95% 警戒线，或者<strong>美联储净流动性降至负区间（Net Liquidity Z-Score &lt; 0）</strong>，或<strong>SOFR-IORB利差突破 0 基点警戒线</strong>。这些信号均表明银行及影子银行体系超额流动性正在收缩，或是资金面开始出现局部的结构性融资惩罚溢价。虽然股指短期仍有惯性，但防御性调仓程序应立即启动。'
                : '<strong>Current Regime: ELEVATED RISK</strong>. The Slow Macro Turbulence has breached the 95th percentile, or **Fed Net Liquidity has entered the negative Z-score zone**, or the **SOFR-IORB spread has flipped positive**. These signal a drains-down of system-wide bank reserves or funding penalty pressures in the money markets. Defensive pruning protocols must be activated immediately.';
            
            allocHtml = state.activeLang === 'zh'
                ? `<li>仓位控制：<strong>上限 50%（主动降仓）</strong></li>
                   <li>无风险现金：<strong>50% 以上（短期债/现金）</strong></li>
                   <li>战术动作：强制撤出至少一半的多头头寸。当美联储净流动性紧缩与非银拆借溢价上升并存时，坚决兑现利润以规避成长股杀估值。</li>`
                : `<li>Equities Exposure: <strong>Max 50% (Active De-risking)</strong></li>
                   <li>Cash/Bills Reserve: <strong>50% or above</strong></li>
                   <li>Action: Force-scale down equity exposure to 50% max. If negative net liquidity and positive SOFR-IORB spread co-exist, lock in profits defensively.</li>`;
                   
            rotHtml = state.activeLang === 'zh'
                ? `<li>配置行业：防御性低 Beta 板块（必需消费 XLP、医疗保健 XLV、黄金 GLD）</li>
                   <li>规避行业：缩减高杠杆、投机性强、依赖流动性扩张估值的中小市值成长股。</li>`
                : `<li>Sector Tilt: Defensive low-beta (XLP, XLV, gold GLD)</li>
                   <li>Avoid: Speculative growth, high debt small caps highly vulnerable to funding dry-ups.</li>`;
                   
            hedgeHtml = state.activeLang === 'zh'
                ? `<li>对冲配比：<strong>10% 名义价值对冲</strong></li>
                   <li>对冲建议：考虑到隐含波动率（VIX）可能尚未反应此处的流动性降温，应以较低的隐含波动率保费成本，购入远期虚值（OTM -5%）看跌期权做尾部保护。</li>`
                : `<li>Hedging Ratio: <strong>10% Notional Value</strong></li>
                   <li>Action: Volatility might be underpricing the liquidity drain. Acquire cheap OTM (-5% strike) protective puts under low VIX regimes.</li>`;
                   
        } else if (stateName === 'HIGH RISK') {
            analysisContent = state.activeLang === 'zh'
                ? '<strong>当前状态：高风险（HIGH RISK - 崩盘预警）</strong>。系统已触发置信度极高的 <strong>Danger Zone 警告（SPY在50日均线上方但流动性底层已发生相关性分裂）</strong>，或<strong>国债收益率曲线发生“牛陡（Bull Steepening）”衰退重估</strong>，或<strong>劳动力 SOS 指标突破 0.15 警示界线</strong>。此阶段市场往往伴随着极度的“盲目乐观”与高自满，股市价格在高位横盘震荡，但随时可能因一次微小的流动性扰动引发急速的多头踩踏。'
                : '<strong>Current Regime: HIGH RISK (Crash Danger Zone Active)</strong>. The system has triggered a high-confidence **Danger Zone Warning** (SPY above 50d SMA but cross-asset correlations fracturing), or the yield curve exhibits a **Bull Steepener recession re-rating**, or **Labor SOS has breached 0.15**. The market displays high complacency, but is highly vulnerable to correlation-breakdowns.';
            
            allocHtml = state.activeLang === 'zh'
                ? `<li>仓位控制：<strong>上限 25%（极度防御）</strong></li>
                   <li>无风险现金：<strong>75% 以上（高流动性资产）</strong></li>
                   <li>战术动作：强制降仓至 25% 以下。严格遵守单一标的持仓不超过 2% 净资产的硬性限制。保留大量干火药（Dry powder）。</li>`
                : `<li>Equities Exposure: <strong>Max 25% (Extreme Capital Preservation)</strong></li>
                   <li>Cash/Money Market: <strong>75% or above</strong></li>
                   <li>Action: Rigidly cap equity portfolio size at 25%. Limit single-stock positions to under 2% to protect against unexpected tail drops.</li>`;
                   
            rotHtml = state.activeLang === 'zh'
                ? `<li>配置行业：现金类资产为主，权益端仅配置必需消费（XLP）与公用事业（XLU）</li>
                   <li>规避行业：规避所有周期性行业（XLY、XLF、XLE）以及估值泡沫高企的硬科技。</li>`
                : `<li>Sector Tilt: Move to cash, limited allocation to core utilities (XLU) & staples (XLP)</li>
                   <li>Avoid: Highly cyclical sectors (XLY, XLF, XLE) and high-multiple high growth.</li>`;
                  
            const putStrike = Math.round(latestSpx.level * 0.97);
            hedgeHtml = state.activeLang === 'zh'
                ? `<li>对冲配比：<strong>30% 名义价值对冲</strong></li>
                   <li>对冲建议：若隐含波动率 VIX ($${latestVix.level.toFixed(1)}) 仍受压，必须直接买入 30-45天到期、行权价在当前标普价格 -3% 处的平值（ATM）看跌期权做高保护对冲。</li>`
                : `<li>Hedging Ratio: <strong>30% Notional Value (Heavy Hedging)</strong></li>
                   <li>Action: Buy 30-45 DTE SPY protective puts at -3% strike. Hedges are highly underpriced.</li>`;
                   
        } else if (stateName === 'CRITICAL') {
            analysisContent = state.activeLang === 'zh'
                ? '<strong>当前状态：极端风险（CRITICAL - 绝对退守）</strong>。跨资产马氏距离慢速线击穿 99% 的绝对历史上限，或是<strong>劳动力市场 SOS 指标突破 0.20 深度衰退值（失业人数相较于低点边际剧烈爬升）</strong>。金融系统面临灾难性的无差别清算清盘风险，所有大类资产的协方差破裂并趋于同向下跌。无论大盘是否暴跌、无论VIX是否飙升，实体经济正遭受硬着陆洗礼。'
                : '<strong>Current Regime: CRITICAL (Systemic Capitulation)</strong>. Slow Macro Turbulence has breached the 99th percentile limit, or **Labor SOS has crossed the 0.20 threshold**, signifying rapid job decay and recession. Cross-asset covariance is fractured, leading to high-correlation crash risk. Physical recession or liquidity freeze is highly probable.';
            
            allocHtml = state.activeLang === 'zh'
                ? `<li>仓位控制：<strong>0%（绝对空仓，强制清零）</strong></li>
                   <li>无风险现金：<strong>100% 停泊（隔夜现金/超短期美债）</strong></li>
                   <li>战术动作：完全撤出多头，强制清零所有风险权益。<strong>禁止任何形式的抄底、补仓、马丁加仓或网格交易</strong>。</li>`
                : `<li>Equities Exposure: <strong>0% (Absolute Cash / Liquidation)</strong></li>
                   <li>Cash/Bills Allocation: <strong>100% (Safety Haven)</strong></li>
                   <li>Action: Clean sweep risk assets. Enforce cash-only stance. **Strictly forbid catching falling knives, averaging down, or grid trading.**</li>`;
                  
            rotHtml = state.activeLang === 'zh'
                ? `<li>行业动作：忽略任何行业板块轮动。在硬着陆流动性踩踏中，防守板块与成长股将同遭抛售。</li>
                   <li>战术动作：仅持有超短期美国国债或超流动性的货币市场基金，保持高度的变现自由度。</li>`
                : `<li>Sector Tilt: Disregard sector rotation. In a liquidity run-off, staples will sell off with tech.</li>
                   <li>Action: Rest strictly in ultra-short-term government T-Bills or cash equivalents.</li>`;
                  
            hedgeHtml = state.activeLang === 'zh'
                ? `<li>对冲措施：<strong>以平仓兑现现金代替期权对冲</strong></li>
                   <li>对冲建议：由于流动性崩坏此时隐含波动率（VIX $${latestVix.level.toFixed(1)}）极高，期权权利金（Premium）极度昂贵，此时买入看跌期权性价比极低，应完全通过股票清仓规避下行风险。</li>`
                : `<li>Hedging Ratio: <strong>Exit Positions Rather Than Buying Put Options</strong></li>
                   <li>Action: Due to high VIX ($${latestVix.level.toFixed(1)}), put premiums are prohibitively expensive. Rely on equity exits and cash holding instead of buying expensive puts.</li>`;
        }
        
        tipsCard.style.borderLeft = `4px solid ${status.state_color}`;
        tipsCard.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 18px;">
                <div class="tips-icon-wrap" style="display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 6px; background: var(--gold-wash); color: var(--brand-gold);">
                    <i data-lucide="shield-alert" style="width: 18px; height: 18px; color: ${status.state_color};"></i>
                </div>
                <div>
                    <h3 style="margin: 0; font-size: 0.95rem; font-weight: 600; font-family: var(--font-display); color: var(--text-primary);">${titleText}</h3>
                    <span style="font-size: 0.7rem; color: var(--text-muted);">${subtitleText}</span>
                </div>
            </div>
            
            <div style="margin-bottom: 20px;">
                <h4 style="margin: 0 0 8px 0; font-size: 0.75rem; color: var(--brand-gold); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">${analysisHeader}</h4>
                <div style="font-size: 0.8rem; line-height: 1.6; color: var(--text-secondary);">${analysisContent}</div>
            </div>

            <div class="tips-content-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; border-top: 1px solid var(--border); padding-top: 15px;">
                <div class="playbook-alloc">
                    <h4 style="margin: 0 0 10px 0; font-size: 0.75rem; color: var(--brand-gold); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">${allocationHeader}</h4>
                    <ul style="margin: 0; padding-left: 18px; font-size: 0.8rem; line-height: 1.7; color: var(--text-secondary);">${allocHtml}</ul>
                </div>
                <div class="playbook-rot">
                    <h4 style="margin: 0 0 10px 0; font-size: 0.75rem; color: var(--brand-gold); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">${rotationHeader}</h4>
                    <ul style="margin: 0; padding-left: 18px; font-size: 0.8rem; line-height: 1.7; color: var(--text-secondary);">${rotHtml}</ul>
                </div>
                <div class="playbook-hedge">
                    <h4 style="margin: 0 0 10px 0; font-size: 0.75rem; color: var(--brand-gold); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">${hedgingHeader}</h4>
                    <ul style="margin: 0; padding-left: 18px; font-size: 0.8rem; line-height: 1.7; color: var(--text-secondary);">${hedgeHtml}</ul>
                </div>
            </div>
        `;
    }
    
    if (window.lucide) window.lucide.createIcons(); // Instantly compile dynamic Lucide tags
    
    // 5. Render Chart
    renderTurbulenceChart(payload.chart_series);
}

export function updateProbitModalData() {
    if (!state.currentTurbulenceData || !state.currentTurbulenceData.status || !state.currentTurbulenceData.status.probit) {
        return;
    }
    const probit = state.currentTurbulenceData.status.probit;

    // VIX
    const vixRawEl = document.getElementById('probit-m-vix-raw');
    const vixZEl = document.getElementById('probit-m-vix-z');
    const vixContribEl = document.getElementById('probit-m-vix-contrib');
    if (vixRawEl) vixRawEl.textContent = probit.vix_raw !== undefined ? probit.vix_raw.toFixed(2) : '-';
    if (vixZEl) vixZEl.textContent = probit.x_vix !== undefined ? probit.x_vix.toFixed(4) : '-';
    if (vixContribEl) vixContribEl.textContent = probit.x_vix !== undefined ? (probit.x_vix * 0.586576).toFixed(4) : '-';

    // Yield Curve
    const ycRawEl = document.getElementById('probit-m-yc-raw');
    const ycZEl = document.getElementById('probit-m-yc-z');
    const ycContribEl = document.getElementById('probit-m-yc-contrib');
    if (ycRawEl) ycRawEl.textContent = probit.yc_raw !== undefined ? probit.yc_raw.toFixed(2) : '-';
    if (ycZEl) ycZEl.textContent = probit.x_yc !== undefined ? probit.x_yc.toFixed(4) : '-';
    if (ycContribEl) ycContribEl.textContent = probit.x_yc !== undefined ? (probit.x_yc * 0.314905).toFixed(4) : '-';

    // Credit Spread
    const csRawEl = document.getElementById('probit-m-cs-raw');
    const csZEl = document.getElementById('probit-m-cs-z');
    const csContribEl = document.getElementById('probit-m-cs-contrib');
    if (csRawEl) csRawEl.textContent = probit.cs_raw !== undefined ? probit.cs_raw.toFixed(2) : '-';
    if (csZEl) csZEl.textContent = probit.x_cs !== undefined ? probit.x_cs.toFixed(4) : '-';
    if (csContribEl) csContribEl.textContent = probit.x_cs !== undefined ? (probit.x_cs * -0.196963).toFixed(4) : '-';

    // Intercept, Z, Prob, Threshold, Verdict
    const zscoreEl = document.getElementById('probit-m-zscore');
    const probEl = document.getElementById('probit-m-probability');
    const verdictEl = document.getElementById('probit-m-verdict');

    if (zscoreEl) zscoreEl.textContent = probit.z_value !== undefined ? probit.z_value.toFixed(4) : '-';
    if (probEl) {
        const probPct = probit.probability !== undefined ? (probit.probability * 100).toFixed(2) : '-';
        probEl.textContent = probPct + '%';
    }
    if (verdictEl) {
        if (probit.is_warning) {
            verdictEl.textContent = state.activeLang === 'zh' ? '崩盘预警 (Risk-Off)' : 'CRASH WARNING (RISK-OFF)';
            verdictEl.style.color = '#e71d36';
            verdictEl.style.fontWeight = 'bold';
        } else {
            verdictEl.textContent = state.activeLang === 'zh' ? '正常' : 'NORMAL';
            verdictEl.style.color = '#2ec4b6';
            verdictEl.style.fontWeight = 'bold';
        }
    }
}

export function filterSeriesByRange(series, range) {
    if (range === 'all' || !series || series.length === 0) return series;
    const latestDateStr = series[series.length - 1].date;
    const latestDate = new Date(latestDateStr);
    let limitDate = new Date(latestDate);
    
    if (range === '1m') {
        limitDate.setMonth(limitDate.getMonth() - 1);
    } else if (range === '3m') {
        limitDate.setMonth(limitDate.getMonth() - 3);
    } else if (range === '6m') {
        limitDate.setMonth(limitDate.getMonth() - 6);
    } else if (range === '1y') {
        limitDate.setFullYear(limitDate.getFullYear() - 1);
    }
    
    return series.filter(point => new Date(point.date) >= limitDate);
}

export function downsampleSeries(series, maxPoints = 200) {
    if (!series || series.length <= maxPoints) return series;
    const step = Math.ceil(series.length / maxPoints);
    const result = [];
    for (let i = 0; i < series.length; i += step) {
        result.push(series[i]);
    }
    if (result[result.length - 1] !== series[series.length - 1]) {
        result.push(series[series.length - 1]);
    }
    return result;
}

export function renderTurbulenceChart(series) {
    const canvas = document.getElementById('turbulence-chart');
    if (!canvas) return;
    
    // Destroy existing instance to avoid duplicate overlays
    if (state.turbulenceChartInstance) {
        state.turbulenceChartInstance.destroy();
    }
    
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#a0aec0' : '#4a5568';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)';
    
    // Filter by selected range
    let filteredSeries = filterSeriesByRange(series, state.currentTurbulenceRange);
    
    // Downsample if data is too dense
    filteredSeries = downsampleSeries(filteredSeries, 200);
    
    const labels = filteredSeries.map(x => x.date);
    const turbSlow = filteredSeries.map(x => x.turb_slow);
    const turbFast = filteredSeries.map(x => x.turb_fast);
    const sectorSlow = filteredSeries.map(x => x.sector_slow);
    const slowWarn = filteredSeries.map(x => x.slow_warn);
    const slowExtreme = filteredSeries.map(x => x.slow_extreme);
    const spxPrices = filteredSeries.map(x => x.spx);
    const probitProb = filteredSeries.map(x => x.probit_prob !== undefined ? (x.probit_prob * 100).toFixed(1) : 0);
    const netLiq = filteredSeries.map(x => x.net_liq !== undefined ? x.net_liq : 0);
    
    const Chart = window.Chart;
    if (!Chart) {
        console.error('Chart.js is not loaded');
        return;
    }

    const ctx = canvas.getContext('2d');
    state.turbulenceChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: state.activeLang === 'zh' ? '宏观系统阻尼 (5d EMA)' : 'Slow Macro Turbulence (5d EMA)',
                    data: turbSlow,
                    borderColor: isDark ? '#d4c196' : '#c5b086', // Brand gold matching ledger
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    yAxisID: 'y'
                },
                {
                    label: state.activeLang === 'zh' ? '行业分散度 (5d EMA)' : 'Slow Sector Dispersion (5d EMA)',
                    data: sectorSlow,
                    borderColor: '#06b6d4', // Teal/cyan
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    yAxisID: 'y',
                    hidden: true
                },
                {
                    label: state.activeLang === 'zh' ? '快速系统阻尼 (2d EMA)' : 'Fast Macro Turbulence (2d EMA)',
                    data: turbFast,
                    borderColor: isDark ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.15)',
                    borderWidth: 1,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                    yAxisID: 'y'
                },
                {
                    label: state.activeLang === 'zh' ? '宏观警戒阈值 (95%)' : 'Macro Warning Threshold (95%)',
                    data: slowWarn,
                    borderColor: '#ff9f1c', // Vibrant warning orange
                    borderWidth: 1.5,
                    borderDash: [5, 5],
                    pointRadius: 0,
                    yAxisID: 'y'
                },
                {
                    label: state.activeLang === 'zh' ? '宏观极端阈值 (99%)' : 'Macro Extreme Threshold (99%)',
                    data: slowExtreme,
                    borderColor: '#e71d36', // Bright red
                    borderWidth: 1.5,
                    borderDash: [3, 3],
                    pointRadius: 0,
                    yAxisID: 'y'
                },
                {
                    label: state.activeLang === 'zh' ? '标普500 (SPY)' : 'S&P 500 (SPY)',
                    data: spxPrices,
                    borderColor: isDark ? '#5fa3df' : '#2c70ab', // Blue axis
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    yAxisID: 'y1'
                },
                {
                    label: state.activeLang === 'zh' ? 'Probit 崩盘概率 (%)' : 'Probit Crash Probability (%)',
                    data: probitProb,
                    borderColor: '#a855f7', // Purple
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    yAxisID: 'y2'
                },
                {
                    label: state.activeLang === 'zh' ? '美联储净流动性 (十亿美元)' : 'Net Liquidity ($B)',
                    data: netLiq,
                    borderColor: '#10b981', // Emerald Green
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    yAxisID: 'y3'
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
                        text: state.activeLang === 'zh' ? '阻尼与离散指数' : 'Turbulence & Dispersion Score',
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
                },
                y2: {
                    position: 'left',
                    grid: {
                        drawOnChartArea: false
                    },
                    title: {
                        display: true,
                        text: state.activeLang === 'zh' ? '崩盘概率 (%)' : 'Crash Probability (%)',
                        color: textColor,
                        font: {
                            size: 11
                        }
                    },
                    ticks: {
                        color: textColor,
                        callback: function(value) {
                            return value + '%';
                        },
                        font: {
                            family: 'JetBrains Mono',
                            size: 10
                        }
                    },
                    min: 0,
                    max: 100
                },
                y3: {
                    position: 'right',
                    grid: {
                        drawOnChartArea: false
                    },
                    title: {
                        display: true,
                        text: state.activeLang === 'zh' ? '美联储净流动性 (十亿美元)' : 'Net Liquidity ($B)',
                        color: textColor,
                        font: {
                            size: 11
                        }
                    },
                    ticks: {
                        color: textColor,
                        callback: function(value) {
                            return '$' + value + 'B';
                        },
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

onLanguageChange(() => {
    if (state.tabLoaded.turbulence && state.currentTurbulenceData) {
        renderTurbulence(state.currentTurbulenceData);
        updateProbitModalData();
    }
});
