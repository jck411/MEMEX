"""Shared viewport position persistence for dashboard POST actions."""

from __future__ import annotations

POSITION_PERSISTENCE_JS = """
(function () {
  var positionKey = "memex:page-position";
  var rowSelectors = {
    source: ".source-row",
    wiki: ".wiki-row",
    fact: ".fact-row",
    issue: ".issue-row"
  };

  function storage() {
    try {
      return window.sessionStorage;
    } catch (error) {
      return null;
    }
  }

  function pathOnly(value) {
    try {
      return new URL(value, window.location.href).pathname || "/";
    } catch (error) {
      return window.location.pathname || "/";
    }
  }

  function returnPath(form) {
    var returnTo = form.querySelector('input[name="return_to"]');
    if (returnTo && returnTo.value && returnTo.value.charAt(0) === "/") {
      return pathOnly(returnTo.value);
    }
    return window.location.pathname || "/";
  }

  function rowKind(row) {
    if (!row) return "";
    if (row.classList.contains("source-row")) return "source";
    if (row.classList.contains("wiki-row")) return "wiki";
    if (row.classList.contains("fact-row")) return "fact";
    if (row.classList.contains("issue-row")) return "issue";
    return "";
  }

  function rowId(row, kind) {
    if (!row) return "";
    if (kind === "source") return row.getAttribute("data-source-id") || "";
    if (kind === "wiki") return row.getAttribute("data-wiki-id") || "";
    if (kind === "fact") return row.getAttribute("data-fact-id") || "";
    if (kind === "issue") return row.getAttribute("data-issue-index") || "";
    return "";
  }

  function rowList(kind) {
    var selector = rowSelectors[kind];
    return selector ? Array.prototype.slice.call(document.querySelectorAll(selector)) : [];
  }

  function rowIndex(row, kind) {
    return rowList(kind).indexOf(row);
  }

  function sameKindRow(node, kind) {
    return node && rowKind(node) === kind ? node : null;
  }

  function adjacentAnchor(row, kind) {
    if (!row) return null;
    var rowTop = row.getBoundingClientRect().top;
    var next = sameKindRow(row.nextElementSibling, kind);
    if (next) return { row: next, top: rowTop };
    var previous = sameKindRow(row.previousElementSibling, kind);
    if (previous) return { row: previous, top: previous.getBoundingClientRect().top };
    return null;
  }

  function isRemoval(form, submitter) {
    var action = form.getAttribute("action") || "";
    var name = submitter ? submitter.getAttribute("name") || "" : "";
    return action.indexOf("/delete-") === 0 || name.indexOf("delete_") === 0;
  }

  function anchorFor(form, submitter) {
    var row = form.closest(".source-row, .wiki-row, .fact-row, .issue-row");
    var kind = rowKind(row);
    if (!row || !kind) return null;
    if (isRemoval(form, submitter)) return adjacentAnchor(row, kind);
    return { row: row, top: row.getBoundingClientRect().top };
  }

  function rememberPagePosition(form, submitter) {
    var store = storage();
    if (!store) return;
    var anchor = anchorFor(form, submitter);
    var anchorRow = anchor ? anchor.row : null;
    var kind = rowKind(anchorRow);
    var payload = {
      targetPath: returnPath(form),
      scrollX: window.scrollX || 0,
      scrollY: window.scrollY || 0,
      anchorKind: kind,
      anchorId: rowId(anchorRow, kind),
      anchorIndex: kind ? rowIndex(anchorRow, kind) : -1,
      anchorTop: anchor ? anchor.top : 0,
      createdAt: Date.now()
    };
    try {
      store.setItem(positionKey, JSON.stringify(payload));
    } catch (error) {
      return;
    }
  }

  function rowFromPayload(payload) {
    var kind = payload.anchorKind || "";
    if (!kind) return null;
    var rows = rowList(kind);
    var id = payload.anchorId || "";
    if (id) {
      for (var index = 0; index < rows.length; index += 1) {
        if (rowId(rows[index], kind) === id) return rows[index];
      }
    }
    var fallbackIndex = Number(payload.anchorIndex);
    return Number.isFinite(fallbackIndex) && fallbackIndex >= 0 ? rows[fallbackIndex] : null;
  }

  function restorePagePosition() {
    var store = storage();
    if (!store) return;
    var raw = "";
    try {
      raw = store.getItem(positionKey);
      store.removeItem(positionKey);
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
    if (payload.targetPath && payload.targetPath !== (window.location.pathname || "/")) return;

    window.requestAnimationFrame(function () {
      window.requestAnimationFrame(function () {
        var x = Number(payload.scrollX) || 0;
        var y = Number(payload.scrollY) || 0;
        var anchor = rowFromPayload(payload);
        var anchorTop = Number(payload.anchorTop);
        if (anchor && Number.isFinite(anchorTop)) {
          y = window.scrollY + anchor.getBoundingClientRect().top - anchorTop;
        }
        window.scrollTo(x, Math.max(0, y));
      });
    });
  }

  document.addEventListener("submit", function (event) {
    if (event.defaultPrevented) return;
    var form = event.target.closest("form");
    if (!form) return;
    var method = (form.getAttribute("method") || "get").toLowerCase();
    if (method !== "post") return;
    rememberPagePosition(form, event.submitter || null);
  });

  restorePagePosition();
})();
"""
