/* Real-API browser walkthrough for PR #199 (frontend bills slot), 2026-10-20.
 * Stack: real local-demo backend (GLM Coding Plan glm-5.3 + mock bank) + Vite dev server (real-api).
 * Four scenarios, each in its own clean thread: summary / dining details / anomaly check / monthly report.
 * Every rendered value is compared against the same task payload returned by the API.
 */
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const BASE = process.env.WALKTHROUGH_BASE || "http://127.0.0.1:5173/v04";
const OUT = process.env.WALKTHROUGH_OUT || path.join(__dirname, "run");
fs.mkdirSync(OUT, { recursive: true });

const scenario = process.argv[2] || "all";
const apiCalls = [];
const consoleErrors = [];
const steps = [];
let counter = 0;
const record = (name, data = {}) => {
  counter += 1;
  steps.push({ n: counter, name, at: new Date().toISOString(), ...data });
  console.log(`[${counter}] ${name} ${JSON.stringify(data).slice(0, 400)}`);
};
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const yuan = (fen) => (typeof fen === "number" ? "¥" + (fen / 100).toFixed(2) : "未返回");
const share = (bps) => (bps / 100).toFixed(2) + "%";
// Mirror the page's timeLabel: Asia/Shanghai, "yyyy/MM/dd HH:mm".
const isoLabel = (value) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const parts = Object.fromEntries(new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  }).formatToParts(date).map((part) => [part.type, part.value]));
  return `${parts.year}/${parts.month}/${parts.day} ${parts.hour}:${parts.minute}`;
};
const rowParts = (item) => {
  const nature = NATURE[item.nature] ?? item.nature;
  const category = CATEGORY[item.category] ?? item.category;
  return [yuan(item.amount_fen), ...(nature === category ? [nature] : [nature, category]), isoLabel(item.occurred_at)];
};
const CATEGORY = { dining: "餐饮", transport: "交通", medical: "医疗", shopping: "购物", housing: "居住", transfer: "转账", other: "其他" };
const NATURE = { consumption: "消费", transfer: "转账", refund: "退款", interest: "利息" };
const REASON = {
  insufficient_facts: "缺少判断依据",
  lookback_incomplete: "缺少三个月历史流水",
  trusted_family_status_required: "本人转账关系未确认",
  counterparty_or_lookback_missing: "缺少对手方或历史流水",
  amount_baseline_missing: "缺少金额参照",
  timezone_missing: "缺少交易时间",
  periodic_history_incomplete: "缺少连续扣款历史",
  merchant_identity_missing: "缺少商户信息",
};
const ATTENTION = { notice: "提示", high_attention: "重点提示" };

async function waitReady(page, label) {
  await page.waitForFunction(() => document.querySelector("#sh-input") && !document.querySelector("#sh-input").disabled,
    { timeout: 120000, polling: 300 });
  await page.waitForFunction(() => document.body.innerText.includes("已连接"), { timeout: 60000, polling: 300 });
  record("ready", { label });
}

async function newThread(page) {
  const created = await page.evaluate(async () => {
    const response = await fetch("/api/v1/threads", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ request_id: crypto.randomUUID() }),
    });
    return (await response.json()).data.thread_id;
  });
  await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
  await waitReady(page, "new-thread " + created);
  return created;
}

const taskBlocks = (page) => page.evaluate(() => Array.from(document.querySelectorAll(".sh-task")).map((n) => {
  const resultCard = Array.from(n.querySelectorAll(".sh-card")).find((card) => {
    const head = card.querySelector("h3");
    return head && head.textContent.trim() === "办理结果";
  });
  const reportCard = Array.from(n.querySelectorAll(".sh-card")).find((card) => card.querySelector(".sh-report-headline"));
  const choiceCard = Array.from(n.querySelectorAll(".sh-card")).find((card) => card.querySelector(".sh-choices"));
  return {
    id: n.getAttribute("data-task-id"),
    text: n.innerText.replace(/\s+/g, " ").trim(),
    resultText: resultCard ? resultCard.innerText.replace(/\s+/g, " ").trim() : null,
    reportText: reportCard ? reportCard.innerText.replace(/\s+/g, " ").trim() : null,
    choiceText: choiceCard ? choiceCard.innerText.replace(/\s+/g, " ").trim() : null,
    buttons: Array.from(n.querySelectorAll("button")).map((b) => ({ text: b.textContent.trim(), disabled: b.disabled })),
  };
}));

