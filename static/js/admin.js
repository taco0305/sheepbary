async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        // Update Summary Cards
        document.getElementById('revenue-val').innerText = `$${data.total_revenue.toFixed(2)}`;
        document.getElementById('orders-val').innerText = data.total_orders;

        // Render Sales Trend Chart
        const dailyCtx = document.getElementById('salesChart').getContext('2d');
        const dailyLabels = data.daily_sales.map(s => s.date).reverse();
        const dailyTotals = data.daily_sales.map(s => s.total).reverse();

        new Chart(dailyCtx, {
            type: 'line',
            data: {
                labels: dailyLabels,
                datasets: [{
                    label: '每日營收',
                    data: dailyTotals,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.2)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                    x: { grid: { display: false } }
                }
            }
        });

        // Render Top Items Chart
        const itemsCtx = document.getElementById('topItemsChart').getContext('2d');
        const itemNames = data.top_items.map(i => i.name);
        const itemCounts = data.top_items.map(i => i.count);

        new Chart(itemsCtx, {
            type: 'bar',
            data: {
                labels: itemNames,
                datasets: [{
                    label: '銷售數量',
                    data: itemCounts,
                    backgroundColor: ['#a855f7', '#6366f1', '#22d3ee', '#f43f5e', '#fbbf24'],
                    borderRadius: 8
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    y: { grid: { display: false } },
                    x: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } }
                }
            }
        });

    } catch (err) {
        console.error('Failed to load statistics:', err);
    }
}

// Grok AI Insight Logic
const grokBtn = document.getElementById('grok-btn');
const grokResult = document.getElementById('grok-result');

grokBtn.addEventListener('click', async () => {
    grokResult.innerHTML = '<i class="fas fa-spinner fa-spin"></i> &nbsp; Grok 正在深入分析您的經營數據...';
    grokBtn.disabled = true;

    try {
        const response = await fetch('/api/ai_insight');
        const data = await response.json();

        // Convert newlines to breaks for simple markdown-like display
        const content = data.insight.replace(/\n/g, '<br>');
        grokResult.innerHTML = `<div style="text-align: left; width: 100%; animation: fadeIn 0.5s ease-out;">${content}</div>`;
    } catch (err) {
        grokResult.innerHTML = '<span style="color: #f43f5e;">分析失敗，請檢查網路連接或 API 設定。</span>';
    } finally {
        grokBtn.disabled = false;
    }
});

// Initial Load
loadStats();
