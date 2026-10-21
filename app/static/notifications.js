document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-dismiss-notice]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.dismissNotice);
      if (target) {
        target.remove();
        const main = document.getElementById('main-content');
        if (main) main.focus();
      }
    });
  });
});
