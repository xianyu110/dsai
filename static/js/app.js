let updateInterval;
let spotBalanceCollapsed = false;

// 主题切换功能
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    const themeIcon = document.querySelector('.theme-icon');

    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);

    // 更新图标
    themeIcon.textContent = newTheme === 'dark' ? '🌙' : '☀️';

    // 添加切换动画
    document.body.style.transition = 'background 0.3s ease, color 0.3s ease';
}

// 页面加载时恢复主题
(function() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    const html = document.documentElement;
    const themeIcon = document.querySelector('.theme-icon');

    html.setAttribute('data-theme', savedTheme);
    if (themeIcon) {
        themeIcon.textContent = savedTheme === 'dark' ? '🌙' : '☀️';
    }
})();

function toggleSpotBalance() {
    const grid = document.getElementById('spotGrid');
    const icon = document.getElementById('spotToggleIcon');
    const section = document.querySelector('.spot-section');

    spotBalanceCollapsed = !spotBalanceCollapsed;

    if (spotBalanceCollapsed) {
        grid.classList.add('collapsed');
        icon.textContent = '▶';
        section.classList.add('collapsed');
    } else {
        grid.classList.remove('collapsed');
        icon.textContent = '▼';
        section.classList.remove('collapsed');
    }

    // 保存状态到localStorage
    localStorage.setItem('spotBalanceCollapsed', spotBalanceCollapsed);
}

// 页面加载时恢复折叠状态
window.addEventListener('DOMContentLoaded', function() {
    const savedState = localStorage.getItem('spotBalanceCollapsed');
    if (savedState === 'true') {
        // 延迟执行以确保DOM已完全加载
        setTimeout(() => {
            toggleSpotBalance();
        }, 100);
    }
});

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

            // 更新自动交易状态
            updateAutoTradeStatus(data.auto_trade);

            // 更新持仓表格和概览
            updateOrdersTable(data.positions);
            updatePositions(data.positions);
        }
    } catch (error) {
        console.error('获取状态失败:', error);
    }
}

function updateAutoTradeStatus(enabled) {
    const statusBadge = document.getElementById('autoTradeStatus');
    const toggleBtn = document.getElementById('autoTradeToggle');
    const toggleText = document.getElementById('autoTradeToggleText');

    if (enabled) {
        statusBadge.textContent = '运行中';
        statusBadge.className = 'status-badge active';
        toggleBtn.className = 'toggle-btn enabled';
        toggleText.textContent = '停止';
    } else {
        statusBadge.textContent = '已停止';
        statusBadge.className = 'status-badge inactive';
        toggleBtn.className = 'toggle-btn disabled';
        toggleText.textContent = '启用';
    }
}

async function toggleAutoTrade() {
    const toggleBtn = document.getElementById('autoTradeToggle');
    const currentStatus = toggleBtn.classList.contains('enabled');
    const newStatus = !currentStatus;

    // 确认对话框
    const action = newStatus ? '启用' : '停止';
    const warning = newStatus ?
        '⚠️ 启用自动交易后，系统将根据AI分析自动执行交易。\n\n确认要启用吗？' :
        '确认要停止自动交易吗？';

    if (!confirm(warning)) {
        return;
    }

    // 禁用按钮
    toggleBtn.disabled = true;

    try {
        const response = await fetch('/api/auto_trade', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ enable: newStatus })
        });

        const result = await response.json();

        if (result.success) {
            updateAutoTradeStatus(result.auto_trade);
            alert(`✅ ${result.message}`);

            // 刷新状态
            fetchStatus();
        } else {
            alert(`❌ 操作失败: ${result.error}`);
        }
    } catch (error) {
        alert(`❌ 操作失败: ${error.message}`);
    } finally {
        toggleBtn.disabled = false;
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

    if (!grid) return;

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

    // 过滤并排序余额
    // 1. 过滤掉余额太小的币种(总量<0.0001,除非是USDT/USDC等稳定币)
    // 2. 按总量从大到小排序
    const stablecoins = ['USDT', 'USDC', 'BUSD', 'DAI'];
    const MIN_DISPLAY_AMOUNT = 0.0001;

    const filteredBalances = Object.entries(balances)
        .filter(([currency, balance]) => {
            // 稳定币始终显示
            if (stablecoins.includes(currency)) return true;
            // 其他币种需要余额大于阈值
            return balance.total > MIN_DISPLAY_AMOUNT;
        })
        .sort((a, b) => {
            // USDT排第一
            if (a[0] === 'USDT') return -1;
            if (b[0] === 'USDT') return 1;
            // 其他按总量排序
            return b[1].total - a[1].total;
        });

    if (filteredBalances.length === 0) {
        grid.innerHTML = '<div class="card"><p>暂无现货余额</p></div>';
        return;
    }

    // 创建现货余额卡片
    filteredBalances.forEach(([currency, balance]) => {
        const card = document.createElement('div');
        card.className = 'card';
        card.dataset.currency = currency;

        // 根据币种类型决定小数位数
        const decimals = stablecoins.includes(currency) ? 2 : 6;

        card.innerHTML = `
            <h3>${currency}</h3>
            <div class="card-data">
                <div><span>总量</span><strong class="total-value">${balance.total.toFixed(decimals)}</strong></div>
                <div><span>可用</span><span class="free-value">${balance.free.toFixed(decimals)}</span></div>
                <div><span>冻结</span><span class="used-value">${balance.used.toFixed(decimals)}</span></div>
            </div>
        `;
        grid.appendChild(card);
    });
}

