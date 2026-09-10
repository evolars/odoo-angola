import { defineRailway, project, service } from "railway/iac";

// Last resort for a per-service CaC repo. Prefer one .railway file for the
// project and drop this if you later combine services into that file.
export const partial = "odoo-angola";

export default defineRailway(() => {
  const odoo_angola = service("odoo-angola", {
    healthcheck: "/web/login",
    healthcheckTimeout: 300,
    preDeploy: "/usr/local/bin/initialize-odoo-base",
    // dockerfilePath from CaC: "Dockerfile"
    // builder from CaC: "DOCKERFILE"
  });
  return project("odoo-angola", {
    resources: [odoo_angola],
  });
});
