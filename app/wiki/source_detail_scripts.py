"""Client-side behavior for source detail pages."""

from __future__ import annotations


def source_detail_script() -> str:
    return """
<script>
function markDecisionDirty(form, key) {
  if (!form || !key) return false;
  const existing = form.querySelectorAll('input[type="hidden"][name="changed_decision"]');
  for (const input of existing) {
    if (input.value === key) return false;
  }
  const marker = document.createElement("input");
  marker.type = "hidden";
  marker.name = "changed_decision";
  marker.value = key;
  form.appendChild(marker);
  return true;
}

function markWikiDecisionsDirty(form, wikiId) {
  if (!form || !wikiId) return false;
  let changed = false;
  document.querySelectorAll('input[type="checkbox"][name="accepted_decision"]').forEach(function (input) {
    if (input.form !== form || input.getAttribute("data-wiki-id") !== wikiId) return;
    changed = markDecisionDirty(form, input.getAttribute("data-decision-key")) || changed;
  });
  return changed;
}

function submitDecisionForm(form) {
  if (!form || form.dataset.submitting === "1") return;
  if (typeof memexSetFormBusy === "function") {
    memexSetFormBusy(
      form,
      "Saving...",
      "Saving decisions",
      "Updating source review choices."
    );
  } else {
    form.dataset.submitting = "1";
  }
  if (typeof form.requestSubmit === "function") {
    form.requestSubmit();
  } else {
    form.submit();
  }
}

document.addEventListener("click", function (event) {
  const button = event.target.closest("[data-decision-wiki][data-decision-checked]");
  if (!button) return;
  const formId = button.getAttribute("data-decision-form");
  const form = formId ? document.getElementById(formId) : button.closest("form");
  const wikiId = button.getAttribute("data-decision-wiki");
  const checked = button.getAttribute("data-decision-checked") === "true";
  document.querySelectorAll('input[type="checkbox"][name="accepted_decision"]').forEach(function (input) {
    if (formId && input.getAttribute("form") !== formId && input.form !== form) return;
    if (input.getAttribute("data-wiki-id") === wikiId) {
      input.checked = checked;
    }
  });
  if (markWikiDecisionsDirty(form, wikiId)) submitDecisionForm(form);
});

document.addEventListener("change", function (event) {
  const input = event.target.closest('input[type="checkbox"][name="accepted_decision"][data-decision-key]');
  if (!input) return;
  if (markWikiDecisionsDirty(input.form, input.getAttribute("data-wiki-id"))) {
    submitDecisionForm(input.form);
  }
});

document.addEventListener("submit", function (event) {
  const form = event.target.closest(".llm-review-inline");
  if (!form) return;
  if (form.dataset.submitting === "1") {
    event.preventDefault();
    return;
  }
  memexSetFormBusy(
    form,
    "Reviewing...",
    "Reviewing facts",
    "Checking source facts against the assigned wiki."
  );
});

document.addEventListener("submit", function (event) {
  const form = event.target.closest(".fix-form");
  if (!form) return;
  if (!memexSetFormBusy(
    form,
    "Fixing...",
    "Fixing source",
    "Applying the fix instructions to this source."
  )) {
    event.preventDefault();
  }
});
</script>
"""
