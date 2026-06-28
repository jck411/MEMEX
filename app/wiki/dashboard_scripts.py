"""Client-side behavior for dashboard action forms."""

from __future__ import annotations


def dashboard_script() -> str:
    return """
<script>
(function () {
  var scrollKey = "memex:source-delete-scroll";

  function storage() {
    try {
      return window.sessionStorage;
    } catch (error) {
      return null;
    }
  }

  function sourceRowById(sourceId) {
    var rows = document.querySelectorAll(".source-row[data-source-id]");
    for (var index = 0; index < rows.length; index += 1) {
      if (rows[index].dataset.sourceId === sourceId) return rows[index];
    }
    return null;
  }

  function adjacentSourceRow(row) {
    if (!row) return null;
    var next = row.nextElementSibling;
    if (next && next.classList.contains("source-row")) return next;
    var previous = row.previousElementSibling;
    if (previous && previous.classList.contains("source-row")) return previous;
    return null;
  }

  function rememberDeletePosition(form) {
    var store = storage();
    if (!store) return;
    var row = form.closest(".source-row");
    var anchor = adjacentSourceRow(row);
    var top = row ? row.getBoundingClientRect().top : 0;
    var payload = {
      scrollX: window.scrollX || 0,
      scrollY: window.scrollY || 0,
      anchorSourceId: anchor ? anchor.dataset.sourceId || "" : "",
      anchorTop: top
    };
    try {
      store.setItem(scrollKey, JSON.stringify(payload));
    } catch (error) {
      return;
    }
  }

  function restoreDeletePosition() {
    var store = storage();
    if (!store) return;
    var raw = "";
    try {
      raw = store.getItem(scrollKey);
      store.removeItem(scrollKey);
    } catch (error) {
      return;
    }
    if (!raw) return;

    var payload;
    try {
      payload = JSON.parse(raw);
    } catch (error) {
      return;
    }

    window.requestAnimationFrame(function () {
      var x = Number(payload.scrollX) || 0;
      var y = Number(payload.scrollY) || 0;
      if (payload.anchorSourceId) {
        var anchor = sourceRowById(payload.anchorSourceId);
        var anchorTop = Number(payload.anchorTop);
        if (anchor && Number.isFinite(anchorTop)) {
          y = window.scrollY + anchor.getBoundingClientRect().top - anchorTop;
        }
      }
      window.scrollTo(x, Math.max(0, y));
    });
  }

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

  document.addEventListener("submit", function (event) {
    var deleteForm = event.target.closest('form[data-source-delete-form="1"]');
    if (!deleteForm) return;
    rememberDeletePosition(deleteForm);
  });

  restoreDeletePosition();
})();
</script>
"""
