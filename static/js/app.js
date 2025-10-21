let updateInterval;

async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        if (data.success) {
            document.getElementById('balance').textContent = data.balance.toFixed(2);

            const pnlElement = document.getElementById('totalPnl');
            pnlElement.textContent = data.total_pnl.toFixed(2);
            pnlElement.className = 'pnl ' + (data.total_pnl >= 0 ? 'positive' : 'negative');

            document.getElementById('updateTime').textContent = new Date().toLocaleTimeString();

            updatePositions(data.positions);
        }
    } catch (error) {
        console.error('获取状态失败:', error);
    }
}

async function fetchSpotBalance() {
    try {
        const response = await fetch('/api/spot_balance');
        const data = await response.json();

        if (data.success) {
            updateSpotBalances(data.balances);
        }
    } catch (error) {
        console.error('获取现货余额失败:', error);
    }
}

async function fetchMarkets() {
    const symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'BNB/USDT'];
    const grid = document.getElementById('marketsGrid');

    // 首次加载时创建卡片结构
    if (grid.children.length === 0) {
        symbols.forEach(symbol => {
            const card = document.createElement('div');
            card.className = 'card';
            card.dataset.symbol = symbol;
            card.innerHTML = `
                <h3>${symbol}</h3>
                <div class="card-data">
                    <div>价格: <strong class="price-value">-</strong></div>
                    <div>变化: <span class="pnl change-value">-</span></div>
                    <div>最高: <span class="high-value">-</span></div>
                    <div>最低: <span class="low-value">-</span></div>
                </div>
            `;
            grid.appendChild(card);
        });
    }

    // 仅更新数据
    for (const symbol of symbols) {
        try {
            const response = await fetch(`/api/market/${symbol}`);
            const result = await response.json();

            if (result.success) {
                const data = result.data;
                const card = grid.querySelector(`[data-symbol="${symbol}"]`);

                if (card) {
                    // 更新价格
                    const priceElement = card.querySelector('.price-value');
                    const newPrice = `$${data.price.toFixed(2)}`;
                    if (priceElement.textContent !== newPrice) {
                        priceElement.textContent = newPrice;
                        priceElement.classList.add('value-changed');
                        setTimeout(() => priceElement.classList.remove('value-changed'), 500);
                    }

                    // 更新变化
                    const changeElement = card.querySelector('.change-value');
                    const changeClass = data.price_change >= 0 ? 'positive' : 'negative';
                    const newChange = `${data.price_change.toFixed(2)}%`;
                    if (changeElement.textContent !== newChange) {
                        changeElement.className = `pnl ${changeClass}`;
                        changeElement.textContent = newChange;
                        changeElement.classList.add('value-changed');
                        setTimeout(() => changeElement.classList.remove('value-changed'), 500);
                    }

                    // 更新最高价
                    const highElement = card.querySelector('.high-value');
                    const newHigh = `$${data.high.toFixed(2)}`;
                    if (highElement.textContent !== newHigh) {
                        highElement.textContent = newHigh;
                        highElement.classList.add('value-changed');
                        setTimeout(() => highElement.classList.remove('value-changed'), 500);
                    }

                    // 更新最低价
                    const lowElement = card.querySelector('.low-value');
                    const newLow = `$${data.low.toFixed(2)}`;
                    if (lowElement.textContent !== newLow) {
                        lowElement.textContent = newLow;
                        lowElement.classList.add('value-changed');
                        setTimeout(() => lowElement.classList.remove('value-changed'), 500);
                    }
                }
            }
        } catch (error) {
            console.error(`获取${symbol}数据失败:`, error);
        }
    }
}

