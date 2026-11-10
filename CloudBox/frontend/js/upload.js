(() => {
  "use strict";

  const MAX_FILE_SIZE = 25 * 1024 * 1024;
  const ALLOWED_TYPES = new Set("pdf png jpg jpeg gif webp txt md csv doc docx xls xlsx ppt pptx zip".split(" "));
  const input = document.querySelector("#file-input");
  const dropzone = document.querySelector("#dropzone");
  const progress = document.querySelector("#upload-progress");
  const status = document.querySelector("#upload-status");
  let notify = () => {};
  let onUploaded = async () => {};
  let busy = false;

  function validate(file) {
    const extension = file.name.includes(".") ? file.name.split(".").pop().toLowerCase() : "";
    if (!ALLOWED_TYPES.has(extension)) return "This file type is not supported.";
    if (file.size > MAX_FILE_SIZE) return "Files must be 25 MB or smaller.";
    return "";
  }
  async function uploadOne(file) {
    const issue = validate(file);
    if (issue) { notify(`${file.name}: ${issue}`); return; }
    progress.hidden = false;
    progress.value = 0;
    status.textContent = `Preparing ${file.name}…`;
    try {
      await window.CloudBoxApi.uploadFile(file, (value) => {
        progress.value = value;
        status.textContent = `Uploading ${file.name}: ${value}%`;
      });
      progress.value = 100;
      status.textContent = `${file.name} uploaded successfully.`;
      notify(`${file.name} uploaded.`);
      await onUploaded();
    } catch (error) {
      status.textContent = `Upload failed: ${file.name}`;
      notify(`${file.name}: ${error.message}`);
    } finally {
      window.setTimeout(() => { progress.hidden = true; progress.value = 0; }, 1200);
    }
  }
  async function handle(files) {
    if (busy) return;
    const selected = Array.from(files || []);
    if (!selected.length) return;
    busy = true;
    document.querySelectorAll("#upload-button, #choose-files, #empty-upload").forEach((button) => { button.disabled = true; });
    try {
      for (const file of selected) await uploadOne(file);
    } finally {
      busy = false;
      document.querySelectorAll("#upload-button, #choose-files, #empty-upload").forEach((button) => { button.disabled = false; });
      input.value = "";
    }
  }
  function setup(options = {}) {
    notify = options.notify || notify;
    onUploaded = options.onUploaded || onUploaded;
    const choose = () => input.click();
    document.querySelector("#upload-button").addEventListener("click", choose);
    document.querySelector("#choose-files").addEventListener("click", (event) => { event.stopPropagation(); choose(); });
    document.querySelector("#empty-upload").addEventListener("click", choose);
    input.addEventListener("change", (event) => handle(event.target.files));
    ["dragenter", "dragover"].forEach((name) => dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.add("is-dragging");
    }));
    ["dragleave", "drop"].forEach((name) => dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-dragging");
    }));
    dropzone.addEventListener("drop", (event) => handle(event.dataTransfer.files));
  }
  window.CloudBoxUpload = Object.freeze({ setup });
})();
