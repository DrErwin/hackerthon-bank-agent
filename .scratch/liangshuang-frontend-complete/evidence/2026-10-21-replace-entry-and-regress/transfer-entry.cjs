/* Ticket 05 regression: transfer on the new main entry "/" (1280x900).
 * Low-risk 500 flow: confirmation gate -> code verification -> bank result -> refresh read-only.
 * Extra: double click on the confirmation button must submit once.
 */
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const BASE = process.env.ENTRY_BASE || "http://127.0.0.1:5173/";
const OUT = process.env.ENTRY_OUT || path.join(__dirname, "run");
fs.mkdirSync(OUT, { recursive: true });
const shot = (name) => path.join(OUT, name + ".png");

const steps = [];
const apiCalls = [];
const consoleErrors = [];
let no = 0;
const record = (name, data = {}) => {
  no += 1;
  steps.push({ n: no, name, at: new Date().toISOString(), ...data });
  console.log(`[${no}] ${name} ${JSON.stringify(data).slice(0, 400)}`);
};
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function clickButton(page, text, timeout = 30000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const state = await page.evaluate((t) => {
      const nodes = Array.from(document.querySelectorAll("button"));
      const el = nodes.find((node) => (node.textContent || "").replace(/\s+/g, "").includes(t.replace(/\s+/g, "")));
      if (!el) return "missing";
      if (el.disabled) return "disabled";
      el.scrollIntoView({ block: "center" });
      el.click();
      return "clicked";
    }, text);
    if (state === "clicked") return;
    await sleep(250);
  }
  throw new Error("找不到可点击按钮: " + text);
}

async function waitTaskText(page, taskId, text, timeout = 240000) {
  await page.waitForFunction((id, t) => {
    const node = Array.from(document.querySelectorAll(".sh-task")).find((el) => el.getAttribute("data-task-id") === id);
    return Boolean(node && node.innerText.includes(t));
  }, { timeout, polling: 300 }, taskId, text);
}

async function taskIds(page) {
  return page.evaluate(() => Array.from(document.querySelectorAll(".sh-task")).map((node) => node.getAttribute("data-task-id")));
}

async function taskBlock(page, taskId) {
  return page.evaluate((id) => {
    const node = Array.from(document.querySelectorAll(".sh-task")).find((el) => el.getAttribute("data-task-id") === id);
    if (!node) return null;
    return {
      text: node.innerText.trim().replace(/\s+/g, " "),
      buttons: Array.from(node.querySelectorAll("button")).map((button) => ({ text: button.textContent.trim(), disabled: button.disabled })),
      readOnlyLines: Array.from(node.querySelectorAll(".sh-readonly-line")).map((n) => n.textContent.trim()),
      placeholders: Array.from(node.querySelectorAll(".sh-hint")).map((n) => n.textContent.trim()).filter((t) => t.includes("正在读取")),
    };
  }, taskId);
}

async function newThread(page) {
  const created = await page.evaluate(async () => {
    const response = await fetch("/api/v1/threads", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ request_id: crypto.randomUUID() }) });
    return (await response.json()).data.thread_id;
  });
  await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
  await waitReady(page, "new-thread");
  return created;
}

