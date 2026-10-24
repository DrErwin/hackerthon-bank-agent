/* Capture step-by-step screenshots of the real-API v0.4 frontend for the E2E showcase board.
 * Stack: real local-demo backend (GLM Coding Plan glm-5.3 + mock bank) on 8000, Vite dev 5173 real-api.
 * Usage: node capture.cjs [outDir]
 */
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const BASE = process.env.CAPTURE_BASE || "http://127.0.0.1:5173/";
const OUT = process.argv[2] || path.join(__dirname, "..", "raw");
fs.mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let n = 0;
const log = (name, data = {}) => {
  n += 1;
  console.log(`[${String(n).padStart(2, "0")}] ${name} ${JSON.stringify(data).slice(0, 300)}`);
};

async function waitReady(page) {
  await page.waitForFunction(
    () => document.querySelector("#sh-input") && !document.querySelector("#sh-input").disabled,
    { timeout: 120000, polling: 300 },
  );
  await page.waitForFunction(() => document.body.innerText.includes("已连接"), { timeout: 60000, polling: 300 });
  await sleep(300);
}

async function newThread(page) {
  const id = await page.evaluate(async () => {
    const res = await fetch("/api/v1/threads", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ request_id: crypto.randomUUID() }),
    });
    return (await res.json()).data.thread_id;
  });
  await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
  await waitReady(page);
  await sleep(500);
  return id;
}

async function send(page, text) {
  await page.click("#sh-input");
  await page.type("#sh-input", text, { delay: 15 });
  await page.evaluate(() => {
    const button = Array.from(document.querySelectorAll("button")).find((b) => b.textContent.includes("发送"));
    button.click();
  });
  log("send", { text });
}

async function scrollLastTask(page) {
  await page.evaluate(() => {
    const tasks = document.querySelectorAll(".sh-task");
    const last = tasks[tasks.length - 1];
    if (last) last.scrollIntoView({ block: "center", behavior: "instant" });
  });
  await sleep(450);
}

async function shot(page, name, fullPage = false) {
  await scrollLastTask(page);
  await page.screenshot({ path: path.join(OUT, name + ".png"), fullPage });
  log("shot", { name });
}

async function waitText(page, text, timeout = 240000) {
  await page.waitForFunction((t) => document.body.innerText.includes(t), { timeout, polling: 300 }, text);
}

async function clickInTask(page, text, timeout = 30000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const state = await page.evaluate((t) => {
      const tasks = document.querySelectorAll(".sh-task");
      const node = tasks[tasks.length - 1];
      if (!node) return "no-task";
      const button = Array.from(node.querySelectorAll("button")).find(
        (b) => !b.disabled && (b.textContent || "").replace(/\s+/g, "").includes(t.replace(/\s+/g, "")),
      );
      if (!button) return "missing";
      button.scrollIntoView({ block: "center", behavior: "instant" });
      button.click();
      return "clicked";
    }, text);
    if (state === "clicked") {
      log("click", { text });
      return;
    }
    await sleep(300);
  }
  throw new Error("无法点击任务按钮: " + text);
}

async function choiceLabels(page) {
  return page.evaluate(() => {
    const tasks = document.querySelectorAll(".sh-task");
    const node = tasks[tasks.length - 1];
    if (!node) return [];
    return Array.from(node.querySelectorAll(".sh-choice:not([disabled])")).map((b) => b.textContent.trim());
  });
}

async function clickChoice(page, preferences) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const labels = await choiceLabels(page);
    if (labels.length > 0) {
      let target = null;
      for (const pref of preferences) {
        const hit = labels.find((label) => label.includes(pref));
        if (hit) {
          target = hit;
          break;
        }
      }
      if (!target) target = labels[0];
      await page.evaluate((label) => {
        const tasks = document.querySelectorAll(".sh-task");
        const node = tasks[tasks.length - 1];
        const button = Array.from(node.querySelectorAll(".sh-choice")).find((b) => b.textContent.trim() === label);
        button.scrollIntoView({ block: "center", behavior: "instant" });
        button.click();
      }, target);
      log("choice", { target });
      await sleep(1400);
      return target;
    }
    await sleep(800);
  }
  throw new Error("等待选项超时");
}

