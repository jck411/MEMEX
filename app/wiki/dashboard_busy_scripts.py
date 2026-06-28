"""Shared client-side busy overlay behavior.

Provides the JS functions that both the ingest page and source detail page
use to show a full-screen busy overlay when a long-running form submission
is in progress.  Included automatically via the shared page shell so that
page-specific scripts can call ``memexSetFormBusy`` without redeclaring it.
"""

from __future__ import annotations

BUSY_OVERLAY_JS = """
function memexShowBusyOverlay(titleText, detailText) {
  var overlay = document.getElementById("memex-busy-loader");
  if (!overlay) return;
  var title = overlay.querySelector("[data-busy-title]");
  var detail = overlay.querySelector("[data-busy-detail]");
  if (title) title.textContent = titleText;
  if (detail) detail.textContent = detailText;
  overlay.hidden = false;
  overlay.setAttribute("aria-busy", "true");
  document.documentElement.classList.add("busy-lock");
}

function memexSetFormBusy(form, buttonText, titleText, detailText) {
  if (!form || form.dataset.submitting === "1") return false;
  form.dataset.submitting = "1";
  form.setAttribute("aria-busy", "true");
  form.classList.add("is-submitting");
  form.querySelectorAll('button[type="submit"]').forEach(function (button) {
    button.dataset.originalText = button.textContent;
    button.textContent = buttonText;
    button.disabled = true;
  });
  memexShowBusyOverlay(titleText, detailText);
  return true;
}
"""
