const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const page_url = "file:///D:/hackerthon-bank-agent/.scratch/liangshuang-frontend-complete/showcase/index.html";
const OUT = path.join(__dirname, "..", "preview");
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const browser = await puppeteer.launch({ executablePath: EDGE, headless: true, args: ["--lang=zh-CN", "--allow-file-access-from-files"], defaultViewport: { width: 1600, height: 1000 } });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });
  await page.goto(page_url, { waitUntil: "load", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 1200));
  await page.screenshot({ path: path.join(OUT, "01-transfer.png") });
  // bills lens
  await page.click('.lens button[data-lens="bills"]');
  await new Promise((r) => setTimeout(r, 900));
  await page.screenshot({ path: path.join(OUT, "02-bills.png") });
  // cross lens
  await page.click('.lens button[data-lens="cross"]');
  await new Promise((r) => setTimeout(r, 900));
  await page.screenshot({ path: path.join(OUT, "03-cross.png") });
  // mobile lens
  await page.click('.lens button[data-lens="mobile"]');
  await new Promise((r) => setTimeout(r, 900));
  await page.screenshot({ path: path.join(OUT, "04-mobile.png") });
  // overview
  await page.click('.lens button[data-lens="all"]');
  await new Promise((r) => setTimeout(r, 900));
  await page.screenshot({ path: path.join(OUT, "05-all.png") });
  // open a card drawer
  await page.click('.lens button[data-lens="transfer"]');
  await new Promise((r) => setTimeout(r, 800));
  await page.evaluate(() => { const n = document.querySelector('.node[data-id="t3"]'); n.scrollIntoView(); n.click(); });
  await new Promise((r) => setTimeout(r, 700));
  await page.screenshot({ path: path.join(OUT, "06-drawer.png") });
  console.log("STATS", await page.evaluate(() => document.getElementById("statline").textContent));
  console.log("ERRORS", JSON.stringify(errors.slice(0, 10)));
  await browser.close();
})();
