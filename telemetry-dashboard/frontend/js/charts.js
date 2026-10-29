(function () {
  const colors = ["#9c87ff", "#62c9d4", "#e4ad68", "#64d9a1"];
  const commonLegend = { display: true, position: "bottom", labels: { color: "#aaa8b5", boxWidth: 7, boxHeight: 7, padding: 12, font: { family: "DM Mono", size: 8 } } };
  const commonTooltip = { backgroundColor: "#25232d", titleColor: "#f1f0f7", bodyColor: "#c2bfce", borderColor: "#46424f", borderWidth: 1, padding: 9, titleFont: { family: "DM Mono", size: 9 }, bodyFont: { family: "DM Mono", size: 9 } };
  let subsystemChart;
  let componentChart;
  let balanceChart;

  function chartOptions(legend = commonLegend) {
    return { responsive: true, maintainAspectRatio: false, plugins: { legend, tooltip: commonTooltip } };
  }

  function render(data, live) {
    if (!window.Chart) return;
    Chart.defaults.color = "#aaa8b5";
    Chart.defaults.font.family = "DM Mono";
    const subsystems = Object.entries(data.subsystem_draw_mW);
    const ranked = data.top_components.slice(0, 6);
    const subsystemData = { labels: subsystems.map(([name]) => name), datasets: [{ data: subsystems.map(([, value]) => value), backgroundColor: colors, borderColor: "#191820", borderWidth: 3, hoverOffset: 4 }] };
    const componentData = { labels: ranked.map((item) => item.name), datasets: [{ data: ranked.map((item) => item.energy_per_orbit_mWh), backgroundColor: ranked.map((_, index) => index === 0 ? "#9c87ff" : "rgba(156,135,255,.58)"), borderRadius: 2, barThickness: 13 }] };
    const balanceData = { labels: ["Generated", "Consumed"], datasets: [{ data: [live.generated, live.consumed], backgroundColor: ["#64d9a1", "#9c87ff"], borderColor: "#191820", borderWidth: 3, hoverOffset: 4 }] };
    if (!subsystemChart) {
      subsystemChart = new Chart(document.getElementById("subsystem-chart"), { type: "doughnut", data: subsystemData, options: { ...chartOptions(commonLegend), cutout: "72%" } });
      componentChart = new Chart(document.getElementById("component-chart"), { type: "bar", data: componentData, options: { ...chartOptions({ display: false }), indexAxis: "y", scales: { x: { grid: { color: "rgba(255,255,255,.06)" }, border: { display: false }, ticks: { color: "#85828e", font: { size: 8 } } }, y: { grid: { display: false }, border: { display: false }, ticks: { color: "#aaa8b5", font: { size: 8 } } } } } });
      balanceChart = new Chart(document.getElementById("balance-chart"), { type: "doughnut", data: balanceData, options: { ...chartOptions({ display: false }), cutout: "72%" } });
      return;
    }
    subsystemChart.data = subsystemData;
    componentChart.data = componentData;
    balanceChart.data = balanceData;
    balanceChart.data.datasets[0].backgroundColor = live.margin < 0 ? ["#64d9a1", "#ff777d"] : ["#64d9a1", "#9c87ff"];
    subsystemChart.update();
    componentChart.update();
    balanceChart.update();
  }

  window.DashboardCharts = { render };
})();
