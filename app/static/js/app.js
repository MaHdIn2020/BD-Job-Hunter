// Vanilla JS UI helpers: mobile navigation, flash message dismissal, and loading overlay.
document.addEventListener("DOMContentLoaded", () => {
    const menuBtn = document.getElementById("mobile-menu-btn");
    const mobileMenu = document.getElementById("mobile-menu");

    if (menuBtn && mobileMenu) {
        menuBtn.addEventListener("click", () => {
            const isHidden = mobileMenu.classList.toggle("hidden");
            menuBtn.setAttribute("aria-expanded", String(!isHidden));
        });
    }

    document.querySelectorAll("[data-dismiss-flash]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const banner = btn.closest("[data-flash-banner]");
            if (banner) {
                banner.remove();
            }
        });
    });

    document.querySelectorAll("form[data-show-loading]").forEach((form) => {
        form.addEventListener("submit", () => {
            const loader = document.getElementById("global-loading");
            if (loader) {
                loader.classList.remove("hidden");
            }
        });
    });
});

