<script>
  let { usage } = $props();

  const MIN_Y_AXIS = 10;
  const DAYS_TO_SHOW = 30;

  const PROVIDERS = [
    { key: "openai", name: "OpenAI", color: "#10a37f" },
    { key: "anthropic", name: "Anthropic", color: "#e07a5f" },
    { key: "google", name: "Google", color: "#4285f4" },
    { key: "custom", name: "Custom", color: "#8b5cf6" },
  ];

  const PROVIDER_COLORS = Object.fromEntries(PROVIDERS.map(p => [p.key, p.color]));

  function toDateString(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  const chartData = $derived(() => {
    const data = [];
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    for (let i = DAYS_TO_SHOW - 1; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);
      const dateStr = toDateString(date);
      const existing = usage?.daily?.find((d) => d.date === dateStr);
      data.push({
        date: dateStr,
        requests: existing?.requests || 0,
        by_provider: existing?.by_provider || {},
      });
    }
    return data;
  });

  const providerData = $derived(() => {
    const providers = usage?.by_provider || {};
    const total = Object.values(providers).reduce((a, b) => a + b, 0);
    if (total === 0) return [];

    let cumulative = 0;
    return Object.entries(providers).map(([name, count]) => {
      const start = cumulative;
      const percentage = (count / total) * 100;
      cumulative += percentage;
      return {
        name,
        count,
        percentage,
        startAngle: (start / 100) * 360,
        endAngle: (cumulative / 100) * 360,
        color: PROVIDER_COLORS[name] || "#6b7280",
      };
    });
  });

  const legendData = $derived(() => {
    const providers = usage?.by_provider || {};
    return PROVIDERS.map(p => ({
      ...p,
      count: providers[p.key] || 0,
    }));
  });

  const hasData = $derived(() => {
    const providers = usage?.by_provider || {};
    return Object.values(providers).reduce((a, b) => a + b, 0) > 0;
  });

  function isFullCircle(startAngle, endAngle) {
    return (endAngle - startAngle) >= 359.99;
  }

  function getDonutPath(startAngle, endAngle, radius = 40, innerRadius = 28) {
    const startRad = ((startAngle - 90) * Math.PI) / 180;
    const endRad = ((endAngle - 90) * Math.PI) / 180;

    const x1 = 50 + radius * Math.cos(startRad);
    const y1 = 50 + radius * Math.sin(startRad);
    const x2 = 50 + radius * Math.cos(endRad);
    const y2 = 50 + radius * Math.sin(endRad);
    const x3 = 50 + innerRadius * Math.cos(endRad);
    const y3 = 50 + innerRadius * Math.sin(endRad);
    const x4 = 50 + innerRadius * Math.cos(startRad);
    const y4 = 50 + innerRadius * Math.sin(startRad);

    const largeArc = (endAngle - startAngle) > 180 ? 1 : 0;

    return `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} L ${x3} ${y3} A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${x4} ${y4} Z`;
  }

  const maxY = $derived(() => {
    const maxRequests = Math.max(...chartData().map((d) => d.requests), 0);
    return Math.max(maxRequests, MIN_Y_AXIS);
  });

  const yAxisTicks = $derived(() => {
    const max = maxY();
    if (max <= 10) return [0, 5, 10];
    if (max <= 50) return [0, 25, 50];
    if (max <= 100) return [0, 50, 100];
    const step = Math.ceil(max / 4 / 10) * 10;
    return [0, step, step * 2, step * 3, Math.ceil(max / 10) * 10];
  });

  function formatNumber(num) {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  }

  function getBarHeight(requests) {
    const max = maxY();
    if (max === 0) return 0;
    return (requests / max) * 100;
  }

  function formatDate(dateStr) {
    const [year, month, day] = dateStr.split('-').map(Number);
    const date = new Date(year, month - 1, day);
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  function formatProviderName(name) {
    const names = {
      openai: "OpenAI",
      anthropic: "Anthropic",
      google: "Google",
      custom: "Custom",
    };
    return names[name] || name;
  }
</script>

<div class="usage-chart">
  <div class="usage-stats">
    <div class="stat-card">
      <span class="stat-value">{formatNumber(usage?.total_requests || 0)}</span>
      <span class="stat-label">Total Requests</span>
    </div>
    <div class="stat-card">
      <span class="stat-value">{formatNumber(usage?.total_tokens || 0)}</span>
      <span class="stat-label">Total Tokens</span>
    </div>
    <div class="stat-card provider-card">
      <div class="donut-container">
        <svg viewBox="0 0 100 100" class="donut-chart">
          {#if hasData()}
            {#each providerData() as segment}
              {#if isFullCircle(segment.startAngle, segment.endAngle)}
                <circle
                  cx="50"
                  cy="50"
                  r="34"
                  fill="none"
                  stroke={segment.color}
                  stroke-width="12"
                  class="donut-segment"
                >
                  <title>{formatProviderName(segment.name)}: {segment.count}</title>
                </circle>
              {:else}
                <path
                  d={getDonutPath(segment.startAngle, segment.endAngle)}
                  fill={segment.color}
                  class="donut-segment"
                >
                  <title>{formatProviderName(segment.name)}: {segment.count}</title>
                </path>
              {/if}
            {/each}
          {:else}
            <circle cx="50" cy="50" r="34" fill="none" stroke="#e5e7eb" stroke-width="12" />
          {/if}
        </svg>
        <div class="donut-center">
          <span class="donut-total">{usage?.total_requests || 0}</span>
        </div>
      </div>
      <div class="provider-legend">
        {#each legendData() as item}
          <div class="legend-item" class:has-data={item.count > 0}>
            <span class="legend-dot" style="background: {item.color}"></span>
            <span class="legend-name">{item.name}</span>
            <span class="legend-count">{item.count}</span>
          </div>
        {/each}
      </div>
      <span class="stat-label">By Provider</span>
    </div>
  </div>

  <div class="chart-container">
    <h4 class="chart-title">Daily Requests (Last 30 Days)</h4>
    <div class="chart-wrapper">
      <div class="y-axis">
        {#each [...yAxisTicks()].reverse() as tick}
          <span class="y-tick">{tick}</span>
        {/each}
      </div>
      <div class="chart-area">
        <div class="grid-lines">
          {#each yAxisTicks() as tick}
            <div class="grid-line" style="bottom: {(tick / maxY()) * 100}%"></div>
          {/each}
        </div>
        <div class="bar-chart">
          {#each chartData() as day}
            <div class="bar-wrapper" title="{formatDate(day.date)}: {day.requests} requests">
              <div class="stacked-bar" style="height: {getBarHeight(day.requests)}%">
                {#each PROVIDERS as provider}
                  {#if day.by_provider[provider.key]}
                    <div
                      class="bar-segment"
                      style="height: {(day.by_provider[provider.key] / day.requests) * 100}%; background: {provider.color};"
                      title="{provider.name}: {day.by_provider[provider.key]}"
                    ></div>
                  {/if}
                {/each}
              </div>
            </div>
          {/each}
        </div>
      </div>
    </div>
    <div class="chart-labels">
      <span>{formatDate(chartData()[0].date)}</span>
      <span>{formatDate(chartData()[chartData().length - 1].date)}</span>
    </div>
  </div>
</div>

<style>
  .usage-chart {
    width: 100%;
  }

  .usage-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .stat-card {
    background: var(--bg-secondary);
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
  }

  .stat-value {
    display: block;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 0.25rem;
  }

  .stat-label {
    display: block;
    font-size: 0.75rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .provider-card {
    padding: 0.75rem;
  }

  .donut-container {
    position: relative;
    width: 70px;
    height: 70px;
    margin-bottom: 0.5rem;
  }

  .donut-chart {
    width: 100%;
    height: 100%;
  }

  .donut-segment {
    transition: opacity 0.15s;
    cursor: default;
  }

  .donut-segment:hover {
    opacity: 0.8;
  }

  .donut-center {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .donut-total {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--text-primary);
  }

  .provider-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    justify-content: center;
    margin-bottom: 0.5rem;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.7rem;
    opacity: 0.4;
  }

  .legend-item.has-data {
    opacity: 1;
  }

  .legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .legend-name {
    color: var(--text-secondary);
  }

  .legend-count {
    font-weight: 600;
    color: var(--text-primary);
  }

  .chart-container {
    background: var(--bg-secondary);
    border-radius: 8px;
    padding: 1rem;
  }

  .chart-title {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-secondary);
    margin: 0 0 1rem 0;
  }

  .chart-wrapper {
    display: flex;
    gap: 0.5rem;
  }

  .y-axis {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 120px;
    padding: 0;
    width: 30px;
    flex-shrink: 0;
  }

  .y-tick {
    font-size: 0.7rem;
    color: var(--text-secondary);
    text-align: right;
    line-height: 1;
  }

  .chart-area {
    flex: 1;
    position: relative;
    height: 120px;
  }

  .grid-lines {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  .grid-line {
    position: absolute;
    left: 0;
    right: 0;
    height: 1px;
    background: var(--border-light);
  }

  .bar-chart {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 100%;
    position: relative;
    z-index: 1;
  }

  .bar-wrapper {
    flex: 1;
    height: 100%;
    display: flex;
    align-items: flex-end;
  }

  .stacked-bar {
    width: 100%;
    min-height: 0;
    display: flex;
    flex-direction: column;
    border-radius: 2px 2px 0 0;
    overflow: hidden;
    transition: height 0.3s ease;
  }

  .bar-segment {
    width: 100%;
    flex-shrink: 0;
    transition: opacity 0.15s;
  }

  .bar-segment:first-child {
    border-radius: 2px 2px 0 0;
  }

  .bar-wrapper:hover .bar-segment {
    opacity: 0.85;
  }

  .chart-labels {
    display: flex;
    justify-content: space-between;
    margin-top: 0.5rem;
    margin-left: 38px;
    font-size: 0.75rem;
    color: var(--text-secondary);
  }

  @media (max-width: 600px) {
    .usage-stats {
      grid-template-columns: 1fr;
    }
  }
</style>