async function clickChoice(page, preferences) {
  const options = await page.evaluate(() => Array.from(document.querySelectorAll(".sh-choice:not([disabled])")).map((b) => b.textContent.trim()));
  if (options.length === 0) return null;
  let target = null;
  for (const pref of preferences) {
    const hit = options.find((label) => label.includes(pref));
    if (hit) { target = hit; break; }
  }
  if (!target) target = options[0];
  await page.evaluate((label) => {
    const button = Array.from(document.querySelectorAll(".sh-choice")).find((b) => b.textContent.trim() === label);
    button.click();
  }, target);
  record("choice-clicked", { target, options });
  return target;
}

async function fetchTask(page, taskId) {
  return page.evaluate(async (id) => (await (await fetch("/api/v1/tasks/" + id)).json()).data, taskId);
}

function check(conditions) {
  const failed = conditions.filter((item) => !item.ok).map((item) => item.name + (item.detail ? ": " + item.detail : ""));
  return { checks: Object.fromEntries(conditions.map((item) => [item.name, item.ok])), failed };
}

function assertAll(name, data, text, conditions) {
  conditions.push({ name, ok: data.includes(text), detail: "missing " + JSON.stringify(text) });
}

async function runScenario(page, spec) {
  console.log("=== scenario", spec.key, "===");
  const threadId = await newThread(page);
  const known = new Set((await taskBlocks(page)).map((block) => block.id));
  const phaseCalls = [];
  const onResponse = (response) => {
    const url = response.url();
    if (!url.includes("/api/v1/")) return;
    const call = { phase: spec.key, method: response.request().method(), url: url.replace("http://127.0.0.1:5173", ""), status: response.status() };
    apiCalls.push(call);
    phaseCalls.push(call);
  };
  page.on("response", onResponse);
  try {
    await page.click("#sh-input");
    await page.type("#sh-input", spec.message, { delay: 15 });
    await page.evaluate(() => Array.from(document.querySelectorAll("button")).find((b) => b.textContent.includes("发送")).click());
    record("send", { message: spec.message, threadId });

    let blocks = [];
    let taskId = null;
    const deadline = Date.now() + 300000;
    while (Date.now() < deadline) {
      blocks = await taskBlocks(page);
      const fresh = blocks.filter((block) => !known.has(block.id));
      if (fresh.length > 0) {
        const active = fresh[fresh.length - 1];
        taskId = active.id;
        if (active.choiceText) {
          await page.screenshot({ path: path.join(OUT, `${spec.key}-choice.png`), fullPage: true });
          const clicked = await clickChoice(page, spec.prefs);
          if (clicked) await sleep(1200);
          continue;
        }
        const task = await fetchTask(page, taskId);
        const terminal = ["succeeded", "failed", "cancelled", "partially_succeeded"].includes(task.status);
        if (terminal && (active.resultText || active.reportText)) {
          const typed = await page.evaluate(() => document.querySelector("#sh-input").value);
          record("terminal", { taskId, status: task.status, dirtyInput: typed });
          break;
        }
      }
      await sleep(600);
    }
    if (!taskId) throw new Error("no task block appeared");
    const task = await fetchTask(page, taskId);
    const data = task.data;
    const finalBlock = (await taskBlocks(page)).find((block) => block.id === taskId);
    if (!finalBlock || (!finalBlock.resultText && !finalBlock.reportText)) throw new Error("terminal card missing");
    const pageText = await page.evaluate(() => document.body.innerText.replace(/\s+/g, " "));
    const dom = await page.evaluate(() => ({
      demoNotes: Array.from(document.querySelectorAll(".sh-demo-note")).map((n) => n.innerText.trim()),
      ribbon: Boolean(document.querySelector(".sh-ribbon")),
      topbar: (document.querySelector(".sh-topbar") || {}).innerText || "",
    }));
    await page.screenshot({ path: path.join(OUT, `${spec.key}.png`), fullPage: true });
    fs.writeFileSync(path.join(OUT, `${spec.key}-task.json`), JSON.stringify({ task, threadId }, null, 2), "utf8");
    fs.writeFileSync(path.join(OUT, `${spec.key}-block.txt`), finalBlock.text, "utf8");
    const verdict = spec.assert({ task, data, block: finalBlock, pageText, dom });
    fs.writeFileSync(path.join(OUT, `${spec.key}-checks.json`), JSON.stringify(verdict, null, 2), "utf8");
    record("checks", { scenario: spec.key, failed: verdict.failed, status: task.status });
    return { scenario: spec.key, taskId, threadId, status: task.status, failed: verdict.failed, checks: verdict.checks, api: phaseCalls };
  } finally {
    page.off("response", onResponse);
  }
}