function updateSpotBalances(balances) {
    const grid = document.getElementById('spotGrid');

    if (!balances || Object.keys(balances).length === 0) {
        if (grid.innerHTML !== '<div class="card"><p>暂无现货余额</p></div>') {
            grid.innerHTML = '<div class="card"><p>暂无现货余额</p></div>';
        }
        return;
    }

    // 清空现有内容
    grid.innerHTML = '';

    // 创建现货余额卡片
    Object.entries(balances).forEach(([currency, balance]) => {
        if (balance.total > 0) {
            const card = document.createElement('div');
            card.className = 'card';
            card.dataset.currency = currency;

            card.innerHTML = `
                <h3>${currency}</h3>
                <div class="card-data">
                    <div>总量: <strong class="total-value">${balance.total.toFixed(6)}</strong></div>
                    <div>可用: <span class="free-value">${balance.free.toFixed(6)}</span></div>
                    <div>冻结: <span class="used-value">${balance.used.toFixed(6)}</span></div>
                </div>
            `;
            grid.appendChild(card);
        }
    });
}

function updatePositions(positions) {
    const grid = document.getElementById('positionsGrid');

    if (!positions || positions.length === 0) {
        if (grid.innerHTML !== '<div class="card"><p>暂无持仓</p></div>') {
            grid.innerHTML = '<div class="card"><p>暂无持仓</p></div>';
        }
        return;
    }

    // 构建持仓映射
    const positionMap = {};
    positions.forEach(pos => {
        const key = `${pos.symbol}-${pos.side}`;
        positionMap[key] = pos;
    });

    // 删除不存在的持仓卡片
    Array.from(grid.children).forEach(card => {
        const key = card.dataset.positionKey;
        if (key && !positionMap[key]) {
            card.remove();
        }
    });

    // 更新或创建持仓卡片
    positions.forEach(pos => {
        const key = `${pos.symbol}-${pos.side}`;
        let card = grid.querySelector(`[data-position-key="${key}"]`);

        if (!card) {
            // 创建新卡片
            card = document.createElement('div');
            card.className = 'card';
            card.dataset.positionKey = key;

            const sideColor = pos.side === 'long' ? '#10b981' : '#ef4444';

            card.innerHTML = `
                <h3>${pos.symbol}</h3>
                <div class="card-data">
                    <div>方向: <strong class="side-text" style="color: ${sideColor}">${pos.side === 'long' ? '多' : '空'}</strong></div>
                    <div>数量: <span class="size-value">-</span></div>
                    <div>入场: <span class="entry-value">-</span></div>
                    <div>盈亏: <span class="pnl pnl-value">-</span></div>
                </div>
            `;
            grid.appendChild(card);
        }

        // 更新数据
        const sizeElement = card.querySelector('.size-value');
        const newSize = pos.size.toFixed(6);
        if (sizeElement.textContent !== newSize) {
            sizeElement.textContent = newSize;
            sizeElement.classList.add('value-changed');
            setTimeout(() => sizeElement.classList.remove('value-changed'), 500);
        }

        const entryElement = card.querySelector('.entry-value');
        const newEntry = `$${pos.entry_price.toFixed(2)}`;
        if (entryElement.textContent !== newEntry) {
            entryElement.textContent = newEntry;
            entryElement.classList.add('value-changed');
            setTimeout(() => entryElement.classList.remove('value-changed'), 500);
        }

        const pnlElement = card.querySelector('.pnl-value');
        const pnlClass = pos.unrealized_pnl >= 0 ? 'positive' : 'negative';
        const newPnl = `${pos.unrealized_pnl.toFixed(2)} USDT`;
        if (pnlElement.textContent !== newPnl) {
            pnlElement.className = `pnl ${pnlClass}`;
            pnlElement.textContent = newPnl;
            pnlElement.classList.add('value-changed');
            setTimeout(() => pnlElement.classList.remove('value-changed'), 500);
        }
    });
}

