import { state } from '../state.js';

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
                        drawOnChartArea: false
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
