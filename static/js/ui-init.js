import { animate } from "motion";
import autoAnimate from "@formkit/auto-animate";

document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) {
    window.lucide.createIcons();
  }

  const animatedContainers = document.querySelectorAll("[data-auto-animate]");
  animatedContainers.forEach((container) => {
    autoAnimate(container, { duration: 200, easing: "ease-in-out" });
  });

  window.toggleDrawer = (drawerEl, backdropEl, show) => {
    if (show) {
      drawerEl.classList.remove("hidden");
      backdropEl.classList.remove("hidden");
      animate(backdropEl, { opacity: [0, 0.5] }, { duration: 0.2 });
      animate(drawerEl, { transform: ["translateX(100%)", "translateX(0%)"] }, { duration: 0.25, easing: "ease-out" });
    } else {
      Promise.all([
        animate(drawerEl, { transform: ["translateX(0%)", "translateX(100%)"] }, { duration: 0.2 }).finished,
        animate(backdropEl, { opacity: [0.5, 0] }, { duration: 0.2 }).finished,
      ]).then(() => {
        drawerEl.classList.add("hidden");
        backdropEl.classList.add("hidden");
      });
    }
  };
});
