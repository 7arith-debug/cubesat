(function () {
  const connection = document.getElementById("connection-state");
  let retryDelay = 1000;

  function setConnection(connected) {
    connection.classList.toggle("offline", !connected);
    connection.querySelector("span").textContent = connected ? "LIVE LINK" : "RECONNECTING";
  }

  window.renderTelemetry = function (frame, readings) {
    const value = (name, digits = 2) => {
      const reading = readings[name];
      const rawValue = typeof reading === "object" && reading !== null ? reading.value : reading;
      return rawValue !== undefined ? Number(rawValue).toFixed(digits) : "--";
    };
    document.getElementById("battery-voltage").textContent = value("battery_voltage", 2);
    document.getElementById("battery-soc").textContent = value("battery_soc", 1);
    document.getElementById("solar-power").textContent = value("solar_power", 2);
    document.getElementById("battery-temp").textContent = value("battery_temp", 1);
    document.getElementById("frame-info").textContent = `FRAME ${String(frame.sequence_number).padStart(5, "0")} · RSSI ${Number(frame.rssi).toFixed(0)} dBm`;
    document.getElementById("last-updated").textContent = `UPDATED ${new Date(frame.received_at).toLocaleTimeString()}`;
    const status = document.getElementById("eps-status");
    const socValue = readings.battery_soc;
    const soc = Number(typeof socValue === "object" && socValue !== null ? socValue.value : socValue ?? 0);
    status.classList.toggle("warn", soc < 25);
    status.classList.toggle("fault", soc < 12);
    status.textContent = soc < 12 ? "FAULT" : soc < 25 ? "WARN" : "OK";
  };

  function connect() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${location.host}/ws/telemetry`);
    socket.addEventListener("open", () => { retryDelay = 1000; setConnection(true); });
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "telemetry") window.renderTelemetry(message.frame, message.frame.readings);
    });
    socket.addEventListener("close", () => {
      setConnection(false);
      setTimeout(connect, retryDelay);
      retryDelay = Math.min(retryDelay * 1.7, 10000);
    });
    socket.addEventListener("error", () => socket.close());
  }

  connect();
})();
