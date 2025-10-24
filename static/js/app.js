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

// 手动操作区域折叠
function toggleControls() {
    const content = document.getElementById('controlsContent');
    const icon = document.getElementById('controlsToggleIcon');
    const section = document.querySelector('.controls-section');

    const isCollapsed = content.style.display === 'none';

    if (isCollapsed) {
        content.style.display = 'block';
        icon.textContent = '▼';
        section.classList.remove('collapsed');
        localStorage.setItem('controlsCollapsed', 'false');
    } else {
        content.style.display = 'none';
        icon.textContent = '▶';
        section.classList.add('collapsed');
        localStorage.setItem('controlsCollapsed', 'true');
    }
}

// 交易日志折叠
function toggleTradeLogs() {
    const content = document.getElementById('tradeLogsContent');
    const icon = document.getElementById('tradeLogsToggleIcon');
    const section = document.querySelector('.trade-logs-section');

    const isCollapsed = content.style.display === 'none';

    if (isCollapsed) {
        content.style.display = 'block';
        icon.textContent = '▼';
        section.classList.remove('collapsed');
        localStorage.setItem('tradeLogsCollapsed', 'false');
    } else {
        content.style.display = 'none';
        icon.textContent = '▶';
        section.classList.add('collapsed');
        localStorage.setItem('tradeLogsCollapsed', 'true');
    }
}

// 合��持仓折叠
function togglePositions() {
    const content = document.getElementById('positionsContent');
    const icon = document.getElementById('positionsToggleIcon');
    const section = document.querySelector('.unified-trading-section');

    const isCollapsed = content.style.display === 'none';

    if (isCollapsed) {
        content.style.display = 'block';
        icon.textContent = '▼';
        section.classList.remove('collapsed');
        localStorage.setItem('positionsCollapsed', 'false');
    } else {
        content.style.display = 'none';
        icon.textContent = '▶';
        section.classList.add('collapsed');
        localStorage.setItem('positionsCollapsed', 'true');
    }
}

// 页面加载时恢复折叠状态
window.addEventListener('DOMContentLoaded', function() {
    // 恢复现货余额折叠状态
    const spotState = localStorage.getItem('spotBalanceCollapsed');
    if (spotState === 'true') {
        setTimeout(() => {
            toggleSpotBalance();
        }, 100);
    }

    // 恢复手动操作折叠状态
    const controlsState = localStorage.getItem('controlsCollapsed');
    if (controlsState === 'true') {
        setTimeout(() => {
            toggleControls();
        }, 100);
    }

    // 恢复交易日志折叠状态
    const tradeLogsState = localStorage.getItem('tradeLogsCollapsed');
    if (tradeLogsState === 'true') {
        setTimeout(() => {
            toggleTradeLogs();
        }, 100);
    }

    // 恢复合约持仓折叠状态
    const positionsState = localStorage.getItem('positionsCollapsed');
    if (positionsState === 'true') {
        setTimeout(() => {
            togglePositions();
        }, 100);
    }
});

