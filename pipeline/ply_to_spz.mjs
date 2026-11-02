// Converts a cleaned .ply to the compact .spz format with Spark's own encoder (runs in a headless browser).
// Usage: node pipeline/ply_to_spz.mjs viewer/assets/scene.ply viewer/assets/scene.spz
// Needs Playwright with a browser:  npm i playwright && npx playwright install chromium
import { createRequire } from "node:module";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";

function loadPlaywright() {
  for (const base of ["package.json", "video/package.json"]) {
    try { return createRequire(path.resolve(base))("playwright"); } catch { /* try next */ }
  }
  throw new Error("playwright not found: run  npm i playwright  first");
}
const { chromium } = loadPlaywright();
const [src, dst] = process.argv.slice(2);
const root = path.resolve("viewer");

const server = http.createServer((req, res) => {
  const f = path.join(root, decodeURIComponent(req.url.split("?")[0]));
  if (req.url === "/" || !fs.existsSync(f)) { res.writeHead(200, { "Content-Type": "text/html" }); res.end('<html><head><script type="importmap">{"imports":{"three":"/vendor/three.module.js","three/addons/postprocessing/Pass.js":"/vendor/Pass.js"}}</script></head><body>spz</body></html>'); return; }
  const type = f.endsWith(".js") ? "text/javascript" : "application/octet-stream";
  res.writeHead(200, { "Content-Type": type });
  fs.createReadStream(f).pipe(res);
}).listen(8123);

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto("http://localhost:8123/");
const bytes = fs.readFileSync(src);
const b64 = await page.evaluate(async ({ plyUrl }) => {
  const { transcodeSpz } = await import("/vendor/spark.module.js").catch(async () => {
    throw new Error("import failed");
  });
  const buf = new Uint8Array(await (await fetch(plyUrl)).arrayBuffer());
  const out = await transcodeSpz({ inputs: [{ fileBytes: buf }], maxSh: 0 });
  const u8 = out.fileBytes;
  let s = "";
  const CH = 0x8000;
  for (let i = 0; i < u8.length; i += CH) s += String.fromCharCode.apply(null, u8.subarray(i, i + CH));
  return btoa(s);
}, { plyUrl: "/" + path.relative(root, path.resolve(src)).replace(/\\/g, "/") });
fs.writeFileSync(dst, Buffer.from(b64, "base64"));
console.log(`${src} ${(bytes.length / 1e6).toFixed(1)} MB -> ${dst} ${(fs.statSync(dst).size / 1e6).toFixed(1)} MB`);
await browser.close();
server.close();
