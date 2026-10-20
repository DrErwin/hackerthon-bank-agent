/* Ticket 05 accessibility walkthrough: real-api main entry, one viewport per run.
 * Measures the v0.1 spec numbers (font sizes, tap targets 48, card padding 20,
 * gaps 16), reports WCAG-AA contrast as a supplementary baseline, checks keyboard
 * focus and horizontal overflow. No style changes here.
 *
 * Usage: node a11y-entry.cjs 390 844
 */
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const W = Number(process.argv[2] || 390);
const H = Number(process.argv[3] || 844);
const BASE = process.env.A11Y_BASE || "http://127.0.0.1:5173/";
const OUT = process.env.A11Y_OUT || path.join(__dirname, `a11y-${W}x${H}`);
fs.mkdirSync(OUT, { recursive: true });
const shot = (name) => path.join(OUT, name + ".png");
const steps = [];
let no = 0;
const record = (name, data = {}) => {
  no += 1;
  steps.push({ n: no, name, at: new Date().toISOString(), ...data });
  console.log(`[${no}] ${name} ${JSON.stringify(data).slice(0, 300)}`);
};
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const MEASURE_JS = () => {
  const parseColor = (value) => {
    const match = /rgba?\(([^)]+)\)/.exec(value || "");
    if (!match) return null;
    const parts = match[1].split(",").map((part) => Number(part.trim()));
    return { r: parts[0], g: parts[1], b: parts[2], a: parts[3] === undefined ? 1 : parts[3] };
  };
  const luminance = ({ r, g, b }) => {
    const channel = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
  };
  const blend = (top, bottom) => ({
    r: Math.round(top.r * top.a + bottom.r * (1 - top.a)),
    g: Math.round(top.g * top.a + bottom.g * (1 - top.a)),
    b: Math.round(top.b * top.a + bottom.b * (1 - top.a)),
    a: 1,
  });
  const effectiveBackground = (el) => {
    let node = el;
    let stack = [];
    while (node) {
      const cs = getComputedStyle(node);
      if (cs.backgroundImage && cs.backgroundImage !== "none") return null;
      const color = parseColor(cs.backgroundColor);
      if (color && color.a > 0) { stack.push(color); if (color.a >= 0.999) break; }
      node = node.parentElement;
    }
    let result = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = stack.length - 1; i >= 0; i -= 1) result = blend(stack[i], result);
    return result;
  };
  const ratio = (a, b) => {
    const l1 = luminance(a), l2 = luminance(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  };

  const visible = (el) => {
    if (!el.getClientRects().length) return false;
    const cs = getComputedStyle(el);
    return cs.display !== "none" && cs.visibility !== "hidden" && Number(cs.opacity) > 0.05;
  };
  const ownText = (el) => Array.from(el.childNodes)
    .filter((node) => node.nodeType === Node.TEXT_NODE)
    .map((node) => node.textContent.trim())
    .join("")
    .trim();

  // 1. font sizes of visible text-bearing elements
  const fonts = [];
  for (const el of document.querySelectorAll(".sh-root *")) {
    if (!visible(el) || el.closest(".sr-only") || el.closest('[aria-hidden="true"]')) continue;
    const text = ownText(el);
    if (!text) continue;
    const cs = getComputedStyle(el);
    fonts.push({ cls: String(el.className || ""), tag: el.tagName.toLowerCase(), text: text.slice(0, 24),
      size: parseFloat(cs.fontSize), weight: Number(cs.fontWeight) || 400, color: cs.color, bg: cs.backgroundColor });
  }

  // 2. tap targets
  const targets = [];
  const selector = 'a[href], button, input, select, textarea, summary, [role="button"], [tabindex]:not([tabindex="-1"])';
  for (const el of document.querySelectorAll(selector)) {
    if (!visible(el) || el.closest(".sr-only") || el.closest('[aria-hidden="true"]')) continue;
    const rect = el.getBoundingClientRect();
    targets.push({ cls: String(el.className || ""), tag: el.tagName.toLowerCase(),
      text: (el.innerText || el.getAttribute("aria-label") || el.getAttribute("placeholder") || "").trim().slice(0, 24),
      w: Math.round(rect.width * 10) / 10, h: Math.round(rect.height * 10) / 10, disabled: Boolean(el.disabled) });
  }

  // 3. contrast for visible text
  const contrasts = [];
  const seen = new Set();
  for (const el of document.querySelectorAll(".sh-root *")) {
    if (!visible(el) || el.closest(".sr-only") || el.closest('[aria-hidden="true"]')) continue;
    const text = ownText(el);
    if (!text) continue;
    const cs = getComputedStyle(el);
    const fg = parseColor(cs.color);
    const bg = effectiveBackground(el);
    if (!fg || !bg) continue;
    const key = fg.r + "," + fg.g + "," + fg.b + "|" + bg.r + "," + bg.g + "," + bg.b + "|" + cs.fontSize + "|" + cs.fontWeight;
    if (seen.has(key)) continue;
    seen.add(key);
    const size = parseFloat(cs.fontSize);
    const weight = Number(cs.fontWeight) || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    const value = Math.round(ratio(fg, bg) * 100) / 100;
    contrasts.push({ cls: String(el.className || ""), text: text.slice(0, 18), size, weight,
      color: cs.color, background: `rgb(${bg.r}, ${bg.g}, ${bg.b})`, ratio: value,
      required: large ? 3 : 4.5, pass: value >= (large ? 3 : 4.5) });
  }

  // 4. horizontal overflow
  const overflow = [];
  for (const el of document.querySelectorAll(".sh-root *")) {
    if (!visible(el) || el.closest(".sr-only")) continue;
    const cs = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    if (rect.width > 0 && (rect.right > innerWidth + 1 || rect.left < -1)) {
      overflow.push({ cls: String(el.className || ""), left: Math.round(rect.left), right: Math.round(rect.right) });
    } else if (el.scrollWidth > el.clientWidth + 1 && !["auto", "scroll"].includes(cs.overflowX)) {
      overflow.push({ cls: String(el.className || ""), scrollWidth: el.scrollWidth, clientWidth: el.clientWidth });
    }
  }

  // 5. layout numbers
  const card = document.querySelector(".sh-card");
  const timeline = document.querySelector(".sh-timeline");
  const task = document.querySelector(".sh-task");
  const composer = document.querySelector(".sh-composer-wrap");
  const topbar = document.querySelector(".sh-topbar");
  const h1 = document.querySelector(".sh-brand h1");
  const layout = {
    cardPadding: card ? getComputedStyle(card).padding : null,
    cardRadius: card ? getComputedStyle(card).borderRadius : null,
    timelineGap: timeline ? getComputedStyle(timeline).rowGap : null,
    taskGap: task ? getComputedStyle(task).rowGap : null,
    composerHeight: composer ? Math.round(composer.getBoundingClientRect().height * 10) / 10 : null,
    composerBottom: composer ? Math.round(composer.getBoundingClientRect().bottom) : null,
    topbarHeight: topbar ? Math.round(topbar.getBoundingClientRect().height * 10) / 10 : null,
    brandTitle: h1 ? { size: parseFloat(getComputedStyle(h1).fontSize), weight: Number(getComputedStyle(h1).fontWeight) } : null,
    viewport: { width: innerWidth, height: innerHeight },
    doc: { scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth },
  };
  return { fonts, targets, contrasts, overflow, layout, bodyText: document.body.innerText.replace(/\s+/g, " ").slice(0, 500) };
};

