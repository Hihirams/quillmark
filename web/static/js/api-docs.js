/* Quillmark's first-party shell retains FastAPI's standard Swagger explorer. */
(function () {
  "use strict";
  var host = document.getElementById("swagger-ui");
  var bundle = window.SwaggerUIBundle;
  if (!host || typeof bundle !== "function") return;
  bundle({
    url: host.dataset.openapiUrl,
    dom_id: "#swagger-ui",
    layout: "BaseLayout",
    deepLinking: true,
    showExtensions: true,
    showCommonExtensions: true,
    oauth2RedirectUrl: window.location.origin + host.dataset.oauthRedirect,
    presets: [bundle.presets.apis, bundle.SwaggerUIStandalonePreset],
    onComplete: function () {
      document.getElementById("swagger-fallback").hidden = true;
    }
  });
})();
