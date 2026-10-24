/* Resumable capture of real-API v0.4 frontend states for the E2E showcase board.
 * Usage: node capture2.cjs [flow1,flow2,...]
 * Flows: modify, verifyWrong, recovery, highrisk, summary, detail, anomaly, report
 */
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const BASE = process.env.CAPTURE_BASE || "http://127.0.0.1:5173/";
const OUT = process.env.CAPTURE_OUT || path.join(__dirname, "..", "raw");
fs.mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const log = (name, data = {}) => console.log(`[${new Date().toISOString().slice(11, 19)}] ${name} ${JSON.stringify(data).slice(0, 260)}`);

let page;
async function waitReady() {
  await page.waitForFunction(() => document.querySelector("#sh-input") && !document.querySelector("#sh-input").disabled, { timeout: 120000, polling: 300 });
  await page.waitForFunction(() => document.body.innerText.includes("已连接"), { timeout: 60000, polling: 300 });
  await sleep(300);
}
async function newThread() {
  await page.evaluate(async () => {
    await fetch("/api/v1/threads", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ request_id: crypto.randomUUID() }) });
  });
  await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
  await waitReady();
  await sleep(500);
}
async function send(text) {
  await page.click("#sh-input");
  await page.type("#sh-input", text, { delay: 10 });
  await page.evaluate(() => Array.from(document.querySelectorAll("button")).find((b) => b.textContent.includes("发送")).click());
  log("send", { text });
}
async function shot(name) {
  await page.evaluate(() => {
    const tasks = document.querySelectorAll(".sh-task");
    const last = tasks[tasks.length - 1];
    if (last) last.scrollIntoView({ block: "center", behavior: "instant" });
  });
  await sleep(450);
  await page.screenshot({ path: path.join(OUT, name + ".png") });
  log("shot", { name });
}
async function waitText(text, timeout = 300000) {
  await page.waitForFunction((t) => document.body.innerText.includes(t), { timeout, polling: 300 }, text);
}
async function waitAny(texts, timeout = 300000) {
  await page.waitForFunction((list) => list.some((t) => document.body.innerText.includes(t)), { timeout, polling: 300 }, texts);
}
async function clickInTask(text, timeout = 30000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const state = await page.evaluate((t) => {
      const tasks = document.querySelectorAll(".sh-task");
      const node = tasks[tasks.length - 1];
      if (!node) return "no-task";
      const button = Array.from(node.querySelectorAll("button")).find((b) => !b.disabled && (b.textContent || "").replace(/\s+/g, "").includes(t.replace(/\s+/g, "")));
      if (!button) return "missing";
      button.scrollIntoView({ block: "center", behavior: "instant" });
      button.click();
      return "clicked";
    }, text);
    if (state === "clicked") { log("click", { text }); return; }
    await sleep(300);
  }
  throw new Error("无法点击任务按钮: " + text);
}
async function choiceLabels() {
  return page.evaluate(() => {
    const tasks = document.querySelectorAll(".sh-task");
    const node = tasks[tasks.length - 1];
    return node ? Array.from(node.querySelectorAll(".sh-choice:not([disabled])")).map((b) => b.textContent.trim()) : [];
  });
}
async function clickChoice(preferences) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const labels = await choiceLabels();
    if (labels.length > 0) {
      let target = null;
      for (const pref of preferences) { const hit = labels.find((label) => label.includes(pref)); if (hit) { target = hit; break; } }
      if (!target) target = labels[0];
      await page.evaluate((label) => {
        const tasks = document.querySelectorAll(".sh-task");
        const node = tasks[tasks.length - 1];
        const button = Array.from(node.querySelectorAll(".sh-choice")).find((b) => b.textContent.trim() === label);
        button.scrollIntoView({ block: "center", behavior: "instant" });
        button.click();
      }, target);
      log("choice", { target });
      await sleep(1500);
      return target;
    }
    await sleep(800);
  }
  throw new Error("等待选项超时");
}
async function waitChoice(timeout = 300000) {
  await page.waitForFunction(() => {
    const tasks = document.querySelectorAll(".sh-task");
    const node = tasks[tasks.length - 1];
    return Boolean(node && node.querySelector(".sh-choice:not([disabled])"));
  }, { timeout, polling: 300 });
  await sleep(400);
}
// Wait until the current transfer task shows its confirmation card, answering obvious choices first.
async function ensureConfirmation() {
  const deadline = Date.now() + 300000;
  while (Date.now() < deadline) {
    const state = await page.evaluate(() => ({
      confirm: document.body.innerText.includes("确认办理"),
      choice: Array.from(document.querySelectorAll(".sh-choice:not([disabled])")).map((b) => b.textContent.trim()),
      terminal: /已取消|没有转出去|高风险|终止/.test(document.body.innerText),
    }));
    if (state.confirm) return;
    if (state.choice.length > 0) { await clickChoice(["所有本人账户", "主账户", "妈妈", "A1"]); continue; }
    if (state.terminal) throw new Error("任务在该步骤已终止: " + JSON.stringify(state));
    await sleep(800);
  }
  throw new Error("等待确认单超时");
}

