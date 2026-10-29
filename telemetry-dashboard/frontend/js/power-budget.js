(function () {
  let budget = null;
  let saveTimer = null;
  let toastTimer = null;

  function number(value, digits = 2) {
    return Number(value).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  function setText(id, value) {
    const node = document.getElementById(id);
    if (node) node.textContent = value;
  }

  function renderBudget(data) {
    budget = data;
    const count = Number(document.getElementById("cell-count").value) || data.config.selected_cell_count;
    const generated = count * Number(data.config.solar_cell_power_W);
    const consumed = data.total_power_W;
    const margin = generated - consumed;
    setText("cell-power", number(data.config.solar_cell_power_W, 2));
    setText("cell-spec", `CELL OUTPUT · ${number(data.config.solar_cell_power_W, 2)} W`);
    setText("generated-power", number(generated, 2));
    setText("selected-cell-display", String(count));
    setText("consumed-power", number(consumed, 2));
    setText("component-count", `${data.components.length} components in budget`);
    setText("component-config", `${data.components.length} COMPONENTS · ${number(data.total_power_mW, 0)} mW LOAD`);
    setText("power-margin", `${margin < 0 ? "−" : "+"}${number(Math.abs(margin), 2)}`);
    setText("chart-total", number(data.total_power_mW, 0));
    setText("balance-margin", `${margin < 0 ? "−" : "+"}${number(Math.abs(margin), 2)}`);
    setText("summary-mw", number(data.total_power_mW, 0));
    setText("summary-w", number(data.total_power_W, 3));
    setText("summary-orbit", number(data.energy_per_orbit_mWh, 0));
    setText("summary-orbits", number(data.orbits_per_day, 1));
    setText("summary-day", number(data.energy_per_day_mWh, 0));
    setText("orbit-spec", `ORBIT DURATION · ${number(data.config.orbit_duration_hours, 2)} H`);
    document.getElementById("margin-card").classList.toggle("negative", margin < 0);
    document.getElementById("margin-card").classList.toggle("positive", margin >= 0);

    const message = document.getElementById("budget-message");
    if (margin < 0) {
      message.classList.add("warning");
      message.textContent = `Power deficit of ${number(Math.abs(margin), 2)} W · add ${Math.ceil(Math.abs(margin) / data.config.solar_cell_power_W)} cell(s) to meet demand`;
    } else {
      message.classList.remove("warning");
      message.textContent = `Array meets demand with ${number(margin, 2)} W of surplus power`;
    }
    window.DashboardCharts?.render(data, { generated, consumed, margin });
  }

  function showToast() {
    const toast = document.getElementById("save-toast");
    toast.classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("visible"), 2200);
  }

  function queueSave(count) {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      try {
        const saved = await window.DashboardAPI.updateCellCount(count);
        renderBudget(saved);
        showToast();
      } catch (error) {
        document.getElementById("budget-message").textContent = `Could not save cell count: ${error.message}`;
      }
    }, 500);
  }

  async function start() {
    const input = document.getElementById("cell-count");
    try {
      const [data, latest] = await Promise.all([
        window.DashboardAPI.getPowerBudget(),
        window.DashboardAPI.getLatestTelemetry(),
      ]);
      input.value = data.config.selected_cell_count;
      renderBudget(data);
      if (latest.frame) window.renderTelemetry(latest.frame, latest.readings);
    } catch (error) {
      document.getElementById("budget-message").textContent = `Dashboard API unavailable: ${error.message}`;
      return;
    }
    input.addEventListener("input", () => {
      const count = Math.max(1, Math.min(10000, Math.floor(Number(input.value) || 1)));
      if (input.value !== "") renderBudget({ ...budget, config: { ...budget.config, selected_cell_count: count } });
      queueSave(count);
    });
    input.addEventListener("blur", () => {
      if (!input.value || Number(input.value) < 1) input.value = budget.config.selected_cell_count;
    });
  }

  window.renderPowerBudget = renderBudget;
  document.addEventListener("DOMContentLoaded", start);
})();
