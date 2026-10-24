const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const URL = "file:///D:/hackerthon-bank-agent/.scratch/liangshuang-frontend-complete/showcase/index.html";
const OUT = path.join(__dirname, "..", "preview");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const browser = await puppeteer.launch({ executablePath: EDGE, headless: true, args: ["--lang=zh-CN", "--allow-file-access-from-files"], defaultViewport: { width: 1600, height: 1000 } });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });
  await page.goto(URL, { waitUntil: "load", timeout: 60000 });
  await sleep(900);
  await page.screenshot({ path: path.join(OUT, "10-transfer-zoom.png") });

  // note node drawer
  await page.click('.lens button[data-lens="cross"]');
  await sleep(800);
  await page.evaluate(() => document.querySelector('.node[data-id="x5"]').click());
  await sleep(600);
  await page.screenshot({ path: path.join(OUT, "11-drawer-note.png") });
  await page.keyboard.press("Escape");
  await sleep(400);
  // double image drawer
  await page.evaluate(() => document.querySelector('.node[data-id="x6"]').click());
  await sleep(600);
  await page.screenshot({ path: path.join(OUT, "12-drawer-double.png") });
  // lightbox
  await page.evaluate(() => document.querySelector("#drawer-body img").click());
  await sleep(500);
  await page.screenshot({ path: path.join(OUT, "13-lightbox.png") });
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await sleep(400);
  // bills anomaly drawer
  await page.click('.lens button[data-lens="bills"]');
  await sleep(700);
  await page.evaluate(() => document.querySelector('.node[data-id="a4"]').click());
  await sleep(600);
  await page.screenshot({ path: path.join(OUT, "14-drawer-bills.png") });
  await page.keyboard.press("Escape");
  // zoom buttons
  const before = await page.$eval("#zoom-pct", (el) => el.textContent);
  await page.click("#zoom-in");
  await sleep(300);
  const after = await page.$eval("#zoom-pct", (el) => el.textContent);
  // wheel pan
  const viewBefore = await page.evaluate(() => document.getElementById("world").style.transform);
  await page.mouse.move(800, 600);
  await page.mouse.wheel({ deltaY: 300 });
  await sleep(300);
  const viewAfter = await page.evaluate(() => document.getElementById("world").style.transform);
  console.log("ZOOM", before, "->", after);
  console.log("WHEEL", viewBefore, "->", viewAfter);
  console.log("ERRORS", JSON.stringify(errors));
  await browser.close();
})();
