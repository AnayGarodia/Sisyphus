/**
 * Sisyphus Landing - Interactive with Parallax & Dark Mode
 * Synced theme system across landing and app
 */

class SisyphusLanding {
  constructor() {
    this.modals = {
      waitlist: document.getElementById("waitlistModal"),
      contact: document.getElementById("contactModal"),
    };

    this.toast = document.getElementById("successToast");
    this.nav = document.querySelector("nav");

    // Parallax elements
    this.parallaxFigure = document.querySelector(".parallax-figure");

    this.init();
  }

  init() {
    this.setupTheme();
    this.setupButtonListeners();
    this.setupModalListeners();
    this.setupFormListeners();
    this.setupSmoothScroll();
    this.setupParallaxScroll();
    this.setupNavScroll();
  }

  setupTheme() {
    // Use the same localStorage key as app.js for consistency
    const savedTheme = localStorage.getItem("sisyphus-theme");
    const prefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)"
    ).matches;

    if (savedTheme === "dark" || (!savedTheme && prefersDark)) {
      document.body.classList.add("dark-theme");
    }

    this.updateThemeIcon();
  }

  toggleTheme() {
    document.body.classList.toggle("dark-theme");
    const theme = document.body.classList.contains("dark-theme")
      ? "dark"
      : "light";
    // Use the same localStorage key as app.js
    localStorage.setItem("sisyphus-theme", theme);
    this.updateThemeIcon();
  }

  updateThemeIcon() {
    const themeToggle = document.querySelector(".theme-toggle-nav");
    if (!themeToggle) return;

    const isDark = document.body.classList.contains("dark-theme");
    themeToggle.innerHTML = isDark
      ? `<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="4"/>
        <path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32l1.41-1.41"/>
      </svg>`
      : `<svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
      </svg>`;
  }

  setupButtonListeners() {
    // Theme toggle
    const themeToggle = document.querySelector(".theme-toggle-nav");
    if (themeToggle) {
      themeToggle.addEventListener("click", () => this.toggleTheme());
    }

    // Launch Platform buttons
    const launchButtons = [
      document.getElementById("navLaunchBtn"),
      document.getElementById("heroGetStartedBtn"),
      document.getElementById("ctaLaunchBtn"),
      document.getElementById("footerLaunchLink"),
    ];

    launchButtons.forEach((btn) => {
      if (btn) {
        btn.addEventListener("click", () => this.handleLaunch());
      }
    });

    // Docs button
    const docsBtn = document.getElementById("heroDocsBtn");
    if (docsBtn) {
      docsBtn.addEventListener("click", () => {
        document.getElementById("how")?.scrollIntoView({
          behavior: "smooth",
        });
      });
    }

    // Contact sales
    document
      .getElementById("contactSalesBtn")
      ?.addEventListener("click", (e) => {
        e.preventDefault();
        this.openModal("contact");
      });

    // Footer contact
    document
      .getElementById("footerContactLink")
      ?.addEventListener("click", (e) => {
        e.preventDefault();
        this.openModal("contact");
      });
  }

  setupModalListeners() {
    // Close buttons
    document.querySelectorAll(".modal-close").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const modalId = e.target.dataset.modal;
        this.closeModal(modalId);
      });
    });

    // Click outside to close
    Object.values(this.modals).forEach((modal) => {
      modal.addEventListener("click", (e) => {
        if (e.target === modal) {
          this.closeModal(modal.id);
        }
      });
    });

    // Escape key to close
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        this.closeAllModals();
      }
    });
  }

  setupFormListeners() {
    // Waitlist form
    document.getElementById("waitlistForm")?.addEventListener("submit", (e) => {
      e.preventDefault();
      this.handleWaitlistSubmit(e.target);
    });

    // Contact form
    document.getElementById("contactForm")?.addEventListener("submit", (e) => {
      e.preventDefault();
      this.handleContactSubmit(e.target);
    });
  }

  setupSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
      anchor.addEventListener("click", (e) => {
        const href = anchor.getAttribute("href");
        if (href && href !== "#") {
          e.preventDefault();
          const target = document.querySelector(href);
          if (target) {
            target.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        }
      });
    });
  }

  setupParallaxScroll() {
    let ticking = false;

    window.addEventListener("scroll", () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          this.updateParallax();
          ticking = false;
        });
        ticking = true;
      }
    });

    // Initial position
    this.updateParallax();
  }

  updateParallax() {
    const scrolled = window.pageYOffset;
    const windowHeight = window.innerHeight;

    // Only apply parallax effect in the hero section
    if (scrolled < windowHeight * 1.5) {
      const progress = Math.min(scrolled / windowHeight, 1);

      // Figure moves upward as you scroll (climbing the hill)
      if (this.parallaxFigure) {
        const figureMovement = -scrolled * 0.6;
        const figureOpacity = Math.max(0.12, 0.5 - progress * 0.35);
        this.parallaxFigure.style.transform = `translateY(${figureMovement}px)`;
        this.parallaxFigure.style.opacity = figureOpacity;
      }
    }
  }

  setupNavScroll() {
    let lastScroll = 0;

    window.addEventListener("scroll", () => {
      const currentScroll = window.pageYOffset;

      if (currentScroll > 100) {
        this.nav.classList.add("scrolled");
      } else {
        this.nav.classList.remove("scrolled");
      }

      lastScroll = currentScroll;
    });
  }

  openModal(modalName) {
    const modal = this.modals[modalName];
    if (modal) {
      modal.classList.add("active");
      document.body.style.overflow = "hidden";
    }
  }

  closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove("active");
      document.body.style.overflow = "";
    }
  }

  closeAllModals() {
    Object.values(this.modals).forEach((modal) => {
      modal.classList.remove("active");
    });
    document.body.style.overflow = "";
  }

  handleLaunch() {
    // Navigate to /app route
    window.location.href = "/app";

    // Fallback: if app route doesn't exist, show waitlist
    setTimeout(() => {
      if (window.location.pathname !== "/app") {
        this.showToast("We're launching soon! Join the waitlist?");
        setTimeout(() => {
          this.openModal("waitlist");
        }, 2000);
      }
    }, 500);
  }

  async handleWaitlistSubmit(form) {
    const formData = new FormData(form);
    const data = {
      name: formData.get("name"),
      email: formData.get("email"),
      company: formData.get("company") || "",
      useCase: formData.get("useCase") || "",
    };

    // Log submission
    console.log("Waitlist submission:", data);

    // Show loading state
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = "Joining...";
    submitBtn.disabled = true;

    // Simulate API delay
    await new Promise((resolve) => setTimeout(resolve, 1500));

    // Success
    submitBtn.textContent = originalText;
    submitBtn.disabled = false;

    this.closeModal("waitlistModal");
    this.showToast(`Thanks ${data.name}! We'll be in touch soon.`);

    form.reset();
  }

  async handleContactSubmit(form) {
    const formData = new FormData(form);
    const data = {
      name: formData.get("name"),
      email: formData.get("email"),
      company: formData.get("company"),
      message: formData.get("message"),
    };

    // Log submission
    console.log("Contact form submission:", data);

    // Show loading state
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = "Sending...";
    submitBtn.disabled = true;

    // Simulate API delay
    await new Promise((resolve) => setTimeout(resolve, 1500));

    // Success
    submitBtn.textContent = originalText;
    submitBtn.disabled = false;

    this.closeModal("contactModal");
    this.showToast(`Thanks ${data.name}! We'll get back to you soon.`);

    form.reset();
  }

  showToast(message, duration = 4000) {
    const toastMessage = document.getElementById("toastMessage");
    toastMessage.textContent = message;

    this.toast.classList.add("show");

    setTimeout(() => {
      this.toast.classList.remove("show");
    }, duration);
  }
}

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  window.sisyphusLanding = new SisyphusLanding();
});
