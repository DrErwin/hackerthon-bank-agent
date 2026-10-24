const puppeteer = require("puppeteer-core");
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
(async () => {
  const browser = await puppeteer.launch({ executablePath: EDGE, headless: true, args: ["--lang=zh-CN"], defaultViewport: { width: 1280, height: 900 } });
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:5173/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForFunction(() => document.querySelector("#sh-input") && !document.querySelector("#sh-input").disabled, { timeout: 120000 });
  await new Promise((r) => setTimeout(r, 1000));
  const data = await page.evaluate(async () => {
    const get = async (url) => (await (await fetch(url)).json());
    const threads = await get("/api/v1/threads?limit=100");
    const tasks = await get("/api/v1/tasks?limit=100");
    const pending = await get("/api/v1/tasks?recovery_required=true&limit=100");
    return {
      threads: (threads.data?.items || []).map((t) => ({ id: t.thread_id, title: t.title, updated: t.updated_at })),
      tasks: (tasks.data?.items || []).map((t) => ({ id: t.task_id, thread: t.thread_id, status: t.status, module: t.module, recovery: t.recovery_required, actions: t.allowed_actions, message: (t.message || "").slice(0, 60) })),
      pending: (pending.data?.items || []).map((t) => ({ id: t.task_id, thread: t.thread_id, status: t.status, actions: t.allowed_actions })),
    };
  });
  console.log(JSON.stringify(data, null, 2));
  await browser.close();
})();
