document.addEventListener("DOMContentLoaded", () => {
  const viewer = document.getElementById("satellite-model");
  viewer.addEventListener("load", () => viewer.classList.add("model-ready"));
  viewer.addEventListener("error", () => {
    const label = document.querySelector(".model-caption");
    if (label) label.insertAdjacentHTML("beforeend", '<span class="mono">MODEL UNAVAILABLE</span>');
  });
});