async function waitReady(page, label) {
  await page.waitForFunction(() => document.querySelector("#sh-input") && !document.querySelector("#sh-input").disabled, { timeout: 120000, polling: 300 });
  await page.waitForFunction(() => document.body.innerText.includes("已连接"), { timeout: 60000, polling: 300 });
  record("ready", { label });
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: true,
    args: ["--lang=zh-CN", "--no-first-run", "--window-size=1280,900"],
    defaultViewport: { width: 1280, height: 900 },
  });
  const page = await browser.newPage();
  page.setDefaultTimeout(300000);
  page.on("response", (response) => {
    const url = response.url();
    if (url.includes("/api/v1/")) apiCalls.push({ method: response.request().method(), url: url.replace("http://127.0.0.1:5173", ""), status: response.status() });
  });
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => consoleErrors.push("pageerror: " + error.message));
  try {
    await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 60000 });
    await waitReady(page, "entry boot");
    const entry = await page.evaluate(() => ({
      path: window.location.pathname,
      zhInput: Boolean(document.querySelector("#sh-input")),
      legacyTextbox: Boolean(document.querySelector('textarea[aria-label="输入聊天内容"]')),
      demoRibbon: Boolean(document.querySelector(".sh-ribbon")),
    }));
    record("entry", entry);
    if (entry.path !== "/" || !entry.zhInput) throw new Error("主入口不是完整前端");
    await page.screenshot({ path: shot("00-entry") });

    const threadId = await newThread(page);
    const known = new Set(await taskIds(page));
    await page.click("#sh-input");
    await page.type("#sh-input", "给妈妈转500元，主账户A1", { delay: 20 });
    await page.evaluate(() => Array.from(document.querySelectorAll("button")).find((b) => b.textContent.includes("发送")).click());
    record("send", { threadId });

    await page.waitForFunction(() => document.body.innerText.includes("确认办理"), { timeout: 240000, polling: 300 });
    const ids = await taskIds(page);
    const taskId = ids.find((id) => !known.has(id));
    if (!taskId) throw new Error("没有识别到本次新建的任务块");
    await waitTaskText(page, taskId, "确认办理", 60000);
    const confirmation = await taskBlock(page, taskId);
    record("confirmation", { taskId, text: confirmation.text.slice(0, 700), buttons: confirmation.buttons.map((b) => b.text) });
    await page.screenshot({ path: shot("01-confirmation") });

    // double click the confirmation button; the second click must not submit again
    const answerPostsBefore = apiCalls.filter((c) => c.method === "POST" && c.url.includes("/answer")).length;
    await page.evaluate((id) => {
      const node = Array.from(document.querySelectorAll(".sh-task")).find((el) => el.getAttribute("data-task-id") === id);
      const button = Array.from(node.querySelectorAll("button")).find((b) => b.textContent.includes("确认办理"));
      button.click();
      button.click();
    }, taskId);
    record("confirm-double-click", {});
    await waitTaskText(page, taskId, "等您验证", 180000);
    await sleep(1500);
    const answerPostsAfter = apiCalls.filter((c) => c.method === "POST" && c.url.includes("/answer")).length;
    const idsAfter = await taskIds(page);
    const verification = await taskBlock(page, taskId);
    record("verification", {
      text: verification.text.slice(0, 700),
      buttons: verification.buttons.map((b) => b.text),
      answerCount: answerPostsAfter - answerPostsBefore,
      taskCount: idsAfter.length,
    });
    await page.screenshot({ path: shot("02-verification") });

    await page.evaluate((id) => {
      const node = Array.from(document.querySelectorAll(".sh-task")).find((el) => el.getAttribute("data-task-id") === id);
      const button = Array.from(node.querySelectorAll("button")).find((b) => b.textContent.includes("点这里查看"));
      button.click();
    }, taskId);
    await page.waitForFunction(() => {
      const strong = document.querySelector(".sh-task .sh-demo-code strong");
      return Boolean(strong && /^\d{6}$/.test(strong.textContent.trim()));
    }, { timeout: 60000, polling: 300 });
    const demoCode = await page.evaluate(() => document.querySelector(".sh-task .sh-demo-code strong").textContent.trim());
    record("demo-code", { code: demoCode });
    await page.evaluate((id) => {
      const node = Array.from(document.querySelectorAll(".sh-task")).find((el) => el.getAttribute("data-task-id") === id);
      const input = node.querySelector("input.sh-code-input");
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      setter.call(input, "");
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.focus();
    }, taskId);
    await page.type(".sh-task input.sh-code-input", demoCode, { delay: 30 });
    await page.screenshot({ path: shot("03-code-entered") });
    await page.evaluate((id) => {
      const node = Array.from(document.querySelectorAll(".sh-task")).find((el) => el.getAttribute("data-task-id") === id);
      const button = Array.from(node.querySelectorAll("button")).find((b) => b.textContent.includes("提交验证码"));
      if (!button || button.disabled) throw new Error("提交验证码按钮不可用");
      button.click();
    }, taskId);
    record("code-submitted", {});
    await waitTaskText(page, taskId, "转账成功", 240000);
    const result = await taskBlock(page, taskId);
    const txMatch = result.text.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i);
    record("result", { taskId, text: result.text.slice(0, 700), transactionId: txMatch ? txMatch[1] : null });
    await page.screenshot({ path: shot("04-result") });

    // refresh on the new entry: read-only restore, no live confirm buttons, no recovery gate
    await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
    await waitReady(page, "reload");
    await waitTaskText(page, taskId, "转账成功", 120000);
    await waitTaskText(page, taskId, "已确认办理", 60000);
    const reloaded = await taskBlock(page, taskId);
    const liveButtons = reloaded.buttons.filter((button) => !button.disabled);
    record("reload-recovery", {
      text: reloaded.text.slice(0, 900),
      taskBlockButtons: reloaded.buttons.map((b) => b.text),
      readOnlyLines: reloaded.readOnlyLines,
      hasRecoveryGate: reloaded.text.includes("有一项没办完的任务"),
      placeholders: reloaded.placeholders,
      liveButtonCount: liveButtons.length,
    });
    await page.screenshot({ path: shot("05-reload-readonly") });

    const expected401 = apiCalls.filter((call) => call.status === 401 && call.url === "/api/v1/session");
    const failures = apiCalls.filter((call) => call.status >= 400 && !(call.status === 401 && call.url === "/api/v1/session") && call.status !== 409);
    const checks = {
      entryIsCompleteFrontend: entry.path === "/" && entry.zhInput && !entry.legacyTextbox,
      realApiNoDemoRibbon: !entry.demoRibbon,
      modelProducedPlan: Boolean(confirmation.text && confirmation.text.includes("确认办理") && confirmation.text.length > 50),
      doubleClickSingleSubmit: answerPostsAfter - answerPostsBefore === 1 && idsAfter.length === ids.length,
      codeVerificationPassed: Boolean(txMatch),
      refreshRestoredReadOnly: reloaded.readOnlyLines.length > 0 && reloaded.placeholders.length === 0 && !reloaded.text.includes("有一项没办完的任务"),
      refreshNoLiveButtons: liveButtons.length === 0,
      noUnexpectedApiFailures: failures.length === 0,
    };
    const verdict = Object.values(checks).every(Boolean) ? "PASS" : "FAIL";
    const evidence = {
      capturedAt: new Date().toISOString(),
      base: BASE,
      threadId,
      taskId,
      transactionId: txMatch ? txMatch[1] : null,
      checks,
      verdict,
      steps,
      apiCalls,
      consoleErrors,
      expected401: expected401.map((call) => call.url),
      unexpectedApiFailures: failures,
    };
    fs.writeFileSync(path.join(OUT, "transfer-entry.json"), JSON.stringify(evidence, null, 2), "utf8");
    console.log("CHECKS=" + JSON.stringify(checks));
    console.log("VERDICT=" + verdict);
    process.exitCode = verdict === "PASS" ? 0 : 2;
  } catch (error) {
    record("error", { message: error.message });
    fs.writeFileSync(path.join(OUT, "transfer-entry.json"), JSON.stringify({ capturedAt: new Date().toISOString(), base: BASE, steps, apiCalls, consoleErrors, verdict: "ERROR", error: error.message }, null, 2), "utf8");
    await page.screenshot({ path: shot("99-error") }).catch(() => undefined);
    console.error("WALKTHROUGH FAILED: " + error.message);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
