/*
 * Local defaults. The deployment script replaces this file with the selected
 * Flask and API Gateway URLs. Never put credentials or access tokens here.
 */
window.CLOUDBOX_CONFIG = Object.freeze({
  flaskApiBaseUrl: "http://127.0.0.1:5000",
  fileApiBaseUrl: "",
  authRequired: false,
});