async function updatePositionPNL() {
    const grid = document.getElementById('positionsGrid');
    if (!grid) return;

    const positionCards = grid.querySelectorAll('.card[data-position-key]');

    for (const card of positionCards) {
        const key = card.dataset.positionKey;
        if (!key || key === 'undefined') continue;

        const [symbol] = key.split('-');

        try {
            // 获取当前市价
            const response = await fetch(`/api/market/${symbol}`);
            const result = await response.json();

            if (result.success && result.data) {
                const currentPrice = result.data.price;

                // 找到入场价和持仓量元素
                const entryElement = card.querySelector('.entry-value');
                const sizeElement = card.querySelector('.size-value');
                const pnlElement = card.querySelector('.pnl-value');

                if (entryElement && sizeElement && pnlElement) {
                    const entryPrice = parseFloat(entryElement.textContent.replace('$', ''));
                    const size = parseFloat(sizeElement.textContent);
                    const side = card.querySelector('.side-text').textContent;

                    if (entryPrice > 0 && size > 0) {
                        // 计算实时PNL
                        let pnl;
                        if (side === '多') {
                            pnl = (currentPrice - entryPrice) * size;
                        } else {
                            pnl = (entryPrice - currentPrice) * size;
                        }

                        // Update PNL display
                        const pnlClass = pnl >= 0 ? 'positive' : 'negative';
                        const newPnl = `${pnl.toFixed(2)} USDT`;

                        if (pnlElement.textContent !== newPnl) {
                            pnlElement.className = `pnl ${pnlClass}`;
                            pnlElement.textContent = newPnl;
                            pnlElement.classList.add('value-changed');
                            setTimeout(() => pnlElement.classList.remove('value-changed'), 500);
                        }
                    }
                }
            }
        } catch (error) {
            console.error(`更新${symbol} PNL失败:`, error);
        }
    }
}

async function fetchLogs() {
    const symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'BNB/USDT'];
    const container = document.getElementById('logsContainer');

    let hasSignals = false;

    for (const symbol of symbols) {
        try {
            const response = await fetch(`/api/history/${symbol}`);
            const result = await response.json();

            if (result.success && result.signal_history && result.signal_history.length > 0) {
                hasSignals = true;
                const latestSignal = result.signal_history[result.signal_history.length - 1];

                // 查找或创建日志卡片
                let logCard = container.querySelector(`[data-log-symbol="${symbol}"]`);

                if (!logCard) {
                    // 创建新卡片
                    logCard = document.createElement('div');
                    logCard.className = 'log-card';
                    logCard.dataset.logSymbol = symbol;
                    logCard.innerHTML = `
                        <div class="log-header">
                            <h4>${symbol}</h4>
                            <span class="log-time">-</span>
                        </div>
                        <div class="log-content">
                            <div class="log-row">
                                <span>信号:</span>
                                <strong class="signal-value">-</strong>
                            </div>
                            <div class="log-row">
                                <span>信心:</span>
                                <strong class="confidence-value">-</strong>
                            </div>
                            <div class="log-row">
                                <span>理由:</span>
                                <span class="log-reason reason-value">-</span>
                            </div>
                            <div class="log-row stop-loss-row">
                                <span>止损:</span>
                                <span class="stop-loss-value">-</span>
                            </div>
                            <div class="log-row take-profit-row">
                                <span>止盈:</span>
                                <span class="take-profit-value">-</span>
                            </div>
                        </div>
                    `;
                    container.appendChild(logCard);
                }

                // 更新数据
                const timeElement = logCard.querySelector('.log-time');
                timeElement.textContent = latestSignal.timestamp || '未知时间';

                const signalElement = logCard.querySelector('.signal-value');
                const signalColor = latestSignal.signal === 'BUY' ? '#10b981' :
                                   latestSignal.signal === 'SELL' ? '#ef4444' : '#6b7280';
                signalElement.style.color = signalColor;
                signalElement.textContent = latestSignal.signal;

                const confidenceElement = logCard.querySelector('.confidence-value');
                const confidenceColor = latestSignal.confidence === 'HIGH' ? '#10b981' :
                                       latestSignal.confidence === 'MEDIUM' ? '#f59e0b' : '#ef4444';
                confidenceElement.style.color = confidenceColor;
                confidenceElement.textContent = latestSignal.confidence;

                const reasonElement = logCard.querySelector('.reason-value');
                reasonElement.textContent = latestSignal.reason || '无';

                // 更新止损和止盈
                const stopLossRow = logCard.querySelector('.stop-loss-row');
                const stopLossValue = logCard.querySelector('.stop-loss-value');
                if (latestSignal.stop_loss) {
                    stopLossRow.style.display = 'flex';
                    stopLossValue.textContent = `$${typeof latestSignal.stop_loss === 'number' ? latestSignal.stop_loss.toFixed(2) : latestSignal.stop_loss}`;
                } else {
                    stopLossRow.style.display = 'none';
                }

                const takeProfitRow = logCard.querySelector('.take-profit-row');
                const takeProfitValue = logCard.querySelector('.take-profit-value');
                if (latestSignal.take_profit) {
                    takeProfitRow.style.display = 'flex';
                    takeProfitValue.textContent = `$${typeof latestSignal.take_profit === 'number' ? latestSignal.take_profit.toFixed(2) : latestSignal.take_profit}`;
                } else {
                    takeProfitRow.style.display = 'none';
                }
            }
        } catch (error) {
            console.error(`获取${symbol}历史数据失败:`, error);
        }
    }

    if (!hasSignals && container.children.length === 0) {
        container.innerHTML = '<div class="card"><p>暂无AI分析记录</p></div>';
    }
}