function updatePositions(positions) {
    const grid = document.getElementById('positionsGrid');

    if (!grid) return;

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

// fetchLogs函数已废弃，AI分析记录现在合并到交易日志中
async function fetchLogs() {
    // 这个函数保留为空，防止调用报错
    // AI分析记录已经合并到 fetchTradeLogs 中
}

async function triggerAnalysis() {
    const symbol = document.getElementById('analysisSymbol').value;
    const btn = document.getElementById('analysisBtn');

    // 询问用户是否自动执行交易
    const autoExecute = confirm('是否在分析后自动执行交易？\n\n点击"确定"：分析并自动下单\n点击"取消"：仅分析不下单');

    // 禁用按钮，显示加载状态
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '🔄 分析中...';

    try {
        const response = await fetch('/api/analysis', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({symbol, auto_execute: autoExecute})
        });

        const result = await response.json();

        if (result.success) {
            let message = `${result.message}\n信号: ${result.signal_data.signal}\n理由: ${result.signal_data.reason}\n信心: ${result.signal_data.confidence}`;

            if (result.trade_executed) {
                message += `\n\n✅ 交易已执行: ${result.trade_message}`;
            } else if (autoExecute && result.signal_data.signal === 'HOLD') {
                message += '\n\n⏸️ 信号为HOLD，未执行交易';
            }

            alert(message);

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

    // 第一个确认对话框：是否进行分析
    if (!confirm('确认对所有币种进行AI分析？这可能需要一些时间。')) {
        return;
    }

    // 第二个确认对话框：是否自动执行交易
    const autoExecute = confirm('是否在分析后自动执行交易？\n\n点击"确定"：分析并自动下单\n点击"取消"：仅分析不下单');

    let successCount = 0;
    let failCount = 0;
    let tradeCount = 0;
    let tradeResults = [];

    for (const symbol of symbols) {
        try {
            const response = await fetch('/api/analysis', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({symbol, auto_execute: autoExecute})
            });

            const result = await response.json();
            if (result.success) {
                successCount++;
                console.log(`${symbol} 分析完成: ${result.signal_data.signal}`);

                if (result.trade_executed) {
                    tradeCount++;
                    tradeResults.push(`${symbol}: ${result.signal_data.signal} - ${result.trade_message}`);
                }
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

    let message = `批量分析完成！\n✅ 成功: ${successCount}个币种\n❌ 失败: ${failCount}个币种`;

    if (autoExecute) {
        message += `\n\n📊 执行交易: ${tradeCount}笔`;
        if (tradeResults.length > 0) {
            message += '\n\n交易详情:\n' + tradeResults.join('\n');
        }
    }

    alert(message);

    // 刷新数据显示
    fetchStatus();
    fetchMarkets();
    fetchLogs();
}

// 实时更新预计开仓张数
let marketPrices = {};

async function updateEstimatedContracts() {
    const symbol = document.getElementById('tradeSymbol').value;
    const amount = parseFloat(document.getElementById('tradeAmount').value) || 0;
    const estimatedSpan = document.getElementById('estimatedContracts');

    if (amount <= 0) {
        estimatedSpan.textContent = '-';
        return;
    }

    try {
        // 获取当前市场价格
        const response = await fetch(`/api/market/${symbol}`);
        const data = await response.json();

        if (data.success && data.data) {
            const currentPrice = data.data.price;
            marketPrices[symbol] = currentPrice;

            // 计算张数 (简化计算: USDT金额 / 当前价格)
            const contracts = amount / currentPrice;
            estimatedSpan.textContent = contracts.toFixed(4);
        }
    } catch (error) {
        console.error('获取价格失败:', error);
        estimatedSpan.textContent = '计算失败';
    }
}

// 监听交易对和金额变化
document.addEventListener('DOMContentLoaded', function() {
    const symbolSelect = document.getElementById('tradeSymbol');
    const amountInput = document.getElementById('tradeAmount');

    if (symbolSelect) {
        symbolSelect.addEventListener('change', updateEstimatedContracts);
    }

    if (amountInput) {
        amountInput.addEventListener('input', updateEstimatedContracts);
    }

    // 初始计算一次
    setTimeout(updateEstimatedContracts, 500);
});

async function executeTrade(action) {
    const symbol = document.getElementById('tradeSymbol').value;
    const amount = parseFloat(document.getElementById('tradeAmount').value);
    const leverage = parseInt(document.getElementById('tradeLeverage').value);

    if (!amount || amount <= 0) {
        alert('请输入有效的USDT金额');
        return;
    }

    // 获取预计张数用于确认提示
    const estimatedContracts = document.getElementById('estimatedContracts').textContent;

    let confirmMsg = '';
    if (action === 'buy') {
        confirmMsg = `确认开多仓？\n金额: ${amount} USDT\n杠杆: ${leverage}x\n预计: ${estimatedContracts} 张`;
    } else if (action === 'sell') {
        confirmMsg = `确认开空仓？\n金额: ${amount} USDT\n杠杆: ${leverage}x\n预计: ${estimatedContracts} 张`;
    } else {
        confirmMsg = `确认平仓 ${symbol}？`;
    }

    if (!confirm(confirmMsg)) {
        return;
    }

    try {
        const response = await fetch('/api/execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({symbol, action, amount, leverage})
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

// 订单表格管理
async function updateOrdersTable(positions) {
    const tbody = document.getElementById('ordersTableBody');

    if (!positions || positions.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="13" style="text-align: center; padding: 40px; color: #94a3b8;">
                    暂无持仓数据
                </td>
            </tr>
        `;
        return;
    }

    // 获取实时行情数据
    const marketData = {};
    for (const pos of positions) {
        try {
            const response = await fetch(`/api/market/${pos.symbol}`);
            const result = await response.json();
            if (result.success) {
                marketData[pos.symbol] = result.data;
            }
        } catch (error) {
            console.error(`获取${pos.symbol}行情失败:`, error);
        }
    }

    tbody.innerHTML = positions.map((pos, index) => {
        const isProfit = pos.unrealized_pnl >= 0;
        const profitClass = isProfit ? 'profit' : 'loss';
        const directionClass = pos.side === 'long' ? 'long' : 'short';
        const directionText = pos.side === 'long' ? '多' : '空';

        // 获取市场数据
        const market = marketData[pos.symbol];
        const currentPrice = market ? market.price : pos.entry_price;
        const priceChange = market ? market.price_change : 0;
        const priceChangeClass = priceChange >= 0 ? 'positive' : 'negative';

        // 使用API返回的真实数据
        const margin = pos.margin || 0; // 保证金
        const liquidationPrice = pos.liquidation_price || 0; // 强平价
        const leverage = pos.leverage || 10; // 杠杆倍数

        // 强平价预警颜色计算
        let liqPriceClass = '';
        if (liquidationPrice > 0) {
            if (pos.side === 'long') {
                // 多仓：当前价格接近强平价时危险
                const distancePercent = ((currentPrice - liquidationPrice) / currentPrice) * 100;
                if (distancePercent < 5) liqPriceClass = 'danger';
                else if (distancePercent < 10) liqPriceClass = 'warning';
            } else {
                // 空仓：当前价格接近强平价时危险
                const distancePercent = ((liquidationPrice - currentPrice) / currentPrice) * 100;
                if (distancePercent < 5) liqPriceClass = 'danger';
                else if (distancePercent < 10) liqPriceClass = 'warning';
            }
        }

        return `
            <tr>
                <td><input type="checkbox" class="position-checkbox" data-symbol="${pos.symbol}" data-side="${pos.side}"></td>
                <td>${index + 1}</td>
                <td><strong>${pos.symbol}</strong></td>
                <td>
                    <span class="direction-badge ${directionClass}">
                        ${directionText}
                    </span>
                </td>
                <td>${pos.size.toFixed(6)}</td>
                <td class="price-cell">$${pos.entry_price.toFixed(4)}</td>
                <td class="price-cell">$${currentPrice.toFixed(4)}</td>
                <td class="margin-cell">${margin > 0 ? margin.toFixed(2) : '-'} <small>${margin > 0 ? 'USDT' : ''}</small></td>
                <td class="liquidation-cell ${liqPriceClass}">${liquidationPrice > 0 ? '$' + liquidationPrice.toFixed(4) : '-'}</td>
                <td>
                    <span class="pnl ${profitClass}">
                        ${pos.unrealized_pnl.toFixed(2)}
                    </span>
                </td>
                <td>
                    <span class="pnl ${priceChangeClass}">
                        ${priceChange.toFixed(2)}%
                    </span>
                </td>
                <td>
                    <span class="status-badge-table running">
                        ● 进行中
                    </span>
                </td>
                <td>
                    <button class="close-btn-table" onclick="closePosition('${pos.symbol}', '${pos.side}')">
                        平仓
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function toggleSelectAll() {
    const selectAll = document.getElementById('selectAll');
    const checkboxes = document.querySelectorAll('.position-checkbox');
    checkboxes.forEach(cb => cb.checked = selectAll.checked);
}

async function closePosition(symbol, side) {
    if (!confirm(`确认平仓 ${symbol} ${side === 'long' ? '多头' : '空头'}持仓?`)) {
        return;
    }

    try {
        const response = await fetch('/api/execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                symbol: symbol,
                action: 'close'
            })
        });

        const result = await response.json();
        if (result.success) {
            alert('✅ 平仓成功');
            refreshOrders();
        } else {
            alert(`❌ 平仓失败: ${result.error}`);
        }
    } catch (error) {
        alert(`❌ 平仓失败: ${error.message}`);
    }
}

async function refreshOrders() {
    await fetchStatus();
    alert('✅ 刷新完成');
}

async function closeAllPositions() {
    const checkboxes = document.querySelectorAll('.position-checkbox:checked');

    if (checkboxes.length === 0) {
        alert('⚠️ 请先选择要平仓的持仓');
        return;
    }

    if (!confirm(`确认平仓选中的 ${checkboxes.length} 个持仓?`)) {
        return;
    }

    let successCount = 0;
    let failCount = 0;

    for (const checkbox of checkboxes) {
        const symbol = checkbox.dataset.symbol;
        try {
            const response = await fetch('/api/execute', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    symbol: symbol,
                    action: 'close'
                })
            });

            const result = await response.json();
            if (result.success) {
                successCount++;
            } else {
                failCount++;
            }
        } catch (error) {
            failCount++;
        }

        await new Promise(resolve => setTimeout(resolve, 500));
    }

    alert(`批量平仓完成！\n✅ 成功: ${successCount}\n❌ 失败: ${failCount}`);
    refreshOrders();
}

async function fetchTradeLogs() {
    try {
        const response = await fetch('/api/logs');
        const data = await response.json();

        if (data.success) {
            updateTradeLogsDisplay(data.logs);
        }
    } catch (error) {
        console.error('获取交易日志失败:', error);
    }
}

function updateTradeLogsDisplay(logs) {
    const container = document.getElementById('tradeLogsContainer');

    if (!logs || logs.length === 0) {
        container.innerHTML = '<div style="text-align: center; padding: 40px; color: #94a3b8;">暂无操作日志</div>';
        return;
    }

    // 反向显示（最新的在上面）
    const reversedLogs = [...logs].reverse();

    container.innerHTML = reversedLogs.map(log => {
        const time = new Date(log.timestamp).toLocaleTimeString('zh-CN');
        const typeIcon = log.type === 'trade' ? '💰' : log.type === 'analysis' ? '🧠' : '⚙️';
        const statusClass = log.success ? 'success' : 'error';
        const statusIcon = log.success ? '✅' : '❌';

        // 根据操作类型设置颜色
        let actionColor = '#94a3b8';
        if (log.action === 'buy') actionColor = '#10b981';
        else if (log.action === 'sell') actionColor = '#ef4444';
        else if (log.action === 'close') actionColor = '#f59e0b';
        else if (log.action === 'analyze') actionColor = '#3b82f6';

        return `
            <div class="trade-log-item ${statusClass}">
                <div class="log-header">
                    <span class="log-icon">${typeIcon}</span>
                    <span class="log-time">${time}</span>
                    <span class="log-status">${statusIcon}</span>
                </div>
                <div class="log-body">
                    ${log.symbol ? `<span class="log-symbol">${log.symbol}</span>` : ''}
                    <span class="log-action" style="color: ${actionColor}">${getActionText(log.action)}</span>
                    <span class="log-message">${log.message}</span>
                </div>
                ${log.details && Object.keys(log.details).length > 0 ? `
                    <div class="log-details">
                        ${formatLogDetails(log.details)}
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

function getActionText(action) {
    const actionMap = {
        'buy': '开多',
        'sell': '开空',
        'close': '平仓',
        'analyze': 'AI分析',
        'auto_trade': '自动交易'
    };
    return actionMap[action] || action;
}

function formatLogDetails(details) {
    const items = [];
    if (details.amount) items.push(`数量: ${details.amount.toFixed(6)}`);
    if (details.price) items.push(`价格: $${details.price.toFixed(2)}`);
    if (details.size) items.push(`仓位: ${details.size.toFixed(6)}`);
    if (details.side) items.push(`方向: ${details.side === 'long' ? '多' : '空'}`);
    if (details.pnl !== undefined) items.push(`盈亏: ${details.pnl.toFixed(2)} USDT`);
    if (details.leverage) items.push(`杠杆: ${details.leverage}x`);
    if (details.signal) items.push(`信号: ${details.signal}`);
    if (details.confidence) items.push(`信心: ${details.confidence}`);
    if (details.reason) items.push(`理由: ${details.reason}`);

    return items.map(item => `<span class="detail-item">${item}</span>`).join('');
}

async function refreshTradeLogs() {
    await fetchTradeLogs();
}

// 配置弹窗功能
function openConfigModal() {
    const modal = document.getElementById('configModal');
    modal.classList.add('active');
    loadConfig();
}

function closeConfigModal() {
    const modal = document.getElementById('configModal');
    modal.classList.remove('active');
}

function switchConfigTab(tabName) {
    // 移除所有active类
    document.querySelectorAll('.config-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.config-panel').forEach(panel => {
        panel.classList.remove('active');
    });

    // 激活选中的标签
    event.target.classList.add('active');
    document.getElementById(tabName + 'Config').classList.add('active');
}

async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const result = await response.json();

        if (result.success) {
            const config = result.config;

            // 交易所配置
            document.getElementById('exchangeType').value = config.exchange_type || 'okx';
            document.getElementById('okxApiKey').value = config.okx_api_key || '';
            document.getElementById('okxSecret').value = config.okx_secret || '';
            document.getElementById('okxPassword').value = config.okx_password || '';
            document.getElementById('binanceApiKey').value = config.binance_api_key || '';
            document.getElementById('binanceSecret').value = config.binance_secret || '';

            // AI配置
            document.getElementById('aiModel').value = config.ai_model || 'deepseek';
            document.getElementById('useRelayApi').checked = config.use_relay_api || false;
            document.getElementById('relayApiBaseUrl').value = config.relay_api_base_url || '';
            document.getElementById('relayApiKey').value = config.relay_api_key || '';
            document.getElementById('deepseekApiKey').value = config.deepseek_api_key || '';
            document.getElementById('grokApiKey').value = config.grok_api_key || '';
            document.getElementById('claudeApiKey').value = config.claude_api_key || '';

            // 代理配置
            document.getElementById('httpProxy').value = config.http_proxy || '';
            document.getElementById('httpsProxy').value = config.https_proxy || '';

            // 交易配置
            document.getElementById('symbols').value = config.symbols || 'BTC/USDT,ETH/USDT';
            document.getElementById('amountUsd').value = config.amount_usd || '100';
            document.getElementById('leverage').value = config.leverage || '5';
        }
    } catch (error) {
        console.error('加载配置失败:', error);
        alert('加载配置失败: ' + error.message);
    }
}

async function saveConfig() {
    try {
        const config = {
            exchange_type: document.getElementById('exchangeType').value,
            okx_api_key: document.getElementById('okxApiKey').value,
            okx_secret: document.getElementById('okxSecret').value,
            okx_password: document.getElementById('okxPassword').value,
            binance_api_key: document.getElementById('binanceApiKey').value,
            binance_secret: document.getElementById('binanceSecret').value,
            ai_model: document.getElementById('aiModel').value,
            use_relay_api: document.getElementById('useRelayApi').checked,
            relay_api_base_url: document.getElementById('relayApiBaseUrl').value,
            relay_api_key: document.getElementById('relayApiKey').value,
            deepseek_api_key: document.getElementById('deepseekApiKey').value,
            grok_api_key: document.getElementById('grokApiKey').value,
            claude_api_key: document.getElementById('claudeApiKey').value,
            http_proxy: document.getElementById('httpProxy').value,
            https_proxy: document.getElementById('httpsProxy').value,
            symbols: document.getElementById('symbols').value,
            amount_usd: document.getElementById('amountUsd').value,
            leverage: document.getElementById('leverage').value
        };

        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });

        const result = await response.json();

        if (result.success) {
            alert('配置保存成功！\n\n' + result.message);
            closeConfigModal();

            if (result.restart_required) {
                if (confirm('配置已更新，需要重启应用使配置生效。\n是否现在刷新页面？')) {
                    window.location.reload();
                }
            }
        } else {
            alert('保存配置失败: ' + result.error);
        }
    } catch (error) {
        console.error('保存配置失败:', error);
        alert('保存配置失败: ' + error.message);
    }
}

// 点击弹窗外部关闭
document.addEventListener('click', (e) => {
    const modal = document.getElementById('configModal');
    if (e.target === modal) {
        closeConfigModal();
    }
});

// ==================== 策略管理功能 ====================
async function loadStrategies() {
    try {
        const response = await fetch('/api/strategies');
        const data = await response.json();

        if (data.success) {
            displayStrategies(data.strategies);
        } else {
            console.error('加载策略失败:', data.error);
        }
    } catch (error) {
        console.error('加载策略请求失败:', error);
    }
}

function displayStrategies(strategies) {
    const container = document.getElementById('strategiesGrid');
    if (!container) return;

    if (strategies.length === 0) {
        container.innerHTML = '<div style="text-align: center; padding: 40px; color: #94a3b8;">暂无可用策略</div>';
        return;
    }

    container.innerHTML = strategies.map(strategy => {
        const isRunning = strategy.status === 'running';
        const statusClass = isRunning ? 'running' : 'stopped';
        const statusText = isRunning ? '运行中' : '已停止';

        return `
            <div class="strategy-card ${statusClass}" id="strategy-${strategy.id}">
                <div class="strategy-header">
                    <div class="strategy-name">${strategy.name}</div>
                    <span class="strategy-status ${statusClass}">${statusText}</span>
                </div>
                <p class="strategy-description">${strategy.description}</p>
                <div class="strategy-actions">
                    <button class="btn-start"
                            onclick="startStrategy('${strategy.id}')"
                            ${isRunning ? 'disabled' : ''}>
                        ▶️ 启动
                    </button>
                    <button class="btn-stop"
                            onclick="stopStrategy('${strategy.id}')"
                            ${!isRunning ? 'disabled' : ''}>
                        ⏹️ 停止
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

async function startStrategy(strategyId) {
    if (!confirm('确定要启动这个策略吗？')) return;

    try {
        const response = await fetch(`/api/strategy/${strategyId}/start`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            showNotification(`✅ ${data.message}`, 'success');
            loadStrategies();
            fetchTradeLogs(); // 刷新日志
        } else {
            showNotification(`❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showNotification(`❌ 请求失败: ${error.message}`, 'error');
    }
}

async function stopStrategy(strategyId) {
    if (!confirm('确定要停止这个策略吗？')) return;

    try {
        const response = await fetch(`/api/strategy/${strategyId}/stop`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            showNotification(`✅ ${data.message}`, 'success');
            loadStrategies();
            fetchTradeLogs(); // 刷新日志
        } else {
            showNotification(`❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showNotification(`❌ 请求失败: ${error.message}`, 'error');
    }
}

function refreshStrategies() {
    loadStrategies();
    showNotification('🔄 策略列表已刷新', 'info');
}

// 简单的通知函数
function showNotification(message, type = 'info') {
    // 可以使用更复杂的通知库，这里简化处理
    alert(message);
}

// 初始化
fetchStatus();
fetchSpotBalance();
fetchMarkets();
fetchLogs();
fetchTradeLogs();
loadStrategies(); // 加载策略列表

updateInterval = setInterval(() => {
    fetchStatus();
    fetchSpotBalance();
    fetchMarkets();
    fetchLogs();
    fetchTradeLogs();
    loadStrategies(); // 定期刷新策略状态
}, 3000); // 每3秒更新（提高更新频率）

// 独立的价格更新循环（更频繁）
let priceUpdateInterval = setInterval(() => {
    updatePositionPNL();
}, 1000); // 每秒更新持仓PNL