const summarySpec = {
  key: "summary",
  message: "这个月花了多少",
  prefs: ["所有本人账户"],
  assert({ task, data, block, pageText, dom }) {
    const conditions = [];
    const text = block.resultText || "";
    const fail = (name, ok, detail) => conditions.push({ name, ok, detail });
    fail("summaryTaskSucceeded", task.status === "succeeded");
    fail("cardTitle", text.includes("消费汇总"), text.slice(0, 120));
    fail("headlineNet", text.includes(yuan(data.consumption_net_fen)), yuan(data.consumption_net_fen));
    for (const [label, fen] of [["消费支出", data.consumption_gross_fen], ["退款", data.consumption_refund_fen], ["转出", data.transfer_out_fen], ["转入", data.transfer_in_fen]]) {
      fail("field-" + label, text.includes(label + " " + yuan(fen)), label + " " + yuan(fen));
    }
    fail("count", text.includes("笔数 " + data.transaction_count), String(data.transaction_count));
    fail("accounts", text.includes("覆盖账户 " + data.scope.account_ids.length + " 个"), String(data.scope.account_ids.length));
    for (const item of data.categories) {
      const label = `第 ${item.rank} 类 · ${CATEGORY[item.category] ?? item.category}`;
      const expected = label + " " + yuan(item.net_fen) + (typeof item.share_bps === "number" ? " · 占比 " + share(item.share_bps) : "");
      fail("category-" + item.rank, text.includes(expected), expected);
    }
    fail("asOf", text.includes("数据时间 " + isoLabel(data.as_of)), isoLabel(data.as_of));
    fail("noDemoNote", dom.demoNotes.length === 0 && !dom.ribbon);
    fail("realApiTopbar", dom.topbar.includes("已连接"));
    const back = task.message ? String(task.message) : "";
    fail("serverMessagePresent", back.length > 0);
    return check(conditions);
  },
};

