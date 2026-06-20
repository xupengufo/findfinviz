import { state } from '../state.js';

export function renderPlaybook(status) {
    const tipsCard = document.getElementById('turb-tips-card');
    if (!tipsCard) return;

    const stateName = status.state;
    const latestVix = status.vix || { level: 15 };
    const latestSpx = status.spx || { level: 5000 };

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
               <li>战术动作：流动性紧缩环境（Net Liquidity Z-Score < 0）及资金面压力上升时，建议兑现高 Beta 与流动性敏感标的的利润，控制总体组合波动率。</li>`
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
               <li>对冲建议：若隐含波动率 VIX (${latestVix.level.toFixed(1)}) 仍受压，必须直接买入 30-45天到期、行权价在当前标普价格 -3% 处的平值（ATM）看跌期权做高保护对冲。</li>`
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
               <li>对冲建议：由于流动性崩坏此时隐含波动率（VIX ${latestVix.level.toFixed(1)}）极高，期权权利金（Premium）极度昂贵，此时买入看跌期权性价比极低，应完全通过股票清仓规避下行风险。</li>`
            : `<li>Hedging Ratio: <strong>Exit Positions Rather Than Buying Put Options</strong></li>
               <li>Action: Due to high VIX (${latestVix.level.toFixed(1)}), put premiums are prohibitively expensive. Rely on equity exits and cash holding instead of buying expensive puts.</li>`;
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
