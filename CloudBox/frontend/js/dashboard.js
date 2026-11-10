(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const typeList = $("#type-list");

  function formatSize(bytes) {
    const amount = Number(bytes) || 0;
    if (amount === 0) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    const index = Math.min(Math.floor(Math.log(amount) / Math.log(1024)), units.length - 1);
    return `${(amount / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
  }

  function labelForType(value) {
    const type = String(value || "application/octet-stream");
    const labels = {
      "application/pdf": "PDF", "text/plain": "Text", "text/markdown": "Markdown",
      "text/csv": "CSV", "image/jpeg": "JPEG image", "image/png": "PNG image",
      "image/gif": "GIF image", "image/webp": "WebP image", "application/zip": "ZIP archive",
    };
    return labels[type] || type.split("/").pop().replace(/[.+_-]/g, " ").toUpperCase();
  }

  function render(data) {
    const summary = data || {};
    $("#total-files").textContent = Number(summary.total_files || 0).toLocaleString();
    $("#total-files-note").textContent = summary.total_files ? "Active files in your library" : "Ready for your first file";
    $("#total-storage").textContent = formatSize(summary.total_storage);
    $("#storage-sidebar").textContent = formatSize(summary.total_storage);
    $("#type-count").textContent = Number(summary.file_formats || 0).toLocaleString();

    const formats = Array.isArray(summary.formats) ? summary.formats : [];
    typeList.replaceChildren();
    if (!formats.length) {
      const empty = document.createElement("p");
      empty.className = "type-empty";
      empty.textContent = "File type details will appear here.";
      typeList.append(empty);
      return;
    }
    const total = formats.reduce((sum, row) => sum + Number(row.file_count || 0), 0) || 1;
    formats.forEach((row) => {
      const count = Number(row.file_count || 0);
      const item = document.createElement("div");
      item.className = "type-row";
      const icon = document.createElement("span");
      icon.className = "file-type-icon";
      icon.setAttribute("aria-hidden", "true");
      icon.textContent = labelForType(row.file_type).slice(0, 3);
      const meta = document.createElement("div");
      meta.className = "type-meta";
      const title = document.createElement("strong");
      title.append(document.createTextNode(labelForType(row.file_type)));
      const sub = document.createElement("span");
      sub.textContent = `${count} ${count === 1 ? "file" : "files"}`;
      title.append(sub);
      const bar = document.createElement("div");
      bar.className = "type-bar";
      const fill = document.createElement("span");
      fill.style.width = `${Math.max((count / total) * 100, 8)}%`;
      bar.append(fill);
      meta.append(title, bar);
      item.append(icon, meta);
      typeList.append(item);
    });
  }

  window.CloudBoxDashboard = Object.freeze({ render, formatSize });
})();