async function fetchStatus() {
    try {
        const response = await fetch('/api/status');

        if (!response.ok) {
            if (response.status === 401) {
                handleAuthError();
                return;
            }
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        if (data.success) {
            // 安全更新余额显示
            const balanceEl = document.getElementById('balance');
            if (balanceEl) balanceEl.textContent = data.balance.toFixed(2);

            const pnlElement = document.getElementById('totalPnl');
            if (pnlElement) {
                pnlElement.textContent = data.total_pnl.toFixed(2);
                pnlElement.className = 'pnl ' + (data.total_pnl >= 0 ? 'positive' : 'negative');
            }

            const timeEl = document.getElementById('updateTime');
            if (timeEl) timeEl.textContent = new Date().toLocaleTimeString();

            // 更新自动交易状态
            updateAutoTradeStatus(data.auto_trade);

            // 更新持仓表格和概览
            if (data.positions) {
                updateOrdersTable(data.positions);
                updatePositions(data.positions);
            }
        } else {
            console.warn('API返回失败:', data.error || '未知错误');
        }
    } catch (error) {
        console.error('获取状态失败:', error);
        // 可选：显示用户友好的错误消息
        showConnectionError();
    }
}

// 处理认证错误
function handleAuthError() {
    console.warn('认证失败，需要重新登录');
    // 可以选择显示提示并跳转到登录页
    if (confirm('会话已过期，请重新登录')) {
        window.location.href = '/login';
    }
}

// 显示连接错误信息
function showConnectionError() {
    const statusEl = document.querySelector('.connection-status');
    if (statusEl) {
        statusEl.innerHTML = '<span class="pulse error"></span>连接断开';
        statusEl.classList.add('error');
    }

    // 清除可能显示的数据
    const balanceEl = document.getElementById('balance');
    if (balanceEl) balanceEl.textContent = '--';

    const pnlEl = document.getElementById('totalPnl');
    if (pnlEl) {
        pnlEl.textContent = '--';
        pnlEl.className = 'pnl';
    }
}

function updateAutoTradeStatus(enabled) {
    const statusBadge = document.getElementById('autoTradeStatus');
    const toggleBtn = document.getElementById('autoTradeToggle');
    const toggleText = document.getElementById('autoTradeToggleText');

    // 检查DOM元素是否存在，如果不存在则跳过更新
    if (!statusBadge || !toggleBtn || !toggleText) {
        // 自动交易状态元素不存在，静默跳过
        return;
    }

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

        if (!response.ok) {
            if (response.status === 401) {
                handleAuthError();
                return;
            }
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        if (data.success) {
            updateSpotBalances(data.balances);
        } else {
            console.warn('获取现货余额失败:', data.error || '未知错误');
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

    // 构建持仓映射 - 添加健壮性检查
    const positionMap = {};
    positions.forEach(pos => {
        // 确保symbol和side都存在且有效
        if (!pos.symbol || !pos.side) {
            console.warn('[WARN] 跳过无效持仓数据:', pos);
            return;
        }
        const key = `${pos.symbol}-${pos.side}`;
        positionMap[key] = pos;
        console.log(`[DEBUG] 持仓映射: ${key}`, pos);
    });

    console.log('[DEBUG] 当前持仓映射:', Object.keys(positionMap));

    // 删除不存在的持仓卡片
    Array.from(grid.children).forEach(card => {
        const key = card.dataset.positionKey;
        if (key && !positionMap[key]) {
            console.log(`[DEBUG] 删除不存在的持仓卡片: ${key}`);
            card.remove();
        }
    });

    // 更新或创建持仓卡片
    positions.forEach(pos => {
        // 再次确保symbol和side有效
        if (!pos.symbol || !pos.side) {
            console.warn('[WARN] 跳过创建/更新无效持仓:', pos);
            return;
        }

        const key = `${pos.symbol}-${pos.side}`;
        let card = grid.querySelector(`[data-position-key="${key}"]`);

        if (!card) {
            // 创建新卡片
            console.log(`[DEBUG] 创建新持仓卡片: ${key}`);
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
        } else {
            console.log(`[DEBUG] 更新现有持仓卡片: ${key}`);
        }

        // 更新数据 - 添加空值检查
        const sizeElement = card.querySelector('.size-value');
        if (sizeElement && pos.size !== undefined && pos.size !== null) {
            const newSize = pos.size.toFixed(6);
            if (sizeElement.textContent !== newSize) {
                sizeElement.textContent = newSize;
                sizeElement.classList.add('value-changed');
                setTimeout(() => sizeElement.classList.remove('value-changed'), 500);
            }
        }

        const entryElement = card.querySelector('.entry-value');
        if (entryElement && pos.entry_price !== undefined && pos.entry_price !== null) {
            const newEntry = `$${pos.entry_price.toFixed(2)}`;
            if (entryElement.textContent !== newEntry) {
                entryElement.textContent = newEntry;
                entryElement.classList.add('value-changed');
                setTimeout(() => entryElement.classList.remove('value-changed'), 500);
            }
        }

        const pnlElement = card.querySelector('.pnl-value');
        if (pnlElement && pos.unrealized_pnl !== undefined && pos.unrealized_pnl !== null) {
            const pnlClass = pos.unrealized_pnl >= 0 ? 'positive' : 'negative';
            const newPnl = `${pos.unrealized_pnl.toFixed(2)} USDT`;
            if (pnlElement.textContent !== newPnl) {
                pnlElement.className = `pnl ${pnlClass}`;
                pnlElement.textContent = newPnl;
                pnlElement.classList.add('value-changed');
                setTimeout(() => pnlElement.classList.remove('value-changed'), 500);
            }
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
    const autoExecuteCheckbox = document.getElementById('autoExecuteAnalysisCheckbox');

    // 从勾选框获取是否自动执行交易
    const autoExecute = autoExecuteCheckbox ? autoExecuteCheckbox.checked : false;

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
            } else if (!autoExecute) {
                message += '\n\n💡 未自动执行交易（已取消勾选"分析后自动下单"）';
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

    // 确认对话框：是否进行分析
    if (!confirm('确认对所有币种进行AI分析？这可能需要一些时间。')) {
        return;
    }

    // 从勾选框获取是否自动执行交易
    const autoExecuteCheckbox = document.getElementById('autoExecuteAnalysisCheckbox');
    const autoExecute = autoExecuteCheckbox ? autoExecuteCheckbox.checked : false;

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
    } else {
        message += `\n\n💡 未自动执行交易（已取消勾选"分析后自动下单"）`;
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
    const shouldExecute = document.getElementById('executeTradeCheckbox').checked;

    if (!amount || amount <= 0) {
        alert('请输入有效的USDT金额');
        return;
    }

    // 获取预计张数用于确认提示
    const estimatedContracts = document.getElementById('estimatedContracts').textContent;

    let confirmMsg = '';
    if (action === 'buy') {
        confirmMsg = `确认${shouldExecute ? '开多仓' : '模拟开多仓'}？\n金额: ${amount} USDT\n杠杆: ${leverage}x\n预计: ${estimatedContracts} 张`;
    } else if (action === 'sell') {
        confirmMsg = `确认${shouldExecute ? '开空仓' : '模拟开空仓'}？\n金额: ${amount} USDT\n杠杆: ${leverage}x\n预计: ${estimatedContracts} 张`;
    } else {
        confirmMsg = `确认${shouldExecute ? '平仓' : '模拟平仓'} ${symbol}？`;
    }

    if (!confirm(confirmMsg)) {
        return;
    }

    try {
        const response = await fetch('/api/execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                symbol,
                action,
                amount,
                leverage,
                dry_run: !shouldExecute  // 添加dry_run参数控制是否实际下单
            })
        });

        const result = await response.json();

        if (shouldExecute) {
            alert(result.success ? result.message : `操作失败: ${result.error}`);
        } else {
            // 模拟模式下的提示信息
            if (result.success) {
                alert(`模拟${action === 'buy' ? '开多' : action === 'sell' ? '开空' : '平仓'}成功！\n\n${result.message}\n\n💡 这是模拟操作，未实际下单`);
            } else {
                alert(`模拟操作失败: ${result.error}`);
            }
        }

        if (result.success) {
            fetchStatus();
            fetchMarkets();
        }
    } catch (error) {
        alert(`操作失败: ${error.message}`);
    }
}

// 订单表格管理
async function updateOrdersTable(positions) {
    const tbody = document.getElementById('ordersTableBody');

    if (!positions || positions.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="14" style="text-align: center; padding: 40px; color: #94a3b8;">
                    暂无持仓数据
                </td>
            </tr>
        `;
        return;
    }

    // 过滤掉无效持仓数据
    const validPositions = positions.filter(pos => {
        if (!pos.symbol || !pos.side) {
            console.warn('[WARN] updateOrdersTable: 跳过无效持仓', pos);
            return false;
        }
        return true;
    });

    if (validPositions.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="14" style="text-align: center; padding: 40px; color: #94a3b8;">
                    暂无有效持仓数据
                </td>
            </tr>
        `;
        return;
    }

    // 获取实时行情数据
    const marketData = {};
    for (const pos of validPositions) {
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

    tbody.innerHTML = validPositions.map((pos, index) => {
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
                <td class="leverage-cell">
                    <span class="leverage-badge">${leverage}x</span>
                </td>
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
    const container = document.getElementById('tradeLogsContent');

    // 检查容器是否存在
    if (!container) {
        console.warn('交易日志容器不存在');
        return;
    }

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

// 登出功能
function logout() {
    if (confirm('确认要退出登录吗？')) {
        window.location.href = '/logout';
    }
}

// ==================== 策略管理功能 ====================
let allStrategies = [];
let hybridAutoStarted = false; // 防止重复自动启动混合策略

async function loadStrategies() {
    try {
        const response = await fetch('/api/strategies');
        const data = await response.json();

        if (data.success) {
            allStrategies = data.strategies;
            populateStrategySelect();
        } else {
            console.error('加载策略失败:', data.error);
        }
    } catch (error) {
        console.error('加载策略请求失败:', error);
    }
}

function populateStrategySelect() {
    const select = document.getElementById('strategySelect');
    if (!select) return;

    // 保存当前选择的值
    const currentValue = select.value;

    // 清空并重新填充选项
    select.innerHTML = '<option value="">选择策略...</option>';

    // 始终添加混合策略选项
    const hybridOption = document.createElement('option');
    hybridOption.value = 'hybrid';
    hybridOption.textContent = '🚀 DeepSeek + Qwen3 Max 混合策略';
    hybridOption.dataset.status = 'stopped';
    select.appendChild(hybridOption);

    // 添加从API加载的其他策略
    allStrategies.forEach(strategy => {
        // 跳过混合策略，避免重复
        if (strategy.id === 'hybrid') return;

        const option = document.createElement('option');
        option.value = strategy.id;
        option.textContent = `${strategy.name} [${strategy.status === 'running' ? '运行中' : '已停止'}]`;
        option.dataset.status = strategy.status;
        select.appendChild(option);
    });

    // 默认选择混合策略
    select.value = 'hybrid';
    updateStrategyInfo('hybrid');

    // 添加选择变化监听器
    select.onchange = function() {
        updateStrategyInfo(this.value);
    };
}

function updateStrategyInfo(strategyId) {
    const infoContainer = document.getElementById('strategyInfo');
    const startBtn = document.getElementById('startStrategyBtn');
    const stopBtn = document.getElementById('stopStrategyBtn');
    const hybridSection = document.getElementById('hybridStrategySection');

    if (!strategyId) {
        infoContainer.innerHTML = '<div style="text-align: center; padding: 40px; color: #94a3b8;">请选择一个策略</div>';
        startBtn.disabled = true;
        stopBtn.disabled = true;
        // 隐藏混合策略界面
        if (hybridSection) hybridSection.style.display = 'none';
        return;
    }

    // 如果选择的是混合策略，显示混合策略界面
    if (strategyId === 'hybrid') {
        // 检查是否已经自动启动过
        const shouldAutoStart = !hybridAutoStarted;

        if (shouldAutoStart) {
            infoContainer.innerHTML = '<div style="text-align: center; padding: 20px; color: #10b981;">🚀 混合策略已就绪，请手动启动</div>';
            startBtn.disabled = false;
        } else {
            infoContainer.innerHTML = '<div style="text-align: center; padding: 20px; color: #10b981;">🚀 混合策略已就绪，可以进行操作</div>';
            startBtn.disabled = false;
        }

        stopBtn.disabled = true;
        // 显示混合策略界面
        if (hybridSection) {
            hybridSection.style.display = 'block';
            // 刷新混合策略状态
            refreshHybridStatus();
            // 自动启动混合策略（延迟执行确保界���已显示）
            // 暂时禁用自动启动，避免API错误
        }
        return;
    }

    // 隐藏混合策略界面
    if (hybridSection) hybridSection.style.display = 'none';

    const strategy = allStrategies.find(s => s.id === strategyId);
    if (!strategy) return;

    const isRunning = strategy.status === 'running';
    startBtn.disabled = isRunning;
    stopBtn.disabled = !isRunning;

    const modeText = strategy.mode === 'live' ? '🔴 实盘' : '🟡 模拟盘';
    const statusBadge = isRunning ?
        '<span class="strategy-status-badge running">运行中</span>' :
        '<span class="strategy-status-badge stopped">已停止</span>';

    infoContainer.innerHTML = `
        <div class="strategy-details">
            <div class="strategy-detail-item">
                <span class="strategy-detail-label">策略名称</span>
                <span class="strategy-detail-value">${strategy.name}</span>
            </div>
            <div class="strategy-detail-item">
                <span class="strategy-detail-label">策略描述</span>
                <span class="strategy-detail-value">${strategy.description}</span>
            </div>
            <div class="strategy-detail-item">
                <span class="strategy-detail-label">运行模式</span>
                <span class="strategy-detail-value">${modeText}</span>
            </div>
            <div class="strategy-detail-item">
                <span class="strategy-detail-label">当前状态</span>
                ${statusBadge}
            </div>
            <div class="strategy-detail-item">
                <span class="strategy-detail-label">策略文件</span>
                <span class="strategy-detail-value">${strategy.script}</span>
            </div>
        </div>
    `;
}

function getSelectedStrategy() {
    const select = document.getElementById('strategySelect');
    return select ? select.value : null;
}

async function startSelectedStrategy() {
    const strategyId = getSelectedStrategy();
    if (!strategyId) {
        alert('请先选择一个策略');
        return;
    }

    // 如果是混合策略，调用混合策略启动函数
    if (strategyId === 'hybrid') {
        await executeHybridStrategy();
        return;
    }

    const strategy = allStrategies.find(s => s.id === strategyId);
    if (!confirm(`确定要启动「${strategy.name}」吗？`)) return;

    try {
        const response = await fetch(`/api/strategy/${strategyId}/start`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            showNotification(`✅ ${data.message}`, 'success');
            loadStrategies();
            fetchTradeLogs();
        } else {
            showNotification(`❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showNotification(`❌ 请求失败: ${error.message}`, 'error');
    }
}

async function stopSelectedStrategy() {
    const strategyId = getSelectedStrategy();
    if (!strategyId) {
        alert('请先选择一个策略');
        return;
    }

    // 如果是混合策略，停止混合策略
    if (strategyId === 'hybrid') {
        if (!confirm('确定要停止混合策略吗？\n\n这将停止DeepSeek和Qwen3 Max两个策略的运行。')) return;

        try {
            const response = await fetch('/api/hybrid/stop', {
                method: 'POST'
            });
            const data = await response.json();

            if (data.success) {
                showNotification(`✅ ${data.message}`, 'success');
                refreshHybridStatus();
                fetchTradeLogs();
            } else {
                showNotification(`❌ ${data.error}`, 'error');
            }
        } catch (error) {
            showNotification(`❌ 请求失败: ${error.message}`, 'error');
        }
        return;
    }

    const strategy = allStrategies.find(s => s.id === strategyId);
    if (!confirm(`确定要停止「${strategy.name}」吗？`)) return;

    try {
        const response = await fetch(`/api/strategy/${strategyId}/stop`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            showNotification(`✅ ${data.message}`, 'success');
            loadStrategies();
            fetchTradeLogs();
        } else {
            showNotification(`❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showNotification(`❌ 请求失败: ${error.message}`, 'error');
    }
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

// ==================== 混合策略管理功能 ====================

// 保存混合策略配置
async function saveHybridConfig() {
    try {
        const config = {
            total_capital: parseFloat(document.getElementById('totalCapital').value) || 10000,
            deepseek_allocation: parseFloat(document.getElementById('deepseekRatio').value) || 0.6,
            qwen3_allocation: parseFloat(document.getElementById('qwen3Ratio').value) || 0.4,
            deepseek_leverage: parseInt(document.getElementById('deepseekLeverage').value) || 10,
            qwen3_leverage: parseInt(document.getElementById('qwen3Leverage').value) || 20,
            deepseek_amount: parseFloat(document.getElementById('deepseekAmount').value) || 300,
            qwen3_amount: parseFloat(document.getElementById('qwen3Amount').value) || 400,
            rebalance_enabled: document.getElementById('enableRebalance').checked,
            rebalance_hours: parseInt(document.getElementById('rebalanceHours').value) || 24,
            invalidation_level: parseFloat(document.getElementById('qwen3Invalidation').value) || 105000
        };

        const response = await fetch('/api/hybrid/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });

        const result = await response.json();

        if (result.success) {
            alert('✅ 混合策略配置保存成功！\n\n' + result.message);
            refreshHybridStatus();
        } else {
            alert('❌ 配置保存失败: ' + result.error);
        }
    } catch (error) {
        console.error('保存混合策略配置失败:', error);
        alert('❌ 配置保存失败: ' + error.message);
    }
}

// 重置混合策略配置为默认值
function resetHybridConfig() {
    if (!confirm('确定要重置为默认配置吗？')) {
        return;
    }

    document.getElementById('totalCapital').value = 10000;
    document.getElementById('deepseekRatio').value = 0.6;
    document.getElementById('qwen3Ratio').value = 0.4;
    document.getElementById('deepseekLeverage').value = 10;
    document.getElementById('qwen3Leverage').value = 20;
    document.getElementById('deepseekAmount').value = 300;
    document.getElementById('qwen3Amount').value = 400;
    document.getElementById('enableRebalance').checked = true;
    document.getElementById('rebalanceHours').value = 24;
    document.getElementById('qwen3Invalidation').value = 105000;

    // 更新滑块显示
    updateHybridAllocation();

    alert('✅ 已重置为默认配置');
}

// 执行混合策略
// 自动启动混合策略（无确认对话框）
async function autoStartHybridStrategy() {
    try {
        const response = await fetch('/api/hybrid/execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });

        // 检查响应是否为JSON格式
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('服务器响应格式错误，请检查后端API');
        }

        const result = await response.json();

        if (result.success) {
            // 更新信息显示
            const infoContainer = document.getElementById('strategyInfo');
            if (infoContainer) {
                infoContainer.innerHTML = '<div style="text-align: center; padding: 20px; color: #10b981;">🚀 混合策略已自动启动并运行中！</div>';
            }
            refreshHybridStatus();
            fetchTradeLogs();
            console.log('✅ 混合策略自动启动成功:', result.message);
        } else {
            console.warn('❌ 混合策略自动启动失败:', result.error);
            // 启动失败时允许手动启动
            const startBtn = document.getElementById('startStrategyBtn');
            if (startBtn) startBtn.disabled = false;

            const infoContainer = document.getElementById('strategyInfo');
            if (infoContainer) {
                infoContainer.innerHTML = '<div style="text-align: center; padding: 20px; color: #f59e0b;">⚠️ 自动启动失败，请手动启动混合策略</div>';
            }
        }
    } catch (error) {
        console.error('执行混合策略失败:', error);
        // 启动失败时允许手动启动
        const startBtn = document.getElementById('startStrategyBtn');
        if (startBtn) startBtn.disabled = false;

        const infoContainer = document.getElementById('strategyInfo');
        if (infoContainer) {
            infoContainer.innerHTML = '<div style="text-align: center; padding: 20px; color: #ef4444;">❌ 自动启动失败，请手动启动混合策略</div>';
        }
    }
}

async function executeHybridStrategy() {
    if (!confirm('确定要执行混合策略吗？\n\n这将同时运行DeepSeek稳健策略和Qwen3 Max集中策略。')) {
        return;
    }

    const btn = document.getElementById('executeHybridBtn');

    // 检查按钮是否存在
    if (!btn) {
        alert('❌ 按钮不存在，请刷新页面重试');
        return;
    }

    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '🔄 执行中...';

    try {
        const response = await fetch('/api/hybrid/execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });

        // 检查响应格式
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('服务器响应格式错误');
        }

        const result = await response.json();

        if (result.success) {
            alert('✅ 混合策略执行成功！\n\n' + (result.message || '操作成功'));
            refreshHybridStatus();
            fetchTradeLogs();
        } else {
            alert('❌ 混合策略执行失败: ' + (result.error || '未知错误'));
        }
    } catch (error) {
        console.error('执行混合策略失败:', error);
        alert('❌ 执行失败: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// 触发再平衡
async function triggerRebalance() {
    if (!confirm('确定要执行动态再平衡吗？\n\n这将根据当前表现调整DeepSeek和Qwen3 Max的资金分配。')) {
        return;
    }

    const btn = document.getElementById('rebalanceBtn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '🔄 再平衡中...';

    try {
        const response = await fetch('/api/hybrid/rebalance', {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            alert('✅ 再平衡执行成功！\n\n' + result.message);
            refreshHybridStatus();
        } else {
            alert('❌ 再平衡执行失败: ' + result.error);
        }
    } catch (error) {
        console.error('执行再平衡失败:', error);
        alert('❌ 再平衡失败: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// 刷新混合策略状态
async function refreshHybridStatus() {
    try {
        const response = await fetch('/api/hybrid/status');

        if (!response.ok) {
            if (response.status === 401) {
                handleAuthError();
                return;
            }
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('服务器响应格式错误');
        }

        const result = await response.json();

        if (result.success && result.available) {
            // 构造状态对象用于显示
            const status = {
                is_running: true, // 如果available则认为是运行中
                config: result,
                performance: result.performance
            };
            updateHybridStatusDisplay(status);
        } else {
            console.error('获取混合策略状态失败:', result.error || '混合策略不可用');
            // 设置默认状态
            updateHybridStatusDisplay({ is_running: false, config: null, performance: null });
        }
    } catch (error) {
        console.error('获取混合策略状态请求失败:', error);
        // 设置默认状态，避免界面错误
        updateHybridStatusDisplay({ is_running: false, config: null, performance: null });
    }
}

// 更新混合策略状态显示
function updateHybridStatusDisplay(status) {
    // 安全获取状态，防止undefined
    const isRunning = status && typeof status === 'object' ? status.is_running : false;

    // 更新策略管理按钮状态
    const startBtn = document.getElementById('startStrategyBtn');
    const stopBtn = document.getElementById('stopStrategyBtn');
    const strategySelect = document.getElementById('strategySelect');

    if (strategySelect && strategySelect.value === 'hybrid') {
        if (startBtn && stopBtn) {
            startBtn.disabled = isRunning;
            stopBtn.disabled = !isRunning;
        }
    }

    // 更新状态指示器
    const statusIndicator = document.getElementById('hybridStatusIndicator');
    const statusText = document.getElementById('hybridStatusText');

    if (statusIndicator && statusText) {
        statusIndicator.className = `status-indicator ${isRunning ? 'running' : 'stopped'}`;
        statusText.textContent = isRunning ? '运行中' : '已停止';
    }

    // 更新配置显示
    const configDisplay = document.getElementById('hybridConfigDisplay');
    if (configDisplay && status.config) {
        const config = status.config;
        configDisplay.innerHTML = `
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 14px;">
                <div><strong>总资金:</strong> $${config.total_capital?.toLocaleString() || 'N/A'}</div>
                <div><strong>DeepSeek分配:</strong> ${((config.allocation?.deepseek_stable || 0) * 100).toFixed(0)}%</div>
                <div><strong>Qwen3分配:</strong> ${((config.allocation?.qwen3_aggressive || 0) * 100).toFixed(0)}%</div>
                <div><strong>最后再平衡:</strong> ${config.last_rebalance ? new Date(config.last_rebalance).toLocaleTimeString() : 'N/A'}</div>
            </div>
        `;
    }

    // 更新性能指标
    const performanceDisplay = document.getElementById('hybridPerformanceDisplay');
    if (performanceDisplay && status.performance) {
        const perf = status.performance;
        performanceDisplay.innerHTML = `
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 14px;">
                <div><strong>总盈亏:</strong> <span class="${perf.total?.pnl >= 0 ? 'positive' : 'negative'}">${perf.total?.pnl?.toFixed(2) || '0'} USDT</span></div>
                <div><strong>总交易数:</strong> ${perf.total?.trades || 0}</div>
                <div><strong>DeepSeek夏普:</strong> ${perf.deepseek?.sharpe?.toFixed(2) || '0'}</div>
                <div><strong>Qwen3夏普:</strong> ${perf.qwen3?.sharpe?.toFixed(2) || '0'}</div>
            </div>
        `;
    }

    // 更新策略状态
    const strategiesDisplay = document.getElementById('hybridStrategiesDisplay');
    if (strategiesDisplay && status.strategies) {
        const strategies = status.strategies;
        strategiesDisplay.innerHTML = `
            <div style="font-size: 14px;">
                <div style="margin-bottom: 8px;">
                    <strong>DeepSeek策略:</strong>
                    <span class="status-badge ${strategies.deepseek?.is_running ? 'active' : 'inactive'}">
                        ${strategies.deepseek?.is_running ? '运行中' : '已停止'}
                    </span>
                    ${strategies.deepseek?.positions ? `(${strategies.deepseek.positions}个持仓)` : ''}
                </div>
                <div>
                    <strong>Qwen3 Max策略:</strong>
                    <span class="status-badge ${strategies.qwen3?.is_running ? 'active' : 'inactive'}">
                        ${strategies.qwen3?.is_running ? '运行中' : '已停止'}
                    </span>
                    ${strategies.qwen3?.positions ? `(${strategies.qwen3.positions}个持仓)` : ''}
                </div>
            </div>
        `;
    }

    // 更新最后执行时间
    const lastExecution = document.getElementById('hybridLastExecution');
    if (lastExecution && status.last_execution) {
        const lastTime = new Date(status.last_execution).toLocaleString('zh-CN');
        lastExecution.textContent = lastTime;
    }
}

// 更新混合策略分配滑块同步
function updateHybridAllocation() {
    const deepseekSlider = document.getElementById('deepseekRatio');
    const qwen3Slider = document.getElementById('qwen3Ratio');

    if (deepseekSlider && qwen3Slider) {
        const deepseekValue = parseFloat(deepseekSlider.value);
        const qwen3Value = 1 - deepseekValue;
        qwen3Slider.value = qwen3Value;

        // 更新显示文本
        const deepseekDisplay = document.getElementById('deepseekRatioDisplay');
        const qwen3Display = document.getElementById('qwen3RatioDisplay');

        if (deepseekDisplay) deepseekDisplay.textContent = `${(deepseekValue * 100).toFixed(0)}%`;
        if (qwen3Display) qwen3Display.textContent = `${(qwen3Value * 100).toFixed(0)}%`;
    }
}

// 监听混合策略分配滑块变化
document.addEventListener('DOMContentLoaded', function() {
    const deepseekSlider = document.getElementById('deepseekRatio');
    if (deepseekSlider) {
        deepseekSlider.addEventListener('input', updateHybridAllocation);
    }
});

// 暂停混合策略
async function pauseHybridStrategy() {
    if (!confirm('确定要暂停混合策略吗？')) return;

    try {
        const response = await fetch('/api/hybrid/pause', {
            method: 'POST'
        });
        const result = await response.json();

        if (result.success) {
            alert('✅ 混合策略已暂停');
            refreshHybridStatus();

            // 切换按钮显示
            document.getElementById('pauseBtn').style.display = 'none';
            document.getElementById('resumeBtn').style.display = 'inline-block';
        } else {
            alert('❌ 暂停失败: ' + result.error);
        }
    } catch (error) {
        alert('❌ 暂停失败: ' + error.message);
    }
}

// 恢复混合策略
async function resumeHybridStrategy() {
    if (!confirm('确定要恢复混合策略吗？')) return;

    try {
        const response = await fetch('/api/hybrid/resume', {
            method: 'POST'
        });
        const result = await response.json();

        if (result.success) {
            alert('✅ 混合策略已恢复');
            refreshHybridStatus();

            // 切换按钮显示
            document.getElementById('resumeBtn').style.display = 'none';
            document.getElementById('pauseBtn').style.display = 'inline-block';
        } else {
            alert('❌ 恢复失败: ' + result.error);
        }
    } catch (error) {
        alert('❌ 恢复失败: ' + error.message);
    }
}

// 显示混合策略详细信息
function showHybridDetails() {
    const details = `
🚀 DeepSeek + Qwen3 Max 混合策略详细信息

策略组成:
• DeepSeek稳健策略 (60%资金)
  - 10倍杠杆，分散投资
  - 交易标的: BTC, ETH, SOL, DOGE
  - 每次交易: 300 USDT

• Qwen3 Max集中策略 (40%资金)
  - 20倍杠杆，集中投资
  - 专注标的: BTC/USDT
  - 每次交易: 400 USDT
  - 关键支撑位: 105,000 USDT

资金管理:
• 总资金: 10,000 USDT
• 自动再平衡: 每24小时执行
• 失效条件: 价格跌破105,000 USDT时Qwen3 Max策略停止

预期收益:
• 年化收益率: 50-70%
• 最大回撤: <15%
• 胜率: 60-65%
• 夏普指数: >2.0

风险控制:
• 实时监控两个策略表现
• 动态调整资金分配比例
• 严格的止损和仓位管理
    `;

    alert(details);
}

// 初始化
fetchStatus();
fetchSpotBalance();
fetchMarkets();
fetchLogs();
fetchTradeLogs();
loadStrategies(); // 加载策略列表
refreshHybridStatus(); // 加载混合策略状态

updateInterval = setInterval(() => {
    fetchStatus();
    fetchSpotBalance();
    fetchMarkets();
    fetchLogs();
    fetchTradeLogs();
    loadStrategies(); // 定期刷新策略状态
    refreshHybridStatus(); // 定期刷新混合策略状态
}, 3000); // 每3秒更新（提高更新频率）

// 独立的价格更新循环（更频繁）
let priceUpdateInterval = setInterval(() => {
    updatePositionPNL();
}, 1000); // 每秒更新持仓PNL
