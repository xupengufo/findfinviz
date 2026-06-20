import { state } from '../state.js';

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
