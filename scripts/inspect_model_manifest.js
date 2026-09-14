const fs = require("fs");
const path = require("path");

const manifestPath = path.join(__dirname, "..", "outputs", "model_manifest.json");
if (!fs.existsSync(manifestPath)) {
  console.error("No outputs/model_manifest.json. Run Blender render first.");
  process.exit(1);
}
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
console.log("Mesh count:", manifest.mesh_count);
console.log("Detected groups:");
for (const [key, value] of Object.entries(manifest.detected || {})) {
  console.log(`- ${key}: ${value.length}`);
  for (const name of value.slice(0, 10)) console.log(`  ${name}`);
}
