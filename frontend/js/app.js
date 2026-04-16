/**
 * SafeFlow.ai — Global app utilities
 * Button micro-interactions, mobile tabs, shared helpers.
 */

window.addEventListener("DOMContentLoaded", () => {
    // Button press micro-animations
    document.addEventListener("mousedown", (e) => {
        if (e.target.tagName === "BUTTON" || e.target.classList.contains("btn-primary")) {
            e.target.style.transform = "scale(0.97)";
        }
    });
    document.addEventListener("mouseup", (e) => {
        if (e.target.tagName === "BUTTON" || e.target.classList.contains("btn-primary")) {
            e.target.style.transform = "";
        }
    });
});

function initMobileTabs() {
    const tabs = document.querySelectorAll(".nav-tab");
    tabs.forEach(t => {
        t.addEventListener("click", function () {
            tabs.forEach(ti => ti.classList.remove("active"));
            this.classList.add("active");
        });
    });
}