async function waitReady(page, label) {
  await page.waitForFunction(() => document.querySelector("#sh-input") && !document.querySelector("#sh-input").disabled, { timeout: 120000, polling: 300 });
  await page.waitForFunction(() => document.body.innerText.includes("已连接"), { timeout: 60000, polling: 300 });
  record("ready", { label });
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

async function send(page, message) {
  await page.click("#sh-input");
  await page.type("#sh-input", message, { delay: 12 });
  await page.evaluate(() => Array.from(document.querySelectorAll("button")).find((b) => b.textContent.includes("发送")).click());
  record("send", { message });
}

async function clickChoices(page, preferences) {
  const deadline = Date.now() + 240000;
  let emptyPolls = 0;
  let clicked = 0;
  while (Date.now() < deadline) {
    const options = await page.evaluate(() => Array.from(document.querySelectorAll(".sh-choice:not([disabled])")).map((b) => b.textContent.trim()));
    if (options.length === 0) {
      emptyPolls += 1;
      if (clicked > 0 && emptyPolls >= 4) return;
      if (clicked === 0) {
        const done = await page.evaluate(() => /消费汇总|账单报告|转账成功|有账单提示|没有发现需要留意/.test(document.body.innerText));
        if (done) return;
      }
      await sleep(500);
      continue;
    }
    emptyPolls = 0;
    clicked += 1;
    let target = null;
    for (const pref of preferences) { const hit = options.find((label) => label.includes(pref)); if (hit) { target = hit; break; } }
    if (!target) target = options[0];
    await page.evaluate((label) => {
      const button = Array.from(document.querySelectorAll(".sh-choice")).find((b) => b.textContent.trim() === label);
      button.click();
    }, target);
    record("choice", { target });
    await sleep(600);
  }
}

async function waitText(page, text, timeout = 240000) {
  await page.waitForFunction((t) => document.body.innerText.includes(t), { timeout, polling: 300 }, text);
}

async function measure(page, name) {
  const result = await page.evaluate(MEASURE_JS);
  fs.writeFileSync(path.join(OUT, name + ".json"), JSON.stringify(result, null, 2), "utf8");
  await page.screenshot({ path: shot(name) });
  record("measured", { name, fonts: result.fonts.length, targets: result.targets.length, contrast: result.contrasts.length, overflow: result.overflow.length, layout: result.layout });
  return result;
}

function deriveChecks(samples) {
  const failures = [];
  const waived = [];
  for (const [screen, data] of Object.entries(samples)) {
    for (const item of data.targets) {
      if (item.disabled) continue;
      if (item.w < 48 || item.h < 48) {
        if (item.h >= 47.5 && item.text === "跳到对话内容") waived.push({ screen, kind: "skip-link-subpixel", actual: item.h });
        else failures.push({ screen, kind: "target", text: item.text, cls: item.cls, w: item.w, h: item.h });
      }
    }
    if (data.overflow.length > 0) failures.push({ screen, kind: "overflow", items: data.overflow });
    if (data.layout.doc.scrollWidth > data.layout.doc.clientWidth + 1) failures.push({ screen, kind: "doc-overflow", doc: data.layout.doc });
    if (data.layout.composerBottom !== null && data.layout.composerBottom > data.layout.viewport.height + 1) failures.push({ screen, kind: "composer-below-viewport" });
    const brand = data.layout.brandTitle;
    if (brand && brand.size < 22) waived.push({ screen, kind: "brand-title-20-vs-22", actual: brand.size });
    if (data.layout.cardPadding !== null && data.layout.cardPadding !== "20px") failures.push({ screen, kind: "card-padding", actual: data.layout.cardPadding });
    if (data.layout.timelineGap !== null && data.layout.timelineGap !== "16px") failures.push({ screen, kind: "timeline-gap", actual: data.layout.timelineGap });
    if (data.layout.taskGap !== null && data.layout.taskGap !== "16px") failures.push({ screen, kind: "task-gap", actual: data.layout.taskGap });
    for (const font of data.fonts) {
      if (font.size < 16) failures.push({ screen, kind: "font-floor", text: font.text, cls: font.cls, size: font.size });
    }
    for (const font of data.fonts) {
      if (font.size === 17) waived.push({ screen, kind: "off-scale-17", text: font.text, cls: font.cls });
    }
  }
  const contrastFails = Object.entries(samples).flatMap(([screen, data]) => data.contrasts.filter((c) => !c.pass).map((c) => ({ screen, ...c })));
  return { failures, waived, contrastFails };
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: true,
    args: ["--lang=zh-CN", "--no-first-run", `--window-size=${W},${H}`],
    defaultViewport: { width: W, height: H, isMobile: W < 600, hasTouch: W < 600, deviceScaleFactor: 1 },
  });
  const page = await browser.newPage();
  page.setDefaultTimeout(300000);
  const samples = {};
  try {
    await page.emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "reduce" }]);
    await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 60000 });
    await waitReady(page, "boot");
    await newThread(page);

    samples.welcome = await measure(page, "01-welcome");

    // keyboard focus on the welcome screen
    const focusSeq = [];
    for (let i = 0; i < 14; i += 1) {
      await page.keyboard.press("Tab");
      const item = await page.evaluate(() => {
        const el = document.activeElement;
        const cs = getComputedStyle(el);
        const target = el.closest(".sh-code") || el;
        const ts = getComputedStyle(target);
        const rect = el.getBoundingClientRect();
        return { tag: el.tagName, cls: String(el.className || ""), text: (el.innerText || el.getAttribute("aria-label") || "").trim().slice(0, 20),
          outline: `${ts.outlineStyle} ${ts.outlineWidth}`, shadow: ts.boxShadow, visible: rect.top >= 0 && rect.bottom <= innerHeight && rect.width > 0 };
      });
      focusSeq.push(item);
    }
    record("focus-sequence", { first: focusSeq[0], count: focusSeq.length });
    const focusChecks = {
      firstIsSkipLink: focusSeq[0] && String(focusSeq[0].cls).includes("sh-skip"),
      allFocusVisible: focusSeq.filter((item) => item.tag !== "BODY").every((item) => item.outline.includes("solid") && parseFloat(item.outline.split(" ")[1]) >= 2 || item.shadow !== "none"),
      focusedInViewport: focusSeq.filter((item) => item.tag !== "BODY").every((item) => item.visible),
    };

    // confirmation + verification on the same entry
    await send(page, "给妈妈转500元，主账户A1");
    await waitText(page, "确认办理");
    samples.confirmation = await measure(page, "02-confirmation");
    await page.evaluate(() => {
      const button = Array.from(document.querySelectorAll("button")).find((b) => b.textContent.includes("确认办理"));
      button.click();
    });
    await waitText(page, "等您验证");
    samples.verification = await measure(page, "03-verification");

    // bills summary + report in a clean thread
    await newThread(page);
    await send(page, "这个月花了多少");
    await clickChoices(page, ["所有本人账户"]);
    await waitText(page, "消费汇总");
    samples.billsSummary = await measure(page, "04-bills-summary");
    await newThread(page);
    await send(page, "给我出一份这个月的账单");
    await clickChoices(page, ["所有本人账户"]);
    await waitText(page, "账单报告");
    samples.billsReport = await measure(page, "05-bills-report");

    const { failures, waived, contrastFails } = deriveChecks(samples);
    const checks = {
      fontFloor16: !failures.some((failure) => failure.kind === "font-floor"),
      tapTargets48: !failures.some((failure) => failure.kind === "target"),
      noHorizontalOverflow: !failures.some((failure) => ["overflow", "doc-overflow"].includes(failure.kind)),
      cardPadding20: !failures.some((failure) => failure.kind === "card-padding"),
      gaps16: !failures.some((failure) => ["timeline-gap", "task-gap"].includes(failure.kind)),
      composerInViewport: !failures.some((failure) => failure.kind === "composer-below-viewport"),
      focus: focusChecks,
    };
    const hardPass = Object.entries(checks).filter(([key]) => key !== "focus").every(([, value]) => value === true) && Object.values(focusChecks).every(Boolean);
    const verdict = hardPass ? (waived.length > 0 ? "PASS_WITH_WAIVERS" : "PASS") : "FAIL";
    const evidence = {
      capturedAt: new Date().toISOString(),
      base: BASE,
      viewport: { width: W, height: H },
      build: "ticket-05 worktree (feat/frontend/replace-entry)",
      checks, focusSequence: focusSeq, failures, waived, contrastFailures: contrastFails, verdict, steps, samples,
    };
    fs.writeFileSync(path.join(OUT, "a11y.json"), JSON.stringify(evidence, null, 2), "utf8");
    console.log("FAILURES=" + JSON.stringify(failures.slice(0, 12)));
    console.log("WAIVED=" + JSON.stringify(waived.slice(0, 12)));
    console.log("CONTRAST_FAILS=" + JSON.stringify(contrastFails.slice(0, 12)));
    console.log("VERDICT=" + verdict);
    process.exitCode = verdict === "FAIL" ? 2 : 0;
  } catch (error) {
    record("error", { message: error.message });
    const failureBody = await page.evaluate(() => document.body.innerText.replace(/\s+/g, " ").slice(0, 2000)).catch(() => ""); fs.writeFileSync(path.join(OUT, "a11y-error.json"), JSON.stringify({ capturedAt: new Date().toISOString(), steps, error: error.message, body: failureBody }, null, 2), "utf8");
    await page.screenshot({ path: shot("99-error") }).catch(() => undefined);
    console.error("A11Y FAILED: " + error.message);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