const detailSpec = {
  key: "detail",
  message: "看看这个月的餐饮明细",
  prefs: ["所有本人账户"],
  assert({ task, data, block, dom }) {
    const conditions = [];
    const text = block.resultText || "";
    const fail = (name, ok, detail) => conditions.push({ name, ok, detail });
    fail("detailTaskSucceeded", task.status === "succeeded");
    fail("cardTitle", text.includes(data.category ? (CATEGORY[data.category] ?? data.category) + "明细" : "账单明细"), text.slice(0, 120));
    fail("headlineCount", text.includes(data.transactions.length + " 笔"), String(data.transactions.length));
    for (const item of data.transactions) {
      const expected = rowParts(item);
      if (item.counterparty_account_masked) expected.push(item.counterparty_account_masked);
      if (item.summary) expected.push(item.summary);
      const line = expected.join(" · ");
      fail("row-" + item.transaction_id, text.includes(item.counterparty_name) && text.includes(line), line);
      if (!item.counterparty_name.includes("*")) fail("merchantUnmasked-" + item.transaction_id, !text.includes("***"), item.counterparty_name);
      if (item.counterparty_account_masked) fail("accountMasked-" + item.transaction_id, /[*]{2,}/.test(item.counterparty_account_masked) && text.includes(item.counterparty_account_masked));
    }
    fail("asOfNote", text.includes("数据时间：" + isoLabel(data.as_of)), isoLabel(data.as_of));
    fail("noDemoNote", dom.demoNotes.length === 0 && !dom.ribbon);
    const back = task.message ? String(task.message) : "";
    fail("serverMessagePresent", back.length > 0);
    return check(conditions);
  },
};

const filterDetailSpec = {
  key: "detailTransfer",
  message: "看看这个月的转账明细",
  prefs: ["所有本人账户"],
  assert({ task, data, block, dom }) {
    const conditions = [];
    const text = block.resultText || "";
    const fail = (name, ok, detail) => conditions.push({ name, ok, detail });
    fail("detailTaskSucceeded", task.status === "succeeded");
    fail("cardTitle", text.includes(data.category ? (CATEGORY[data.category] ?? data.category) + "明细" : "账单明细"), text.slice(0, 120));
    fail("headlineCount", text.includes(data.transactions.length + " 笔"), String(data.transactions.length));
    const maskedRows = data.transactions.filter((item) => item.counterparty_account_masked);
    fail("hasMaskedRows", maskedRows.length > 0, String(maskedRows.length));
    for (const item of data.transactions) {
      const expected = rowParts(item);
      if (item.counterparty_account_masked) expected.push(item.counterparty_account_masked);
      if (item.summary) expected.push(item.summary);
      const line = expected.join(" · ");
      fail("row-" + item.transaction_id, text.includes(item.counterparty_name) && text.includes(line), line);
      if (item.counterparty_account_masked) fail("accountMasked-" + item.transaction_id, text.includes(item.counterparty_account_masked));
    }
    fail("noDemoNote", dom.demoNotes.length === 0 && !dom.ribbon);
    return check(conditions);
  },
};

const anomalySpec = {
  key: "anomaly",
  message: "这笔钱我不认识，是不是扣错了",
  prefs: ["本月", "列出原范围流水", "所有本人账户", "18 · 2026-10-20"],
  assert({ task, data, block, pageText, dom }) {
    const conditions = [];
    const text = block.resultText || "";
    const fail = (name, ok, detail) => conditions.push({ name, ok, detail });
    fail("anomalyTaskSucceeded", task.status === "succeeded");
    const high = data.findings.some((finding) => finding.attention === "high_attention");
    const title = data.findings.length === 0 ? "没有发现需要留意的交易" : high ? "有需要留意的账单" : "有账单提示";
    fail("cardTitle", text.includes(title), title);
    if (data.transaction) {
      const row = rowParts(data.transaction).join(" · ");
      fail("locatedTransaction", text.includes(data.transaction.counterparty_name) && text.includes(row), row);
    }
    for (const finding of data.findings) {
      fail("finding-rule-" + finding.rule_id, text.includes(ATTENTION[finding.attention] + " · 规则 " + finding.rule_id));
      fail("finding-evidence-" + finding.rule_id, text.includes(finding.evidence));
      fail("finding-suggestion-" + finding.rule_id, text.includes(finding.suggestion));
    }
    for (const item of data.checks) {
      if (item.status !== "insufficient_data") continue;
      fail("insufficient-" + item.rule_id, text.includes("规则 " + item.rule_id + " 数据不足") && text.includes(REASON[item.reason] ?? "这次没能核对"), String(item.reason));
    }
    fail("noActionButtons", block.buttons.length === 0, JSON.stringify(block.buttons));
    fail("noDemoNote", dom.demoNotes.length === 0 && !dom.ribbon);
    fail("noFabricatedAmount", data.findings.length > 0 ? true : !/新商户且金额|超过近三个月/.test(text));
    return check(conditions);
  },
};

