(() => {
  "use strict";

  const MAX_FILE_SIZE = 25 * 1024 * 1024;
  const ALLOWED_TYPES = new Set("pdf png jpg jpeg gif webp txt md csv doc docx xls xlsx ppt pptx zip".split(" "));
  const files = [];
  let activeFilter = "all";
  let searchTerm = "";
  let sortMode = "newest";
  let toastTimer;

  const $ = (selector) => document.querySelector(selector);
  const els = {
    rows: $("#file-rows"), empty: $("#empty-state"), search: $("#search-input"),
    fileInput: $("#file-input"), dropzone: $("#dropzone"), toast: $("#toast"),
    typeList: $("#type-list"),
  };

  function makeId() {
    return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function addFile(file, source = "local") {
    files.unshift({
      id: makeId(), name: file.name, size: file.size, type: file.type || "application/octet-stream",
      createdAt: new Date(), blob: file, source,
    });
  }

  function seedDemoFiles() {
    const samples = [
      ["project-brief.md", "text/markdown", "# CloudBox project brief\n\nA local preview of the CloudBox file workspace.\n"],
      ["design-notes.txt", "text/plain", "CloudBox design notes\n\nKeep the first version simple, readable, and secure.\n"],
      ["sample-data.csv", "text/csv", "name,type,status\nProject brief,Markdown,Ready\nDesign notes,Text,Ready\n"],
    ];
    samples.forEach(([name, type, content], index) => {
      const blob = new Blob([content], { type });
      const createdAt = new Date(Date.now() - [45, 60 * 60 * 1000, 3 * 24 * 60 * 60 * 1000][index]);
      files.push({ id: makeId(), name, type, size: blob.size, createdAt, blob, source: "sample" });
    });
  }

  function formatSize(bytes) {
    if (!bytes) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    const unit = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / 1024 ** unit).toFixed(unit ? 1 : 0)} ${units[unit]}`;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  }

  function extension(name) { return name.split(".").pop().toLowerCase(); }

  function category(file) {
    const ext = extension(file.name);
    if (["png", "jpg", "jpeg", "gif", "webp"].includes(ext)) return "Images";
    if (["doc", "docx", "xls", "xlsx", "ppt", "pptx", "pdf"].includes(ext)) return "Documents";
    if (ext === "zip") return "Archives";
    return "Text files";
  }

  function iconClass(file) {
    const ext = extension(file.name);
    if (ext === "pdf") return "pdf";
    if (["png", "jpg", "jpeg", "gif", "webp"].includes(ext)) return "image";
    if (["doc", "docx", "xls", "xlsx", "ppt", "pptx"].includes(ext)) return "document";
    return "";
  }

  function shortType(file) {
    const ext = extension(file.name);
    return ext.length > 5 ? "FILE" : ext.toUpperCase();
  }

  function notify(message) {
    els.toast.textContent = message;
    els.toast.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => els.toast.classList.remove("is-visible"), 2800);
  }

  function visibleFiles() {
    const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
    const result = files.filter((file) => {
      const matchesSearch = file.name.toLowerCase().includes(searchTerm);
      const isRecent = file.createdAt.getTime() >= cutoff;
      return matchesSearch && (activeFilter === "all" || isRecent);
    });
    return result.sort((a, b) => {
      if (sortMode === "oldest") return a.createdAt - b.createdAt;
      if (sortMode === "name") return a.name.localeCompare(b.name);
      if (sortMode === "size") return b.size - a.size;
      return b.createdAt - a.createdAt;
    });
  }

  function renderRows() {
    const shown = visibleFiles();
    $("#visible-count").textContent = shown.length;
    $("#empty-title").textContent = searchTerm ? "No matching files" : "Your workspace is ready";
    $("#empty-copy").textContent = searchTerm ? "Try a different name or clear your search." : "Upload a file to see it here.";
    els.empty.hidden = shown.length > 0;
    els.rows.innerHTML = shown.map((file) => `
      <tr>
        <td><div class="file-name-cell"><span class="file-type-icon ${iconClass(file)}" aria-hidden="true">${shortType(file)}</span><span><strong title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</strong><small>${file.source === "sample" ? "Sample file" : "Local session file"}</small></span></div></td>
        <td>${escapeHtml(category(file))}</td>
        <td>${formatSize(file.size)}</td>
        <td><time datetime="${file.createdAt.toISOString()}">${file.createdAt.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</time></td>
        <td><div class="row-actions"><button class="icon-button" type="button" data-action="download" data-id="${file.id}" aria-label="Download ${escapeHtml(file.name)}" title="Download">↓</button><button class="icon-button delete" type="button" data-action="delete" data-id="${file.id}" aria-label="Delete ${escapeHtml(file.name)}" title="Delete">×</button></div></td>
      </tr>`).join("");
  }

  function renderSummary() {
    const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
    const groups = files.reduce((counts, file) => {
      const key = category(file);
      counts[key] = (counts[key] || 0) + 1;
      return counts;
    }, {});
    $("#total-files").textContent = files.length;
    $("#total-files-note").textContent = files.length ? "Files in this browser session" : "Ready for your first file";
    $("#total-storage").textContent = formatSize(totalBytes);
    $("#storage-sidebar").textContent = formatSize(totalBytes);
    $("#type-count").textContent = Object.keys(groups).length;
    const percent = Math.min((totalBytes / MAX_FILE_SIZE) * 100, 100);
    $("#storage-progress").style.width = `${percent}%`;
    $(".storage-track").setAttribute("aria-valuenow", Math.round(percent));
    const palette = { "Documents": "document", "Images": "image", "Text files": "", "Archives": "" };
    const total = files.length || 1;
    els.typeList.innerHTML = Object.entries(groups).length
      ? Object.entries(groups).sort((a, b) => b[1] - a[1]).map(([name, count]) => `
        <div class="type-row"><span class="file-type-icon ${palette[name]}" aria-hidden="true">${name === "Images" ? "IMG" : name === "Documents" ? "DOC" : name === "Archives" ? "ZIP" : "TXT"}</span><div class="type-meta"><strong>${name}<span>${count} ${count === 1 ? "file" : "files"}</span></strong><div class="type-bar"><span style="width:${Math.max((count / total) * 100, 8)}%"></span></div></div></div>`).join("")
      : '<p class="type-empty">File type details will appear here.</p>';
  }

  function render() { renderSummary(); renderRows(); }

  function handleFiles(fileList) {
    const selected = Array.from(fileList || []);
    if (!selected.length) return;
    let added = 0;
    selected.forEach((file) => {
      const ext = extension(file.name);
      if (!ALLOWED_TYPES.has(ext)) { notify(`${file.name}: this file type is not supported in the demo.`); return; }
      if (file.size > MAX_FILE_SIZE) { notify(`${file.name}: files must be 25 MB or smaller.`); return; }
      addFile(file);
      added += 1;
    });
    if (added) {
      activeFilter = "all";
      document.querySelectorAll(".filter-tab").forEach((button) => button.classList.toggle("is-selected", button.dataset.filter === "all"));
      render();
      notify(`${added} ${added === 1 ? "file added" : "files added"} to this browser session. Nothing was uploaded to AWS.`);
    }
    els.fileInput.value = "";
  }

  function chooseFiles() { els.fileInput.click(); }

  function setFilter(filter) {
    activeFilter = filter === "overview" ? "all" : filter;
    document.querySelectorAll(".filter-tab").forEach((button) => button.classList.toggle("is-selected", button.dataset.filter === activeFilter));
    document.querySelectorAll(".nav-link").forEach((button) => button.classList.toggle("is-active", button.dataset.view === filter));
    $("#breadcrumb-current").textContent = filter === "recent" ? "Recent" : filter === "all" ? "All files" : "Overview";
    renderRows();
  }

  document.querySelectorAll(".nav-link").forEach((button) => button.addEventListener("click", () => setFilter(button.dataset.view === "recent" ? "recent" : button.dataset.view === "all" ? "all" : "overview")));
  document.querySelectorAll(".filter-tab").forEach((button) => button.addEventListener("click", () => setFilter(button.dataset.filter)));
  $("#upload-button").addEventListener("click", chooseFiles);
  $("#choose-files").addEventListener("click", (event) => { event.stopPropagation(); chooseFiles(); });
  $("#empty-upload").addEventListener("click", chooseFiles);
  els.fileInput.addEventListener("change", (event) => handleFiles(event.target.files));
  els.search.addEventListener("input", (event) => { searchTerm = event.target.value.trim().toLowerCase(); renderRows(); });
  $("#sort-select").addEventListener("change", (event) => { sortMode = event.target.value; renderRows(); });

  els.dropzone.addEventListener("click", (event) => { if (event.target.id !== "choose-files") chooseFiles(); });
  els.dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); chooseFiles(); }
  });
  ["dragenter", "dragover"].forEach((name) => els.dropzone.addEventListener(name, (event) => { event.preventDefault(); els.dropzone.classList.add("is-dragging"); }));
  ["dragleave", "drop"].forEach((name) => els.dropzone.addEventListener(name, (event) => { event.preventDefault(); els.dropzone.classList.remove("is-dragging"); }));
  els.dropzone.addEventListener("drop", (event) => handleFiles(event.dataTransfer.files));

  els.rows.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const file = files.find((item) => item.id === button.dataset.id);
    if (!file) return;
    if (button.dataset.action === "download") {
      const url = URL.createObjectURL(file.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.name;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      notify(`Downloaded ${file.name} from the local demo.`);
    } else if (button.dataset.action === "delete" && window.confirm(`Remove “${file.name}” from this browser session?`)) {
      files.splice(files.indexOf(file), 1);
      render();
      notify(`${file.name} removed from this browser session.`);
    }
  });

  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); els.search.focus(); }
  });

  seedDemoFiles();
  render();
})();
