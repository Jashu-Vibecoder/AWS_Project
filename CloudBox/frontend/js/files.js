(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const rows = $("#file-rows");
  const empty = $("#empty-state");
  const count = $("#visible-count");
  const state = { files: [], search: "", filter: "all", sort: "newest", busy: false };
  let notify = () => {};
  let onChanged = async () => {};

  function extension(name) { return String(name || "").split(".").pop().toLowerCase(); }
  function category(file) {
    const ext = extension(file.file_name);
    if (["png", "jpg", "jpeg", "gif", "webp"].includes(ext)) return "Images";
    if (["doc", "docx", "xls", "xlsx", "ppt", "pptx", "pdf"].includes(ext)) return "Documents";
    if (ext === "zip") return "Archives";
    return "Text files";
  }
  function icon(file) {
    const ext = extension(file.file_name);
    if (["png", "jpg", "jpeg", "gif", "webp"].includes(ext)) return "IMG";
    if (["doc", "docx", "xls", "xlsx", "ppt", "pptx"].includes(ext)) return "DOC";
    if (ext === "pdf") return "PDF";
    return ext.length > 5 ? "FILE" : ext.toUpperCase();
  }
  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  }
  function visibleFiles() {
    const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
    return state.files.filter((file) => state.filter === "all" || new Date(file.uploaded_at).getTime() >= cutoff)
      .slice().sort((a, b) => {
        if (state.sort === "oldest") return new Date(a.uploaded_at) - new Date(b.uploaded_at);
        if (state.sort === "name") return String(a.file_name).localeCompare(String(b.file_name));
        if (state.sort === "size") return Number(b.file_size) - Number(a.file_size);
        return new Date(b.uploaded_at) - new Date(a.uploaded_at);
      });
  }
  function render() {
    const files = visibleFiles();
    count.textContent = String(files.length);
    $("#empty-title").textContent = state.search ? "No matching files" : state.filter === "recent" ? "No recent files" : "Your workspace is ready";
    $("#empty-copy").textContent = state.search ? "Try a different name or clear your search." : "Upload a file to see it here.";
    empty.hidden = files.length > 0;
    rows.innerHTML = files.map((file) => {
      const date = new Date(file.uploaded_at);
      const validDate = !Number.isNaN(date.getTime());
      const dateText = validDate ? date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "—";
      const dateValue = validDate ? date.toISOString() : "";
      const name = escapeHtml(file.file_name || "Untitled file");
      return `<tr>
        <td><div class="file-name-cell"><span class="file-type-icon" aria-hidden="true">${escapeHtml(icon(file))}</span><span><strong title="${name}">${name}</strong><small>Private CloudBox storage</small></span></div></td>
        <td>${escapeHtml(category(file))}</td>
        <td>${window.CloudBoxDashboard.formatSize(file.file_size)}</td>
        <td><time datetime="${dateValue}">${dateText}</time></td>
        <td><div class="row-actions"><button class="icon-button" type="button" data-action="download" data-id="${encodeURIComponent(file.id)}" aria-label="Download ${name}">Download</button><button class="icon-button delete" type="button" data-action="delete" data-id="${encodeURIComponent(file.id)}" aria-label="Delete ${name}">Delete</button></div></td>
      </tr>`;
    }).join("");
  }
  async function refresh(search = state.search) {
    state.search = search;
    const data = await window.CloudBoxApi.listFiles(search);
    state.files = Array.isArray(data.files) ? data.files : [];
    render();
    return data;
  }
  function setup(options = {}) {
    notify = options.notify || notify;
    onChanged = options.onChanged || onChanged;
    $("#search-input").addEventListener("input", (event) => {
      window.clearTimeout(setup.searchTimer);
      setup.searchTimer = window.setTimeout(() => refresh(event.target.value.trim()).catch((error) => notify(error.message)), 250);
    });
    $("#sort-select").addEventListener("change", (event) => { state.sort = event.target.value; render(); });
    document.querySelectorAll(".filter-tab").forEach((button) => button.addEventListener("click", () => {
      state.filter = button.dataset.filter === "recent" ? "recent" : "all";
      document.querySelectorAll(".filter-tab").forEach((item) => item.classList.toggle("is-selected", item === button));
      render();
    }));
    document.querySelectorAll(".nav-link").forEach((button) => button.addEventListener("click", () => {
      const view = button.dataset.view;
      state.filter = view === "recent" ? "recent" : "all";
      document.querySelectorAll(".nav-link").forEach((item) => item.classList.toggle("is-active", item === button));
      document.querySelectorAll(".filter-tab").forEach((item) => item.classList.toggle("is-selected", item.dataset.filter === state.filter));
      $("#breadcrumb-current").textContent = view === "recent" ? "Recent" : view === "all" ? "All files" : "Overview";
      render();
    }));
    rows.addEventListener("click", async (event) => {
      const button = event.target.closest("button[data-action]");
      if (!button || state.busy) return;
      const id = decodeURIComponent(button.dataset.id || "");
      const file = state.files.find((item) => String(item.id) === id);
      if (!file) return;
      state.busy = true;
      try {
        if (button.dataset.action === "delete") {
          if (!window.confirm(`Permanently delete ${file.file_name}?`)) return;
          await window.CloudBoxApi.deleteFile(id);
          notify(`${file.file_name} was deleted.`);
          await onChanged();
        } else if (button.dataset.action === "download") {
          const result = await window.CloudBoxApi.getDownloadUrl(id);
          if (!result.download_url) throw new Error("The service did not return a download link.");
          window.location.assign(result.download_url);
        }
      } catch (error) { notify(error.message); }
      finally { state.busy = false; }
    });
    return { refresh };
  }

  window.CloudBoxFiles = Object.freeze({ setup });
})();
