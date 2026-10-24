const puppeteer = require("puppeteer-core");
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const TASK = process.argv[2];
(async () => {
  const browser = await puppeteer.launch({ executablePath: EDGE, headless: true, args: ["--lang=zh-CN"], defaultViewport: { width: 1280, height: 900 } });
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:5173/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForFunction(() => document.querySelector("#sh-input") && !document.querySelector("#sh-input").disabled, { timeout: 120000 });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const out = await page.evaluate(async (taskId) => {
    const post = async (url, body) => {
      const res = await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
      return { status: res.status, body: await res.json() };
    };
    const before = await (await fetch("/api/v1/tasks/" + taskId)).json();
    const resumed = await post("/api/v1/tasks/" + taskId + "/resume", { request_id: crypto.randomUUID() });
    await new Promise((r) => setTimeout(r, 500));
    const afterResume = await (await fetch("/api/v1/tasks/" + taskId)).json();
    let cancelled = null;
    if (afterResume.data && ["waiting_approval", "waiting_input", "running", "needs_attention"].includes(afterResume.data.status)) {
      cancelled = await post("/api/v1/tasks/" + taskId + "/cancel", { request_id: crypto.randomUUID() });
      await new Promise((r) => setTimeout(r, 800));
    }
    const after = await (await fetch("/api/v1/tasks/" + taskId)).json();
    return {
      before: { status: before.data?.status, actions: before.data?.allowed_actions, recovery: before.data?.recovery_required, interaction: before.data?.interaction?.kind },
      resumed: { http: resumed.status, status: resumed.body?.data?.status, actions: resumed.body?.data?.allowed_actions, message: resumed.body?.data?.message },
      afterResume: { status: afterResume.data?.status, actions: afterResume.data?.allowed_actions, recovery: afterResume.data?.recovery_required },
      cancelled: cancelled ? { http: cancelled.status, status: cancelled.body?.data?.status } : null,
      after: { status: after.data?.status, actions: after.data?.allowed_actions, recovery: after.data?.recovery_required, message: after.data?.message },
    };
  }, TASK);
  console.log(JSON.stringify(out, null, 2));
  await sleep(300);
  await browser.close();
})();