const flow = {
  async modify() {
    await newThread();
    await send("给妈妈转500元，主账户A1");
    await ensureConfirmation();
    await sleep(400);
    await clickInTask("修改");
    await page.waitForFunction(() => Boolean(document.querySelector(".sh-task .sh-modify textarea")), { timeout: 30000, polling: 300 });
    await page.type(".sh-task .sh-modify textarea", "金额改为300元", { delay: 20 });
    await page.evaluate(() => {
      const button = Array.from(document.querySelectorAll(".sh-task .sh-modify button")).find((b) => b.textContent.includes("取消旧确认并准备修改"));
      if (!button) throw new Error("找不到提交修改按钮");
      button.click();
    });
    await page.waitForFunction(() => {
      const input = document.querySelector("#sh-input");
      return Boolean(input && input.value.includes("请将当前转账调整为"));
    }, { timeout: 60000, polling: 300 });
    await sleep(700);
    await shot("t04-modify");
  },
  async verifyWrong() {
    await newThread();
    await send("给妈妈转500元，主账户A1");
    await ensureConfirmation();
    await sleep(400);
    await clickInTask("确认办理");
    await waitText("等您验证", 180000);
    await sleep(900);
    await shot("t05-verification");
    await clickInTask("点这里查看");
    await page.waitForFunction(() => {
      const strong = document.querySelector(".sh-task .sh-demo-code strong");
      return Boolean(strong && /^\d{6}$/.test(strong.textContent.trim()));
    }, { timeout: 60000, polling: 300 });
    await sleep(500);
    await shot("t06-demo-code");
    const demoCode = await page.evaluate(() => document.querySelector(".sh-task .sh-demo-code strong").textContent.trim());
    log("demo-code", { demoCode });
    await page.evaluate(() => {
      const input = document.querySelector(".sh-task .sh-code-input");
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      setter.call(input, "");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await page.type(".sh-task .sh-code-input", demoCode === "000000" ? "111111" : "000000", { delay: 30 });
    await shot("t07-code-entered");
    await clickInTask("提交验证码");
    await waitAny(["验证码不正确", "没有转出去", "办理已终止"], 180000);
    await sleep(1200);
    await shot("t08-code-failed");
  },
  async recovery() {
    await newThread();
    await send("给妈妈转500元，主账户A1");
    await ensureConfirmation();
    await sleep(400);
    await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
    await waitReady();
    await waitText("有一项没办完的任务", 90000);
    await sleep(600);
    await shot("t09-recovery-gate");
    await clickInTask("查看原任务");
    await waitText("已恢复原任务", 90000);
    await sleep(800);
    await shot("t10-recovery-readable");
  },
  async highrisk() {
    await newThread();
    await send("给妈妈转502元，主账户A1");
    await sleep(2000);
    const deadline = Date.now() + 180000;
    while (Date.now() < deadline) {
      const text = await page.evaluate(() => document.body.innerText);
      if (/高风险|终止|不能办理|拒绝|不安全/.test(text)) break;
      await sleep(1500);
    }
    await waitReady().catch(() => undefined);
    await sleep(1000);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(OUT, "t11-highrisk.png") });
    log("shot", { name: "t11-highrisk" });
  },
  async summary() {
    await newThread();
    await send("这个月花了多少");
    await waitChoice();
    await shot("b01-summary-choice");
    await clickChoice(["所有本人账户"]);
    await waitText("消费汇总", 300000);
    await sleep(1200);
    await shot("b02-summary-card");
  },
  async detail() {
    await newThread();
    await send("看看这个月的餐饮明细");
    await waitChoice();
    await shot("b03-detail-choice");
    await clickChoice(["所有本人账户"]);
    await waitText("餐饮明细", 300000);
    await sleep(1200);
    await shot("b04-detail-card");
  },
  async anomaly() {
    await newThread();
    await send("这笔钱我不认识，是不是扣错了");
    await waitChoice();
    await shot("b05-anomaly-choice-range");
    await clickChoice(["本月"]);
    await waitChoice();
    await shot("b06-anomaly-choice-listing");
    await clickChoice(["列出原范围流水"]);
    await waitChoice();
    await shot("b07-anomaly-choice-account");
    await clickChoice(["所有本人账户"]);
    await waitChoice();
    await shot("b08-anomaly-choice-candidate");
    await clickChoice(["500.00", "王", "2026-10"]);
    await waitAny(["有账单提示", "没有发现需要留意的交易", "需要留意"], 300000);
    await sleep(1500);
    await shot("b09-anomaly-card");
  },
  async report() {
    await newThread();
    await send("给我出一份这个月的账单");
    await waitChoice();
    await shot("b10-report-choice");
    await clickChoice(["所有本人账户"]);
    await waitText("账单报告", 300000);
    await sleep(1500);
    await shot("b11-report-card");
  },
};

(async () => {
  const only = (process.argv[2] || Object.keys(flow).join(",")).split(",").map((s) => s.trim()).filter(Boolean);
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: true,
    args: ["--lang=zh-CN", "--no-first-run", "--window-size=1280,900"],
    defaultViewport: { width: 1280, height: 900 },
  });
  page = await browser.newPage();
  page.setDefaultTimeout(300000);
  page.on("pageerror", (e) => console.log("PAGE-ERROR:", e.message));
  try {
    await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 60000 });
    await waitReady();
    for (const key of only) {
      const started = Date.now();
      try {
        await flow[key]();
        results.push({ flow: key, ok: true, seconds: Math.round((Date.now() - started) / 1000) });
        console.log("FLOW OK", key);
      } catch (error) {
        results.push({ flow: key, ok: false, error: error.message });
        console.log("FLOW FAILED", key, error.message.slice(0, 200));
        await page.screenshot({ path: path.join(OUT, "zz-" + key + "-error.png") }).catch(() => undefined);
        await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
        await waitReady().catch(() => undefined);
      }
    }
  } finally {
    fs.writeFileSync(path.join(OUT, "capture-" + (only[0] || "all") + ".json"), JSON.stringify({ capturedAt: new Date().toISOString(), results }, null, 2), "utf8");
    await browser.close();
  }
})();
