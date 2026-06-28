"""Client-side behavior for dashboard source ingestion."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .dashboard_ingest_hints import DuplicateSourceHint


def render_ingest_script(
    duplicate_sources: tuple[DuplicateSourceHint, ...],
) -> str:
    index: dict[str, dict[str, str]] = {}
    for hint in duplicate_sources:
        index.setdefault(
            hint.sha256,
            {
                "source_id": hint.source_id,
                "title": hint.title,
            },
        )
    payload = json.dumps(index, ensure_ascii=True, sort_keys=True).replace(
        "<",
        "\\u003c",
    )
    return f"""
<script>
const MEMEX_DUPLICATE_SOURCES = {payload};

document.addEventListener("change", function (event) {{
  var input = event.target.closest('input[type="file"]');
  if (!input) return;
  var picker = input.closest(".file-picker");
  if (!picker) return;
  var nameEl = picker.querySelector(".file-picker-name");
  if (nameEl) nameEl.textContent = input.files[0] ? input.files[0].name : "No file chosen";
}});

async function memexSha256Bytes(bytes) {{
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map(function (byte) {{ return byte.toString(16).padStart(2, "0"); }})
    .join("");
}}

async function memexSha256ForForm(form) {{
  const fileInput = form.querySelector('input[type="file"][name="source_file"]');
  const file = fileInput && fileInput.files ? fileInput.files[0] : null;
  if (file) return memexSha256Bytes(await file.arrayBuffer());
  const textInput = form.querySelector('textarea[name="source_text"]');
  if (textInput && textInput.value && window.TextEncoder) {{
    return memexSha256Bytes(new TextEncoder().encode(textInput.value));
  }}
  return "";
}}

function memexIngestFormBusy(form) {{
  var isUpload = form.classList.contains("upload-form");
  memexSetFormBusy(
    form, "Working...",
    isUpload ? "Uploading source" : "Adding text source",
    "Extracting durable facts with the selected model."
  );
}}

function memexSubmitForm(form) {{
  form.dataset.duplicateChecked = "1";
  memexIngestFormBusy(form);
  form.submit();
}}

function memexSyncModelSpec(form) {{
  const modelSelect = document.getElementById("source-model-select");
  const modelField = form.querySelector('input[type="hidden"][name="model_spec"]');
  if (modelSelect && modelField) modelField.value = modelSelect.value;
}}

document.addEventListener("submit", async function (event) {{
  const form = event.target.closest("form.extract-form");
  if (!form) return;
  memexSyncModelSpec(form);
  if (form.dataset.submitting === "1" || form.dataset.duplicateChecking === "1") {{
    event.preventDefault();
    return;
  }}
  if (form.dataset.duplicateChecked === "1") {{
    memexIngestFormBusy(form);
    return;
  }}
  const duplicateFlag = form.querySelector('input[name="allow_duplicate"]');
  if (duplicateFlag && duplicateFlag.value === "1") {{
    memexIngestFormBusy(form);
    return;
  }}
  if (!window.crypto || !crypto.subtle) {{
    memexIngestFormBusy(form);
    return;
  }}

  event.preventDefault();
  form.dataset.duplicateChecking = "1";
  let digest = "";
  try {{
    digest = await memexSha256ForForm(form);
  }} catch (error) {{
    digest = "";
  }}
  delete form.dataset.duplicateChecking;
  if (!digest) {{
    memexSubmitForm(form);
    return;
  }}
  const duplicate = MEMEX_DUPLICATE_SOURCES[digest];
  if (!duplicate) {{
    memexSubmitForm(form);
    return;
  }}

  const dialog = document.getElementById("duplicate-upload-dialog");
  const label = dialog.querySelector("[data-duplicate-source-label]");
  const cancel = dialog.querySelector("[data-duplicate-cancel]");
  const keepDuplicate = dialog.querySelector("[data-duplicate-keep]");
  label.textContent = duplicate.title
    ? duplicate.title + " (" + duplicate.source_id + ")"
    : duplicate.source_id;
  cancel.onclick = function () {{
    if (typeof dialog.close === "function") dialog.close();
  }};
  keepDuplicate.onclick = function () {{
    if (duplicateFlag) duplicateFlag.value = "1";
    if (typeof dialog.close === "function") dialog.close();
    memexSubmitForm(form);
  }};
  if (typeof dialog.showModal === "function") {{
    dialog.showModal();
  }} else if (window.confirm("This source already exists. Keep duplicate?")) {{
    keepDuplicate.click();
  }} else {{
    cancel.click();
  }}
}});
</script>
"""