async function triggerAnalysis() {
    const symbol = document.getElementById('analysisSymbol').value;
    const btn = document.getElementById('analysisBtn');

    // 禁用按钮，显示加载状态
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '🔄 分析中...';

    try {
        const response = await fetch('/api/analysis', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({symbol})
        });

        const result = await response.json();

        if (result.success) {
            alert(`${result.message}\n信号: ${result.signal_data.signal}\n理由: ${result.signal_data.reason}\n信心: ${result.signal_data.confidence}`);

            // 刷新数据显示
            fetchStatus();
            fetchMarkets();
            fetchLogs();
        } else {
            alert(`AI分析失败: ${result.error}`);
        }
    } catch (error) {
        alert('AI分析失败: ' + error.message);
    } finally {
        // 恢复按钮状态
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

async function triggerAllAnalysis() {
    const symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'BNB/USDT'];

    if (!confirm('确认对所有币种进行AI分析？这可能需要一些时间。')) {
        return;
    }

    let successCount = 0;
    let failCount = 0;

    for (const symbol of symbols) {
        try {
            const response = await fetch('/api/analysis', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({symbol})
            });

            const result = await response.json();
            if (result.success) {
                successCount++;
                console.log(`${symbol} 分析完成: ${result.signal_data.signal}`);
            } else {
                failCount++;
                console.error(`${symbol} 分析失败: ${result.error}`);
            }
        } catch (error) {
            failCount++;
            console.error(`${symbol} 分析失败:`, error.message);
        }

        // 避免请求过快
        await new Promise(resolve => setTimeout(resolve, 500));
    }

    alert(`批量分析完成！\n成功: ${successCount}个币种\n失败: ${failCount}个币种`);

    // 刷新数据显示
    fetchStatus();
    fetchMarkets();
    fetchLogs();
}

async function executeTrade(action) {
    const symbol = document.getElementById('tradeSymbol').value;
    const amount = parseFloat(document.getElementById('tradeAmount').value);

    if (!confirm(`确认执行${action === 'buy' ? '开多' : action === 'sell' ? '开空' : '平仓'}操作？`)) {
        return;
    }

    try {
        const response = await fetch('/api/execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({symbol, action, amount})
        });

        const result = await response.json();
        alert(result.success ? result.message : `操作失败: ${result.error}`);

        if (result.success) {
            fetchStatus();
            fetchMarkets();
        }
    } catch (error) {
        alert('操作失败: ' + error.message);
    }
}

// 初始化
fetchStatus();
fetchSpotBalance();
fetchMarkets();
fetchLogs();
updateInterval = setInterval(() => {
    fetchStatus();
    fetchSpotBalance();
    fetchMarkets();
    fetchLogs();
}, 3000); // 每3秒更新（提高更新频率）

// 独立的价格更新循环（更频繁）
let priceUpdateInterval = setInterval(() => {
    updatePositionPNL();
}, 1000); // 每秒更新持仓PNL
