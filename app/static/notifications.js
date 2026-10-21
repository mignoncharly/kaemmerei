document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".notice, .alert").forEach((notification) => {
    window.setTimeout(() => {
      notification.classList.add("notification-dismissed");
      notification.setAttribute("aria-hidden", "true");
      window.setTimeout(() => notification.remove(), 300);
    }, 5000);
  });
});
