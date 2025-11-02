/**
 * Sisyphus Landing Page - Interactive Functionality
 */

class LandingPage {
  constructor() {
    this.modals = {
      waitlist: document.getElementById("waitlistModal"),
      contact: document.getElementById("contactModal"),
      demo: document.getElementById("demoModal"),
    };

    this.toast = document.getElementById("successToast");
    this.loadingScreen = document.getElementById("loadingScreen");
    this.mainContent = document.getElementById("mainContent");

    this.init();
  }

  init() {
    this.setupLoadingAnimation();
    this.setupButtonListeners();
    this.setupModalListeners();
    this.setupFormListeners();
    this.setupSmoothScroll();
  }

  setupLoadingAnimation() {
    window.addEventListener("load", () => {
      setTimeout(() => {
        this.loadingScreen.classList.add("slide-up");

        setTimeout(() => {
          this.mainContent.classList.add("visible");
        }, 400);

        setTimeout(() => {
          this.loadingScreen.style.display = "none";
        }, 1200);
      }, 2500);
    });
  }

  setupButtonListeners() {
    // Launch Platform buttons
    const launchButtons = [
      document.getElementById("navLaunchBtn"),
      document.getElementById("heroGetStartedBtn"),
      document.getElementById("ctaLaunchBtn"),
      document.getElementById("footerLaunchLink"),
      document.getElementById("demoTryNowBtn"),
    ];

    launchButtons.forEach((btn) => {
      if (btn) {
        btn.addEventListener("click", () => this.handleLaunch());
      }
    });

    // Demo buttons
    const demoButtons = [
      document.getElementById("heroDemoBtn"),
      document.getElementById("demoPlayBtn"),
    ];

    demoButtons.forEach((btn) => {
      if (btn) {
        btn.addEventListener("click", () => this.openModal("demo"));
      }
    });

    // Action cards
    document.getElementById("waitlistBtn")?.addEventListener("click", () => {
      this.openModal("waitlist");
    });

    document.getElementById("contactBtn")?.addEventListener("click", () => {
      this.openModal("contact");
    });

    document.getElementById("productDemoBtn")?.addEventListener("click", () => {
      this.openModal("demo");
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
        e.preventDefault();
        const target = document.querySelector(anchor.getAttribute("href"));
        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
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
    // Check if running on same server
    const currentHost = window.location.host;

    // Try to navigate to /app route
    window.location.href = "/app";

    // If app route doesn't exist, show message
    setTimeout(() => {
      if (window.location.pathname !== "/app") {
        this.showToast(
          "Platform launching soon! Join the waitlist to get notified."
        );
        setTimeout(() => {
          this.openModal("waitlist");
        }, 2000);
      }
    }, 500);
  }

  async handleWaitlistSubmit(form) {
    const formData = new FormData(form);
    const data = {
      name:
        formData.get("name") || form.querySelector('input[type="text"]').value,
      email:
        formData.get("email") ||
        form.querySelector('input[type="email"]').value,
      company:
        formData.get("company") ||
        form.querySelectorAll('input[type="text"]')[1]?.value ||
        "",
      useCase:
        formData.get("useCase") || form.querySelector("textarea")?.value || "",
    };

    // Simulate API call
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
    this.showToast(
      `Thanks ${data.name}! You're on the waitlist. We'll be in touch soon! `
    );

    form.reset();
  }

  async handleContactSubmit(form) {
    const formData = new FormData(form);
    const data = {
      name:
        formData.get("name") || form.querySelector('input[type="text"]').value,
      email:
        formData.get("email") ||
        form.querySelector('input[type="email"]').value,
      subject:
        formData.get("subject") ||
        form.querySelectorAll('input[type="text"]')[1]?.value ||
        "",
      message:
        formData.get("message") || form.querySelector("textarea")?.value || "",
    };

    // Simulate API call
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
    this.showToast(
      `Message sent! We'll get back to you within 24 hours, ${data.name}! ️`
    );

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
  window.landingPage = new LandingPage();
});
