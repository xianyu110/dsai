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

async function fetchMarkets() {
    const symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'BNB/USDT'];
    const grid = document.getElementById('marketsGrid');
    grid.innerHTML = '';

    for (const symbol of symbols) {
        try {
            const response = await fetch(`/api/market/${symbol}`);
            const result = await response.json();

            if (result.success) {
                const data = result.data;
                const card = document.createElement('div');
                card.className = 'card';

                const changeClass = data.price_change >= 0 ? 'positive' : 'negative';

                card.innerHTML = `
                    <h3>${symbol}</h3>
                    <div class="card-data">
                        <div>价格: <strong>$${data.price.toFixed(2)}</strong></div>
                        <div>变化: <span class="pnl ${changeClass}">${data.price_change.toFixed(2)}%</span></div>
                        <div>最高: $${data.high.toFixed(2)}</div>
                        <div>最低: $${data.low.toFixed(2)}</div>
                    </div>
                `;
                grid.appendChild(card);
            }
        } catch (error) {
            console.error(`获取${symbol}数据失败:`, error);
        }
    }
}

function updatePositions(positions) {
    const grid = document.getElementById('positionsGrid');

    if (!positions || positions.length === 0) {
        grid.innerHTML = '<div class="card"><p>暂无持仓</p></div>';
        return;
    }

    grid.innerHTML = '';
    positions.forEach(pos => {
        const card = document.createElement('div');
        card.className = 'card';

        const sideColor = pos.side === 'long' ? '#10b981' : '#ef4444';
        const pnlClass = pos.unrealized_pnl >= 0 ? 'positive' : 'negative';

        card.innerHTML = `
            <h3>${pos.symbol}</h3>
            <div class="card-data">
                <div>方向: <strong style="color: ${sideColor}">${pos.side === 'long' ? '多' : '空'}</strong></div>
                <div>数量: ${pos.size.toFixed(6)}</div>
                <div>入场: $${pos.entry_price.toFixed(2)}</div>
                <div>盈亏: <span class="pnl ${pnlClass}">${pos.unrealized_pnl.toFixed(2)} USDT</span></div>
            </div>
        `;
        grid.appendChild(card);
    });
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
fetchMarkets();
updateInterval = setInterval(() => {
    fetchStatus();
    fetchMarkets();
}, 10000); // 每10秒更新
