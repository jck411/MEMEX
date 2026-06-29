"""Client-side behavior for dashboard action forms."""

from __future__ import annotations


def dashboard_script() -> str:
    return """
<script>
(function () {
  document.addEventListener("submit", function (event) {
    var buildForm = event.target.closest(".wiki-build-form");
    if (!buildForm) return;
    if (!memexSetFormBusy(
      buildForm,
      "Building...",
      "Building wiki",
      "Synthesizing accepted facts into markdown."
    )) {
      event.preventDefault();
    }
  });
})();
</script>
"""
