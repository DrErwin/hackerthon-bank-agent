/* Recovery-gate capture: pending confirmation -> session expired -> re-enter -> 查看原任务.
 * Real stack. Leaves no pending task behind (cancels the recovered task at the end).
 */
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const BASE = "http://127.0.0.1:5173/";
const OUT = path.join(__dirname, "..", "raw");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const shot = async (page, name) => {
  await page.evaluate(() => {
    const tasks = document.querySelectorAll(".sh-task");
    if (tasks.length) tasks[tasks.length - 1].scrollIntoView({ block: "center", behavior: "instant" });
  });
  await sleep(500);
  await page.screenshot({ path: path.join(OUT, name + ".png") });
  console.log("shot", name);
};
async function waitText(page, text, timeout = 240000) {
  await page.waitForFunction((t) => document.body.innerText.includes(t), { timeout, polling: 300 }, text);
}
async function waitReady(page) {
  await page.waitForFunction(() => document.querySelector("#sh-input") && !document.querySelector("#sh-input").disabled, { timeout: 120000, polling: 300 });
  await page.waitForFunction(() => document.body.innerText.includes("已连接"), { timeout: 60000, polling: 300 });
  await sleep(400);
}
async function newThread(page) {
  await page.evaluate(async () => {
    await fetch("/api/v1/threads", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ request_id: crypto.randomUUID() }) });
  });
  await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
  await waitReady(page);
}
async function clickText(page, text) {
  for (let i = 0; i < 100; i += 1) {
    const ok = await page.evaluate((t) => {
      const nodes = Array.from(document.querySelectorAll("button"));
      const el = nodes.find((n) => !n.disabled && (n.textContent || "").replace(/\s+/g, "").includes(t.replace(/\s+/g, "")));
      if (!el) return false;
      el.scrollIntoView({ block: "center", behavior: "instant" });
      el.click();
      return true;
    }, text);
    if (ok) { console.log("click", text); return; }
    await sleep(300);
  }
  throw new Error("找不到按钮: " + text);
}
(async () => {
  const browser = await puppeteer.launch({ executablePath: EDGE, headless: true, args: ["--lang=zh-CN"], defaultViewport: { width: 1280, height: 900 } });
  const page = await browser.newPage();
  page.setDefaultTimeout(300000);
  try {
    await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 60000 });
    await waitReady(page);
    await newThread(page);
    await page.click("#sh-input");
    await page.type("#sh-input", "给妈妈转500元，主账户A1", { delay: 15 });
    await page.evaluate(() => Array.from(document.querySelectorAll("button")).find((b) => b.textContent.includes("发送")).click());
    console.log("sent");
    await waitText(page, "确认办理");
    await sleep(500);
    console.log("confirmation ready");
    // newsession: clear cookies, reload -> expired banner -> re-enter
    const client = await page.createCDPSession();
    await client.send("Network.clearBrowserCookies");
    await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
    await waitText(page, "登录已过期", 60000);
    console.log("expired banner");
    await clickText(page, "点这里重新进入");
    await waitReady(page);
    await waitText(page, "有一项没办完的任务", 90000);
    await sleep(600);
    await shot(page, "t09-recovery-gate");
    await clickText(page, "查看原任务");
    await waitText(page, "已恢复原任务", 90000);
    await sleep(900);
    await shot(page, "t10-recovery-readable");
    // cleanup: cancel the recovered confirmation so no pending task blocks later runs
    try {
      await clickText(page, "取消");
      await sleep(1200);
      console.log("cleanup cancel clicked");
    } catch (error) {
      console.log("cleanup cancel skipped:", error.message);
    }
  } catch (error) {
    console.log("FLOW FAILED", error.message);
    await page.screenshot({ path: path.join(OUT, "zz-recovery2-error.png") }).catch(() => undefined);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
