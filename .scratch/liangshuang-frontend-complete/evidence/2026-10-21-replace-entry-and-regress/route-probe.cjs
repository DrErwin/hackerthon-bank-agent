/* Probe: ticket05 main-entry replacement routes. */
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const OUT = __dirname;
const shots = (name) => path.join(OUT, name + ".png");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({ executablePath: EDGE, headless: true, args: ["--lang=zh-CN", "--no-first-run"], defaultViewport: { width: 1280, height: 900 } });
  const page = await browser.newPage();
  const results = {};
  try {
    // 1. main entry = complete frontend
    await page.goto("http://127.0.0.1:5173/", { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForFunction(() => document.querySelector("#sh-input") && !document.querySelector("#sh-input").disabled, { timeout: 120000, polling: 300 });
    await page.waitForFunction(() => document.body.innerText.includes("已连接"), { timeout: 60000, polling: 300 });
    results.root = await page.evaluate(() => ({
      zhInput: Boolean(document.querySelector("#sh-input")),
      legacyTextbox: Boolean(document.querySelector('textarea[aria-label="输入聊天内容"], input[aria-label="输入聊天内容"]')),
      hints: document.body.innerText.includes("可以这样说"),
      billsHint: document.body.innerText.includes("这个月花了多少"),
      body: document.body.innerText.replace(/\s+/g, " ").slice(0, 400),
    }));
    await page.screenshot({ path: shots("route-root") });

    // 2. legacy rollback route = simple frontend
    await page.goto("http://127.0.0.1:5173/legacy", { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(1500);
    results.legacy = await page.evaluate(() => ({
      legacyTextbox: Boolean(document.querySelector('textarea[aria-label="输入聊天内容"], input[aria-label="输入聊天内容"]')),
      zhInput: Boolean(document.querySelector("#sh-input")),
      heading: document.body.innerText.replace(/\s+/g, " ").slice(0, 300),
    }));
    await page.screenshot({ path: shots("route-legacy") });

    // 3. /v04 still the complete frontend
    await page.goto("http://127.0.0.1:5173/v04", { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForFunction(() => document.querySelector("#sh-input") && !document.querySelector("#sh-input").disabled, { timeout: 120000, polling: 300 });
    results.v04 = await page.evaluate(() => ({ zhInput: Boolean(document.querySelector("#sh-input")) }));

    // 4. /admin still real admin page
    await page.goto("http://127.0.0.1:5173/admin", { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(1500);
    results.admin = await page.evaluate(() => ({ text: document.body.innerText.replace(/\s+/g, " ").slice(0, 300) }));
    await page.screenshot({ path: shots("route-admin") });

    // 5. /v04/gallery still works
    await page.goto("http://127.0.0.1:5173/v04/gallery", { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(1200);
    results.gallery = await page.evaluate(() => ({ text: document.body.innerText.replace(/\s+/g, " ").slice(0, 200) }));
    fs.writeFileSync(path.join(OUT, "route-probe.json"), JSON.stringify(results, null, 2), "utf8");
    console.log(JSON.stringify(results, null, 2));
  } catch (error) {
    console.error("PROBE FAILED:", error.message);
    await page.screenshot({ path: shots("route-error") }).catch(() => undefined);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