async function waitChoice(page, timeout = 240000) {
  await page.waitForFunction(() => {
    const tasks = document.querySelectorAll(".sh-task");
    const node = tasks[tasks.length - 1];
    return Boolean(node && node.querySelector(".sh-choice:not([disabled])"));
  }, { timeout, polling: 300 });
  await sleep(400);
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
  page.on("console", (m) => { if (m.type() === "error") console.log("CONSOLE-ERROR:", m.text()); });
  page.on("pageerror", (e) => console.log("PAGE-ERROR:", e.message));
  const results = [];
  try {
    // ---------- 0. welcome / entry ----------
    await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 60000 });
    await waitReady(page);
    await newThread(page);
    await shot(page, "t01-welcome");
    results.push({ flow: "entry", ok: true });

    // ---------- 1. transfer happy path until confirmation, then cancel ----------
    await newThread(page);
    await send(page, "给妈妈转500元，主账户A1");
    await waitText(page, "确认办理");
    await sleep(600);
    await shot(page, "t02-confirmation");
    await clickInTask(page, "取消");
    await waitText(page, "已取消");
    await sleep(800);
    await shot(page, "t03-cancelled");
    results.push({ flow: "transfer-cancel", ok: true });

    // ---------- 2. transfer modify branch ----------
    await newThread(page);
    await send(page, "给妈妈转500元，主账户A1");
    await waitText(page, "确认办理");
    await sleep(400);
    await clickInTask(page, "修改");
    await waitText(page, "原确认单已取消");
    await sleep(900);
    await shot(page, "t04-modify");
    results.push({ flow: "transfer-modify", ok: true });

    // ---------- 3. verification card + demo code + wrong code ----------
    await newThread(page);
    await send(page, "给妈妈转500元，主账户A1");
    await waitText(page, "确认办理");
    await sleep(400);
    await clickInTask(page, "确认办理");
    await waitText(page, "等您验证");
    await sleep(800);
    await shot(page, "t05-verification");
    await clickInTask(page, "点这里查看");
    await page.waitForFunction(() => {
      const strong = document.querySelector(".sh-task .sh-demo-code strong");
      return Boolean(strong && /^\d{6}$/.test(strong.textContent.trim()));
    }, { timeout: 60000, polling: 300 });
    await sleep(500);
    await shot(page, "t06-demo-code");
    const demoCode = await page.evaluate(() => document.querySelector(".sh-task .sh-demo-code strong").textContent.trim());
    log("demo-code", { demoCode });
    await page.evaluate(() => {
      const input = document.querySelector(".sh-task .sh-code-input");
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      setter.call(input, "");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const wrong = demoCode === "000000" ? "111111" : "000000";
    await page.type(".sh-task .sh-code-input", wrong, { delay: 30 });
    await shot(page, "t07-code-entered");
    await clickInTask(page, "提交验证码");
    await waitText(page, "没有转出去", 120000).catch(async () => {
      await waitText(page, "验证码", 30000);
    });
    await sleep(1200);
    await shot(page, "t08-code-failed");
    results.push({ flow: "transfer-wrong-code", ok: true });

    // ---------- 4. recovery gate after reloading mid-confirmation ----------
    await newThread(page);
    await send(page, "给妈妈转500元，主账户A1");
    await waitText(page, "确认办理");
    await sleep(400);
    await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
    await waitReady(page);
    await waitText(page, "有一项没办完的任务", 60000);
    await sleep(600);
    await shot(page, "t09-recovery-gate");
    await clickInTask(page, "查看原任务");
    await waitText(page, "已恢复原任务", 60000);
    await sleep(800);
    await shot(page, "t10-recovery-readable");
    results.push({ flow: "transfer-recovery", ok: true });

    // ---------- 5. high-risk refusal (502 demo scenario) ----------
    await newThread(page);
    await send(page, "给妈妈转502元，主账户A1");
    await sleep(2000);
    await waitText(page, "高风险", 240000).catch(async () => {
      await waitText(page, "终止", 60000).catch(async () => {
        await waitText(page, "不能", 60000);
      });
    });
    await sleep(1200);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(OUT, "t11-highrisk.png") });
    log("shot", { name: "t11-highrisk" });
    results.push({ flow: "transfer-highrisk", ok: true });

    // ---------- 6. bills summary ----------
    await newThread(page);
    await send(page, "这个月花了多少");
    await waitChoice(page);
    await shot(page, "b01-summary-choice");
    await clickChoice(page, ["所有本人账户"]);
    await waitText(page, "消费汇总");
    await sleep(1000);
    await shot(page, "b02-summary-card");
    results.push({ flow: "bills-summary", ok: true });

    // ---------- 7. bills detail (dining) ----------
    await newThread(page);
    await send(page, "看看这个月的餐饮明细");
    await waitChoice(page);
    await shot(page, "b03-detail-choice");
    await clickChoice(page, ["所有本人账户"]);
    await waitText(page, "餐饮明细");
    await sleep(1000);
    await shot(page, "b04-detail-card");
    results.push({ flow: "bills-detail", ok: true });

    // ---------- 8. bills anomaly: range -> listing -> account -> candidate -> finding ----------
    await newThread(page);
    await send(page, "这笔钱我不认识，是不是扣错了");
    await waitChoice(page);
    await shot(page, "b05-anomaly-choice-range");
    await clickChoice(page, ["本月"]);
    await waitChoice(page);
    await shot(page, "b06-anomaly-choice-listing");
    await clickChoice(page, ["列出原范围流水"]);
    await waitChoice(page);
    await shot(page, "b07-anomaly-choice-account");
    await clickChoice(page, ["所有本人账户"]);
    await waitChoice(page);
    await shot(page, "b08-anomaly-choice-candidate");
    await clickChoice(page, ["500.00", "王", "2026-10"]);
    await page.waitForFunction(() => {
      const text = document.body.innerText;
      return text.includes("有账单提示") || text.includes("没有发现需要留意的交易") || text.includes("需要留意");
    }, { timeout: 240000, polling: 300 });
    await sleep(1200);
    await shot(page, "b09-anomaly-card");
    results.push({ flow: "bills-anomaly", ok: true });

    // ---------- 9. bills report ----------
    await newThread(page);
    await send(page, "给我出一份这个月的账单");
    await waitChoice(page);
    await shot(page, "b10-report-choice");
    await clickChoice(page, ["所有本人账户"]);
    await waitText(page, "账单报告");
    await sleep(1200);
    await shot(page, "b11-report-card");
    results.push({ flow: "bills-report", ok: true });

    fs.writeFileSync(path.join(OUT, "capture.json"), JSON.stringify({ capturedAt: new Date().toISOString(), base: BASE, results }, null, 2), "utf8");
    console.log("CAPTURE OK", results.length);
  } catch (error) {
    console.log("CAPTURE FAILED:", error.message);
    await page.screenshot({ path: path.join(OUT, "zz-error.png") }).catch(() => undefined);
    fs.writeFileSync(path.join(OUT, "capture.json"), JSON.stringify({ capturedAt: new Date().toISOString(), error: error.message, results }, null, 2), "utf8");
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
