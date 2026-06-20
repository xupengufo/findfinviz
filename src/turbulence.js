import { state, API_BASE } from './state.js';
import { translations, onLanguageChange } from './i18n.js';
import { escapeHtml, parseChange } from './utils.js';
import { renderTurbulenceChart } from './turbulence/chart.js';
import { updateProbitModalData } from './turbulence/probit.js';
import { renderPlaybook } from './turbulence/playbook.js';

export { filterSeriesByRange, downsampleSeries, renderTurbulenceChart } from './turbulence/chart.js';
export { updateProbitModalData } from './turbulence/probit.js';

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
    
    // 2.7 Render Macro Plumbing Cards (Liquidity, Funding, Labor)
    const macroPlumbing = status.macro_plumbing || {};
    const labor = status.labor || status.labor_plumbing || {};
    
    // 2.7.1 Net Liquidity Card
    const liqVal = document.getElementById('macro-liq-val');
    const walclVal = document.getElementById('macro-walcl-val');
    const tgaVal = document.getElementById('macro-tga-val');
    const rrpVal = document.getElementById('macro-rrp-val');
    const liqBadge = document.getElementById('macro-liq-z-badge');
    
    if (macroPlumbing.net_liq !== undefined) {
        if (liqVal) liqVal.textContent = `$${macroPlumbing.net_liq.toFixed(1)}B`;
        if (walclVal) walclVal.textContent = `$${(macroPlumbing.walcl / 1000).toFixed(2)}T`;
        if (tgaVal) tgaVal.textContent = `$${macroPlumbing.tga.toFixed(1)}B`;
        if (rrpVal) rrpVal.textContent = `$${macroPlumbing.rrp.toFixed(1)}B`;
        
        if (liqBadge && macroPlumbing.net_liq_z_score != null) {
            const z = macroPlumbing.net_liq_z_score;
            if (z >= 0) {
                liqBadge.textContent = `Z-Score: +${z.toFixed(2)} (${state.activeLang === 'zh' ? '充足' : 'AMPLE'})`;
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
    const dzHistoryEl = document.getElementById('turb-dz-history');
    const dzHistoryListEl = document.getElementById('turb-dz-history-list');
    if (dzHistoryEl && dzHistoryListEl) {
        const history = payload.danger_zone_history || [];
        if (history.length > 0) {
            const startDateHeader = state.activeLang === 'zh' ? '开始日期' : 'Start Date';
            const endDateHeader = state.activeLang === 'zh' ? '结束日期' : 'End Date';
            const durationHeader = state.activeLang === 'zh' ? '持续时间' : 'Duration';
            const probHeader = state.activeLang === 'zh' ? '峰值崩盘概率' : 'Peak Crash Prob';
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
    renderPlaybook(status);
    
    if (window.lucide) window.lucide.createIcons(); // Instantly compile dynamic Lucide tags
    
    // 5. Render Chart
    renderTurbulenceChart(payload.chart_series);
}

onLanguageChange(() => {
    if (state.tabLoaded.turbulence && state.currentTurbulenceData) {
        renderTurbulence(state.currentTurbulenceData);
        updateProbitModalData();
    }
});
