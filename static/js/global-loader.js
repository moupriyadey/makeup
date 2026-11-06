/* Moupriya global loading feedback.
   Navigation links: top progress bar.
   Form submissions: progress bar + submit-button spinner.
   Existing navigation, form actions, and page logic remain unchanged. */
(function () {
  "use strict";

  if (window.__mouGlobalLoaderInstalled) return;
  window.__mouGlobalLoaderInstalled = true;

  var progress = document.createElement("div");
  progress.id = "mouGlobalProgress";
  progress.setAttribute("aria-hidden", "true");
  progress.innerHTML = '<div class="mou-progress-bar"></div>';
  document.addEventListener("DOMContentLoaded", function () {
    if (!document.getElementById("mouGlobalProgress")) {
      document.body.appendChild(progress);
    }
  });

  var progressBar = null;
  var progressValue = 0;
  var progressTimer = null;

  function getProgressBar() {
    if (!document.getElementById("mouGlobalProgress") && document.body) {
      document.body.appendChild(progress);
    }
    progressBar = document.querySelector("#mouGlobalProgress .mou-progress-bar");
    return progressBar;
  }

  function startProgress() {
    var bar = getProgressBar();
    if (!bar) return;
    window.clearInterval(progressTimer);
    progressValue = 8;
    progress.classList.add("is-active");
    bar.style.width = progressValue + "%";

    progressTimer = window.setInterval(function () {
      if (progressValue < 88) {
        progressValue += Math.max(1, (88 - progressValue) * 0.075);
        bar.style.width = Math.min(progressValue, 88) + "%";
      }
    }, 220);
  }

  function resetProgress() {
    window.clearInterval(progressTimer);
    progressTimer = null;
    var bar = getProgressBar();
    if (!bar) return;
    bar.style.width = "100%";
    window.setTimeout(function () {
      progress.classList.remove("is-active");
      bar.style.width = "0";
      progressValue = 0;
    }, 180);
  }

  function isPlainLeftClick(event) {
    return event.button === 0 && !event.metaKey && !event.ctrlKey &&
      !event.shiftKey && !event.altKey;
  }

  function shouldHandleLink(link, event) {
    if (!link || !isPlainLeftClick(event)) return false;
    if (link.hasAttribute("data-no-loader") || link.hasAttribute("download")) return false;
    if (link.target && link.target.toLowerCase() !== "_self") return false;
    if (link.getAttribute("aria-disabled") === "true") return false;
    if (link.classList.contains("disabled")) return false;

    var href = (link.getAttribute("href") || "").trim();
    if (!href || href === "#" || /^(javascript:|mailto:|tel:)/i.test(href)) return false;

    try {
      var destination = new URL(href, window.location.href);
      if (destination.origin === window.location.origin &&
          destination.pathname === window.location.pathname &&
          destination.search === window.location.search &&
          destination.hash) return false;
    } catch (_) {
      return false;
    }
    return true;
  }

  document.addEventListener("click", function (event) {
    var link = event.target.closest ? event.target.closest("a[href]") : null;
    if (shouldHandleLink(link, event)) startProgress();
  }, true);

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form || form.tagName !== "FORM") return;
    if (form.dataset.mouSubmitting === "true") {
      event.preventDefault();
      return;
    }
    if (form.hasAttribute("data-no-loader")) return;
    if (form.target && form.target.toLowerCase() !== "_self") return;

    var submitter = event.submitter || document.activeElement;
    if (submitter && submitter.form !== form) submitter = null;

    form.dataset.mouSubmitting = "true";
    if (submitter && /^(submit|image)$/i.test(submitter.type || "")) {
      submitter.classList.add("mou-loader-active");
      submitter.setAttribute("aria-busy", "true");
      submitter.setAttribute("data-mou-loader-submitter", "true");
    }
    startProgress();
  }, true);

  window.addEventListener("pageshow", function () {
    document.querySelectorAll("[data-mou-loader-submitter]").forEach(function (button) {
      button.classList.remove("mou-loader-active");
      button.removeAttribute("aria-busy");
      button.removeAttribute("data-mou-loader-submitter");
    });
    document.querySelectorAll("form[data-mou-submitting]").forEach(function (form) {
      delete form.dataset.mouSubmitting;
    });
    resetProgress();
  });

  window.addEventListener("pagehide", function () {
    window.clearInterval(progressTimer);
  });
})();