const reportSpec = {
  key: "report",
  message: "给我出一份这个月的账单",
  prefs: ["所有本人账户"],
  assert({ task, data, block, details, dom }) {
    const conditions = [];
    const text = block.reportText || "";
    const fail = (name, ok, detail) => conditions.push({ name, ok, detail });
    fail("reportTaskSucceeded", task.status === "succeeded");
    fail("noResultCard", !block.resultText);
    fail("cardTitle", text.includes("账单报告"), text.slice(0, 120));
    fail("period", text.includes("统计范围：" + isoLabel(data.scope.start_at) + " 起，" + isoLabel(data.scope.end_at) + " 止"), isoLabel(data.scope.start_at));
    fail("headline", text.includes("消费净额") && text.includes(yuan(data.summary.consumption_net_fen)));
    for (const [label, fen] of [["消费支出", data.summary.consumption_gross_fen], ["退款", data.summary.consumption_refund_fen], ["转出", data.summary.transfer_out_fen], ["转入", data.summary.transfer_in_fen]]) {
      fail("field-" + label, text.includes(label + " " + yuan(fen)), label + " " + yuan(fen));
    }
    fail("count", text.includes("笔数 " + data.summary.transaction_count));
    for (const item of data.summary.categories) {
      const expected = `第 ${item.rank} 类 · ${CATEGORY[item.category] ?? item.category} ${yuan(item.net_fen)}` + (typeof item.share_bps === "number" ? " · 占比 " + share(item.share_bps) : "");
      fail("category-" + item.rank, text.includes(expected), expected);
    }
    if (typeof data.monthly_average_fen === "number") fail("monthlyAverage", text.includes("月均消费 " + yuan(data.monthly_average_fen)));
    else fail("monthlyAverage", !text.includes("月均消费"));
    fail("statisticalDays", text.includes("统计天数 " + data.statistical_days), String(data.statistical_days));
    fail("averageBasis", text.includes("月均口径 " + data.average_basis), data.average_basis);
    fail("generatedAt", text.includes("报告生成时间 " + isoLabel(data.generated_at)), isoLabel(data.generated_at));
    fail("spokenSummary", text.includes(data.spoken_summary), data.spoken_summary);
    // The report card must not carry raw transactions: no merchant names or transaction ids from the details payloads.
    const transactions = (details || []).flatMap((payload) => (payload && payload.transactions) || []);
    const merchants = transactions.map((item) => item.counterparty_name).filter((name) => name && name.length >= 2);
    const leakedMerchants = merchants.filter((name) => text.includes(name));
    const txnIds = transactions.map((item) => item.transaction_id);
    const leakedIds = txnIds.filter((id) => text.includes(id));
    fail("noRawTransactions", leakedMerchants.length === 0 && leakedIds.length === 0, JSON.stringify({ leakedMerchants, leakedIds }));
    fail("noDemoText", !/演示数据|演示结果/.test(text) && dom.demoNotes.length === 0 && !dom.ribbon);
    return check(conditions);
  },
};

const SCENARIOS = { summary: summarySpec, detail: detailSpec, detailTransfer: filterDetailSpec, anomaly: anomalySpec, report: reportSpec };

