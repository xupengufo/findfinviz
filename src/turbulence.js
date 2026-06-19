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
    if (!payload || payload.cache_status === 'empty') {
        const verdictText = document.getElementById('turb-verdict-text');
        if (verdictText) verdictText.textContent = translations[state.activeLang].confluence_cache_empty || 'Cache empty. Please run sync.';
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
    
    // 3. Update Checklist (6 items)
    const macroIcon = document.getElementById('check-icon-macro');
    const macroVal = document.getElementById('check-val-macro');
    const sectorIcon = document.getElementById('check-icon-sector');
    const sectorVal = document.getElementById('check-val-sector');
    const spxIcon = document.getElementById('check-icon-spx');
    const spxVal = document.getElementById('check-val-spx');
    const vixIcon = document.getElementById('check-icon-vix');
    const vixVal = document.getElementById('check-val-vix');
    const moveIcon = document.getElementById('check-icon-move');
    const moveVal = document.getElementById('check-val-move');
    const creditIcon = document.getElementById('check-icon-credit');
    const creditVal = document.getElementById('check-val-credit');
    
    const macroMet = latestMacro.slow > latestMacro.warning_threshold;
    const sectorMet = latestSector.slow > latestSector.warning_threshold;
    const spxMet = latestSpx.above_sma50;
    const vixMet = latestVix.below_dynamic;
    const moveMet = latestMove.below_dynamic;
    const creditMet = latestCredit.below_dynamic;
    
    if (macroVal) macroVal.textContent = `${latestMacro.slow.toFixed(2)} (vs ${latestMacro.warning_threshold.toFixed(2)})`;
    if (macroIcon) {
        macroIcon.outerHTML = macroMet 
            ? `<i id="check-icon-macro" class="check-icon warn-met" data-lucide="alert-triangle"></i>`
            : `<i id="check-icon-macro" class="check-icon unmet" data-lucide="circle"></i>`;
    }
    
    if (sectorVal) sectorVal.textContent = `${latestSector.slow.toFixed(2)} (vs ${latestSector.warning_threshold.toFixed(2)})`;
    if (sectorIcon) {
        sectorIcon.outerHTML = sectorMet 
            ? `<i id="check-icon-sector" class="check-icon warn-met" data-lucide="alert-triangle"></i>`
            : `<i id="check-icon-sector" class="check-icon unmet" data-lucide="circle"></i>`;
    }
    
    if (spxVal) spxVal.textContent = `${latestSpx.level.toFixed(1)} (vs SMA50 ${latestSpx.sma50.toFixed(1)})`;
    if (spxIcon) {
        spxIcon.outerHTML = spxMet 
            ? `<i id="check-icon-spx" class="check-icon met" data-lucide="check-circle-2"></i>`
            : `<i id="check-icon-spx" class="check-icon unmet" data-lucide="circle"></i>`;
    }
    
    if (vixVal) vixVal.textContent = `${latestVix.level.toFixed(1)} (vs ${latestVix.dynamic_threshold.toFixed(1)})`;
    if (vixIcon) {
        vixIcon.outerHTML = vixMet 
            ? `<i id="check-icon-vix" class="check-icon met" data-lucide="check-circle-2"></i>`
            : `<i id="check-icon-vix" class="check-icon unmet" data-lucide="circle"></i>`;
    }
    
    if (moveVal) moveVal.textContent = `${latestMove.level.toFixed(1)} (vs ${latestMove.dynamic_threshold.toFixed(1)})`;
    if (moveIcon) {
        moveIcon.outerHTML = moveMet 
            ? `<i id="check-icon-move" class="check-icon met" data-lucide="check-circle-2"></i>`
            : `<i id="check-icon-move" class="check-icon unmet" data-lucide="circle"></i>`;
    }
    
    if (creditVal) {
        let label = `${latestCredit.level.toFixed(3)} (vs ${latestCredit.dynamic_threshold.toFixed(3)})`;
        if (latestCredit.stressed) {
            label += state.activeLang === 'zh' ? ' (信用压力大!)' : ' (STRESSED!)';
        }
        creditVal.textContent = label;
    }
    if (creditIcon) {
        if (latestCredit.stressed) {
            creditIcon.outerHTML = `<i id="check-icon-credit" class="check-icon warn-met" data-lucide="alert-triangle"></i>`;
        } else {
            creditIcon.outerHTML = creditMet 
                ? `<i id="check-icon-credit" class="check-icon met" data-lucide="check-circle-2"></i>`
                : `<i id="check-icon-credit" class="check-icon unmet" data-lucide="circle"></i>`;
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
            dzHistoryEl.style.display = 'block';
            dzHistoryListEl.innerHTML = `
                <table class="insider-table" style="width: 100%; font-size: 0.75rem; border-collapse: collapse;">
                    <thead>
                        <tr style="border-bottom: 1px solid var(--border); text-align: left;">
                            <th style="padding: 8px 4px; color: var(--text-muted); font-weight: 500;">${state.activeLang === 'zh' ? '开始日期' : 'Start Date'}</th>
                            <th style="padding: 8px 4px; color: var(--text-muted); font-weight: 500;">${state.activeLang === 'zh' ? '结束日期' : 'End Date'}</th>
                            <th style="padding: 8px 4px; color: var(--text-muted); font-weight: 500;">${state.activeLang === 'zh' ? '持续时间' : 'Duration'}</th>
                            <th style="padding: 8px 4px; color: var(--text-muted); font-weight: 500; text-align: right;">${state.activeLang === 'zh' ? '峰值阻尼指数' : 'Peak Turbulence'}</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${history.map(item => `
                            <tr style="border-bottom: 1px dashed var(--border);">
                                <td style="padding: 8px 4px; font-family: var(--font-mono); font-weight: 500; color: #e71d36;">
                                    <i data-lucide="alert-triangle" style="width: 12px; height: 12px; display: inline-block; vertical-align: middle; margin-right: 4px; color: #e71d36;"></i>
                                    ${item.start_date}
                                </td>
                                <td style="padding: 8px 4px; font-family: var(--font-mono);">${item.end_date}</td>
                                <td style="padding: 8px 4px;">${item.duration_days} ${state.activeLang === 'zh' ? '天' : 'days'}</td>
                                <td style="padding: 8px 4px; font-family: var(--font-mono); text-align: right; font-weight: 600;">${item.peak_turb.toFixed(2)}</td>
                            </tr>
                        `).join('')}
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
                ? '<strong>当前状态：常态化（NORMAL）</strong>。大类资产之间的收益率协方差结构保持稳定，传统资产分散化配置模型（如 60/40 股债平衡、风险平价）在此阶段高度有效。标普500（SPY）指数价格呈现健康的上升通道趋势，且 VIX 指数处于正常或较低的历史分位数。未检测到系统性资产重组或共振下跌迹象。'
                : '<strong>Current Regime: NORMAL</strong>. Covariance structures across major asset classes are stable. Traditional diversification models (e.g. 60/40 balance, risk-parity) are highly effective in this phase. The S&P 500 (SPY) tracks a healthy upward trend, and VIX is in a normal or low historical range. No signs of systemic correlation fracture detected.';
            
            allocHtml = state.activeLang === 'zh'
                ? `<li>权益敞口：<strong>100% (满仓)</strong></li>
                   <li>现金留存：<strong>0%</strong></li>
                   <li>战术动作：维持标准战略资产配置，无需保留额外防御性现金。</li>`
                : `<li>Equities Exposure: <strong>100%</strong></li>
                   <li>Cash/Risk-Free Allocation: <strong>0%</strong></li>
                   <li>Action: Maintain full risk asset exposure; follow standard Strategic Asset Allocation (SAA).</li>`;
                   
            rotHtml = state.activeLang === 'zh'
                ? `<li>行业偏向：均衡配置或适度偏向成长板块（科技 XLK、非必需消费 XLY）</li>
                   <li>回避行业：无特定回避行业。</li>`
                : `<li>Sector Tilt: Standard growth-defensive balance or active growth (XLK, XLY)</li>
                   <li>Avoid: No specific exclusions; market broad breadth is healthy.</li>`;
                   
            hedgeHtml = state.activeLang === 'zh'
                ? `<li>期权对冲比例：<strong>0% (无对冲)</strong></li>
                   <li>对冲建议：当前无需期权对冲。尽管 VIX 便宜，但在低湍流环境下持有对冲会有正的保费时间损耗。</li>`
                : `<li>Hedging Ratio: <strong>0% (None)</strong></li>
                   <li>Action: No options hedges needed. While VIX is low, buying protective options under low systemic stress will lead to unnecessary theta decay.</li>`;
                   
        } else if (stateName === 'ELEVATED RISK') {
            analysisContent = state.activeLang === 'zh'
                ? '<strong>当前状态：风险抬升（ELEVATED RISK）</strong>。跨资产湍流指数（慢速线）或行业离散度指数已突破 95% 历史警戒线，表明资产间收益相关性偏离正常模式，底层系统性压力正在加速积聚。目前快速湍流线亦高企，表明市场正在承受强烈的资产重叠共振冲击，资产分散化的保护效应正在迅速下降。'
                : '<strong>Current Regime: ELEVATED RISK</strong>. The Slow Turbulence Index or Sector Dispersion has crossed the 95th percentile warning line, indicating that asset return correlations are deviating from historical norms. A sharp rise in the Fast Turbulence Index confirms an immediate cross-asset correlation shock, leading to a quick decay in diversification protection.';
            
            allocHtml = state.activeLang === 'zh'
                ? `<li>权益敞口：<strong>75%</strong></li>
                   <li>现金留存：<strong>25% (防守防御)</strong></li>
                   <li>战术动作：适度收回部分多头敞口，提防潜在的高位震荡或回撤。</li>`
                : `<li>Equities Exposure: <strong>75%</strong></li>
                   <li>Cash/Risk-Free Allocation: <strong>25%</strong></li>
                   <li>Action: Raise cash buffers; scale down slightly to protect capital.</li>`;
                   
            rotHtml = state.activeLang === 'zh'
                ? `<li>行业偏向：偏向低 Beta 防御性板块（必需消费 XLP、公用事业 XLU、医疗保健 XLV）</li>
                   <li>回避行业：缩减投机性高估值成长股，以及高杠杆小盘股。</li>`
                : `<li>Sector Tilt: Low-beta defensives (XLP, XLU, XLV)</li>
                   <li>Avoid: Speculative high-valuation growth names, highly leveraged micro/small caps.</li>`;
                   
            hedgeHtml = state.activeLang === 'zh'
                ? `<li>期权对冲比例：<strong>10% 名义价值对冲</strong></li>
                   <li>对冲建议：密切监视隐含波动率，可以考虑在当前较低保费水平下，布局少量远期虚值 (OTM -5%) 的标普看跌期权。</li>`
                : `<li>Hedging Ratio: <strong>10% Notional Value</strong></li>
                   <li>Action: Monitor options market. VIX level is low. Consider purchasing cheap OTM (-5% strike) protective puts to hedge tail risk.</li>`;
                   
        } else if (stateName === 'HIGH RISK') {
            analysisContent = state.activeLang === 'zh'
                ? '<strong>当前状态：高风险（HIGH RISK - Danger Zone 预警激活）</strong>。系统已触发模型置信度最高的 <strong>Danger Zone 警告</strong>！市场呈现典型的“牛市末自满”特征——SPY 仍运行于50日均线上方（买盘假象），VIX/MOVE 仍低于滚动动态阈值（市场自满、缺乏保费买盘），然而大类资产湍流指数已突破历史警戒线，底层结构严重分裂。这往往是暴风雨来临前的典型状态。'
                : '<strong>Current Regime: HIGH RISK (Danger Zone Active)</strong>. The system has triggered a high-confidence **Danger Zone alert**! The market is showcasing a classic "complacent bull extension" signature: SPY is above its 50-day SMA (buying momentum) and VIX/MOVE is below the dynamic threshold (market complacency), yet cross-asset turbulence has breached the warning level. This is a typical pre-drawdown signature.';
            
            allocHtml = state.activeLang === 'zh'
                ? `<li>权益敞口：<strong>50%</strong></li>
                   <li>现金留存：<strong>50% (强制对半)</strong></li>
                   <li>战术动作：强制收回流动性，半仓过冬，大幅提升防御性。</li>`
                : `<li>Equities Exposure: <strong>50%</strong></li>
                   <li>Cash/Risk-Free Allocation: <strong>50%</strong></li>
                   <li>Action: Enforce cash conservation; scale down equities to 50%.</li>`;
                   
            rotHtml = state.activeLang === 'zh'
                ? `<li>行业偏向：全面调入防御行业（必需消费 XLP、公用事业 XLU）</li>
                   <li>回避行业：周期性消费股 (XLY)、金融股 (XLF) 及高杠杆行业。</li>`
                : `<li>Sector Tilt: Allocate to low-beta defensives (XLP, XLU)</li>
                   <li>Avoid: Consumer Discretionary (XLY), Financials (XLF), high leverage.</li>`;
                  
            const putStrike = Math.round(latestSpx.level * 0.97);
            hedgeHtml = state.activeLang === 'zh'
                ? `<li>期权对冲比例：<strong>30% 名义价值对冲</strong></li>
                   <li>对冲建议：买入 <strong>30-45 天到期、行权价为 $${putStrike} (SPY/SPX -3% ATM)</strong> 的 SPY Protective Put。当前 VIX ($${latestVix.level.toFixed(1)}) 极低，对冲极其便宜。</li>`
                : `<li>Hedging Ratio: <strong>30% Notional Value</strong></li>
                   <li>Action: Buy <strong>30-45 DTE SPY Protective Put</strong> at strike **$${putStrike}** (SPY -3% ATM). Equity options are cheap as VIX is low ($${latestVix.level.toFixed(1)}).</li>`;
                   
        } else if (stateName === 'CRITICAL') {
            analysisContent = state.activeLang === 'zh'
                ? '<strong>当前状态：极端风险（CRITICAL - 崩溃警告）</strong>。慢速宏观系统湍流已突破 99% 的极端历史上限。大类资产的协方差出现破坏性坍塌，相关性在短期内极速趋近于 1（所有资产同向暴跌风险极大）。不管 VIX 指数是否已经暴起，此状态下金融系统流动性处于极度脆弱边缘，极易发生无差别抛售踩踏。'
                : '<strong>Current Regime: CRITICAL (Crash Warning)</strong>. The Slow Macro Turbulence has breached the 99th percentile extreme historical limit. Covariance structures have collapsed, and correlations are rapidly converging to 1. Regardless of VIX panic level, market liquidity is extremely fragile, and an indiscriminate liquidity sell-off is highly probable.';
            
            allocHtml = state.activeLang === 'zh'
                ? `<li>权益敞口：<strong>25% (最低限度)</strong></li>
                   <li>现金留存：<strong>75%</strong></li>
                   <li>战术动作：只保留底仓，全面退守无风险资产（短期国债/现金）。</li>`
                : `<li>Equities Exposure: <strong>25% (Minimum)</strong></li>
                   <li>Cash/Ultra-Short Bills: <strong>75%</strong></li>
                   <li>Action: Reduce exposure to minimum; park capital in short-term bills.</li>`;
                  
            rotHtml = state.activeLang === 'zh'
                ? `<li>行业动作：忽略任何板块轮动，传统“防御板块”可能会与成长股同跌。</li>
                   <li>战术动作：维持高流动性现金，避免承接任何下落的飞刀。</li>`
                : `<li>Sector Tilt: Ignore sector rotations; defensives will fall with growth in liquidity squeeze.</li>
                   <li>Action: Stay in cash; strictly avoid catching falling knives.</li>`;
                  
            hedgeHtml = state.activeLang === 'zh'
                ? `<li>对冲措施：<strong>多头大幅平仓为主，辅以尾部风险对冲</strong></li>
                   <li>对冲建议：直接通过股票平仓锁定流动性，此时期权保费（VIX $${latestVix.level.toFixed(1)}）过高，买入 Put 已极不划算。</li>`
                : `<li>Hedging Ratio: <strong>Equities Pruning over Options</strong></li>
                   <li>Action: Lock in liquidity by selling shares; buying puts now is expensive due to high volatility (VIX $${latestVix.level.toFixed(1)}).</li>`;
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
