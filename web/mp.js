window.ST_MCU_MP = false;
try {
  window.ST_MCU_MP = new URLSearchParams(window.location.search).get("mp") === "1";
} catch (error) {
  window.ST_MCU_MP = false;
}
if (window.ST_MCU_MP) {
  document.documentElement.classList.add("is-mp");
}