(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: true,
    args: ["--lang=zh-CN", "--no-first-run", "--window-size=1280,900"],
    defaultViewport: { width: 1280, height: 900 },
  });
  const page = await browser.newPage();
  page.setDefaultTimeout(300000);
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => consoleErrors.push("pageerror: " + error.message));
  const results = [];
  let detailsPayloads = [];
  try {
    await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 60000 });
    await waitReady(page, "boot");
    const boot = await page.evaluate(() => ({
      ribbon: Boolean(document.querySelector(".sh-ribbon")),
      demoNotes: Array.from(document.querySelectorAll(".sh-demo-note")).length,
      topbar: (document.querySelector(".sh-topbar") || {}).innerText || "",
      hints: document.body.innerText.includes("这个月花了多少") && document.body.innerText.includes("给我出一份这个月的账单"),
    }));
    record("boot-origin", { ribbon: boot.ribbon, demoNotes: boot.demoNotes, topbar: boot.topbar.replace(/\s+/g, " "), billsHints: boot.hints });
    fs.writeFileSync(path.join(OUT, "boot.json"), JSON.stringify(boot, null, 2), "utf8");

    const order = scenario === "all" ? ["summary", "detail", "detailTransfer", "anomaly", "report"] : [scenario];
    for (const key of order) {
      const spec = SCENARIOS[key];
      if (key === "report" && detailsPayloads.length > 0) spec.assert = ((original) => (args) => original({ ...args, details: detailsPayloads }))(spec.assert);
      const result = await runScenario(page, spec);
      results.push(result);
      if (key === "detail" || key === "detailTransfer") detailsPayloads.push(JSON.parse(fs.readFileSync(path.join(OUT, key + "-task.json"), "utf8")).task.data);
      if (result.failed.length > 0) console.log("SCENARIO FAILED:", key, result.failed);
    }

    const failures = apiCalls.filter((call) => call.status >= 400);
    const expected = failures.filter((call) => (call.status === 401 && call.url === "/api/v1/session") || call.status === 409);
    const unexpected = failures.filter((call) => !expected.includes(call));
    record("api-summary", {
      total: apiCalls.length,
      byStatus: apiCalls.reduce((acc, call) => { acc[call.status] = (acc[call.status] || 0) + 1; return acc; }, {}),
      expected: expected.map((call) => call.status + " " + call.url),
      unexpected,
    });
    const checks = {};
    for (const result of results) Object.entries(result.checks).forEach(([name, ok]) => { checks[result.scenario + "." + name] = ok; });
    checks["api.noUnexpectedFailures"] = unexpected.length === 0;
    checks["console.noErrors"] = consoleErrors.filter((line) => !/Failed to load resource/.test(line)).length === 0;
    const verdict = Object.entries(results).every(([, result]) => result.failed.length === 0) && checks["api.noUnexpectedFailures"] ? "PASS" : "FAIL";
    const evidence = {
      capturedAt: new Date().toISOString(),
      base: BASE,
      stack: { frontend: "vite dev, VITE_API_MODE=real-api", backend: "local-demo uvicorn 127.0.0.1:8000", model: "zhipu Coding Plan glm-5.3", browser: "Microsoft Edge headless 1280x900" },
      verdict,
      checks,
      results,
      apiCalls,
      consoleErrors,
      unexpectedApiFailures: unexpected,
      steps,
    };
    fs.writeFileSync(path.join(OUT, "walkthrough.json"), JSON.stringify(evidence, null, 2), "utf8");
    console.log("CHECKS=" + JSON.stringify(checks));
    console.log("VERDICT=" + verdict);
    process.exitCode = verdict === "PASS" ? 0 : 2;
  } catch (error) {
    record("error", { message: error.message });
    fs.writeFileSync(path.join(OUT, "walkthrough.json"), JSON.stringify({ capturedAt: new Date().toISOString(), base: BASE, steps, apiCalls, consoleErrors, verdict: "ERROR", error: error.message }, null, 2), "utf8");
    await page.screenshot({ path: path.join(OUT, "99-error.png"), fullPage: true }).catch(() => undefined);
    console.error("WALKTHROUGH FAILED: " + error.message);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
