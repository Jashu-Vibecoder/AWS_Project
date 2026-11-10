(() => {
  "use strict";

  const config = window.CLOUDBOX_CONFIG || {};
  const TOKEN_KEY = "cloudboxAccessToken";

  class ApiError extends Error {
    constructor(message, status = 0, code = "request_failed") {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.code = code;
    }
  }

  function token() {
    try { return window.sessionStorage.getItem(TOKEN_KEY) || ""; }
    catch (_error) { return ""; }
  }

  async function request(baseUrl, path, options = {}) {
    if (!baseUrl) throw new ApiError("This CloudBox service is not configured yet.", 0, "not_configured");
    const headers = new Headers(options.headers || {});
    if (options.body !== undefined && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const accessToken = token();
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

    let response;
    try {
      response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
        ...options,
        headers,
        mode: "cors",
        credentials: "omit",
      });
    } catch (_error) {
      throw new ApiError("CloudBox could not reach the service. Check your connection and try again.", 0, "network_error");
    }

    let payload = {};
    try { payload = await response.json(); }
    catch (_error) {
      if (response.ok) return {};
    }

    if (response.status === 401 && config.authRequired) {
      try { window.sessionStorage.removeItem(TOKEN_KEY); } catch (_error) { /* Storage can be disabled. */ }
      window.location.replace("login.html?expired=1");
    }
    if (!response.ok || payload.success === false) {
      throw new ApiError(payload.message || "The request could not be completed.", response.status, payload.error?.code || "request_failed");
    }
    return payload.data ?? payload;
  }

  function flask(path, options) { return request(config.flaskApiBaseUrl || "", path, options); }
  function fileApi(path, options) { return request(config.fileApiBaseUrl || "", path, options); }

  function putSignedUrl(url, file, contentType, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", url, true);
      xhr.setRequestHeader("Content-Type", contentType);
      xhr.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable && onProgress) onProgress(Math.round((event.loaded / event.total) * 100));
      });
      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve();
        else reject(new ApiError("S3 rejected the upload. Check the bucket CORS and signed request settings.", xhr.status, "s3_upload_failed"));
      });
      xhr.addEventListener("error", () => reject(new ApiError("The upload connection was interrupted.", 0, "upload_network_error")));
      xhr.addEventListener("abort", () => reject(new ApiError("The upload was cancelled.", 0, "upload_cancelled")));
      xhr.send(file);
    });
  }

  async function uploadFile(file, onProgress) {
    const requested = await fileApi("/upload-url", {
      method: "POST",
      body: JSON.stringify({ file_name: file.name, file_type: file.type || "application/octet-stream", file_size: file.size }),
    });
    await putSignedUrl(requested.upload_url, file, requested.file_type, onProgress);
    return fileApi("/upload-confirm", {
      method: "POST",
      body: JSON.stringify({
        s3_key: requested.s3_key,
        file_name: requested.file_name,
        file_type: requested.file_type,
        file_size: requested.file_size,
      }),
    });
  }

  window.CloudBoxApi = Object.freeze({
    ApiError,
    getDashboard: () => flask("/api/dashboard"),
    listFiles: (search = "") => flask(`/api/files?limit=100&offset=0${search ? `&q=${encodeURIComponent(search)}` : ""}`),
    uploadFile,
    getDownloadUrl: (id) => fileApi(`/download-url/${encodeURIComponent(id)}`),
    deleteFile: (id) => fileApi(`/files/${encodeURIComponent(id)}`, { method: "DELETE" }),
    hasToken: () => Boolean(token()),
    tokenKey: TOKEN_KEY,
  });
})();
