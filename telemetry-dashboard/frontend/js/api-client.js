window.DashboardAPI = {
  async request(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `Request failed (${response.status})`);
    }
    return response.json();
  },
  getPowerBudget() {
    return this.request("/api/power-budget");
  },
  updateCellCount(selectedCellCount) {
    return this.request("/api/mission-config", {
      method: "PATCH",
      body: JSON.stringify({ selected_cell_count: selectedCellCount }),
    });
  },
  getLatestTelemetry() {
    return this.request("/api/telemetry/latest");
  },
};
