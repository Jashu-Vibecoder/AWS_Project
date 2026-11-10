(() => {
  "use strict";

  const config = window.CLOUDBOX_CONFIG || {};
  const toast = document.querySelector("#toast");
  const connection = document.querySelector("#connection-status");
  let toastTimer;

  function notify(message) {
    toast.textContent = message;
    toast.classList.add("is-visible");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 3500);
  }
  function setConnection(text, connected) {
    connection.lastChild.textContent = text;
    connection.classList.toggle("is-connected", connected);
    connection.classList.toggle("is-error", !connected);
  }
  async function refreshAll() {
    const results = await Promise.allSettled([
      window.CloudBoxApi.getDashboard(),
      window.CloudBoxFilesInstance.refresh(),
    ]);
    const dashboard = results[0];
    const fileList = results[1];
    if (dashboard.status === "fulfilled") window.CloudBoxDashboard.render(dashboard.value);
    if (fileList.status === "rejected") throw fileList.reason;
    if (dashboard.status === "rejected") throw dashboard.reason;
  }

  if (config.authRequired && !window.CloudBoxApi.hasToken()) {
    window.location.replace("login.html");
    return;
  }
  window.CloudBoxFilesInstance = window.CloudBoxFiles.setup({ notify, onChanged: refreshAll });
  window.CloudBoxUpload.setup({ notify, onUploaded: refreshAll });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      document.querySelector("#search-input").focus();
    }
  });

  refreshAll().then(() => setConnection("Connected", true)).catch((error) => {
    setConnection("Connection issue", false);
    notify(error.message);
  });
})();
