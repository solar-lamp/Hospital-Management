// End-to-end check of the static (stlite) build in a real browser.
// Usage: node scripts/browser_smoke.mjs http://localhost:8000/ out_dir
import { chromium } from "playwright";
import fs from "node:fs";

const [url, outDir = "smoke"] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
const problems = [];
page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (["error", "warning"].includes(m.type())) console.log(`console ${m.type()}:`, m.text()); });

const shot = (name) => page.screenshot({ path: `${outDir}/${name}.png`, fullPage: true });
const login = async () => {
  await page.locator('input[type="password"]').waitFor({ timeout: 300_000 });
  await page.locator('input[type="text"]').first().fill("admin");
  await page.locator('input[type="password"]').fill("Admin@123");
  await page.getByRole("button", { name: "Log in" }).click();
  await page.getByRole("heading", { name: "Dashboard" }).waitFor({ timeout: 120_000 });
  await page.getByText("Registered patients").waitFor({ timeout: 60_000 });
};
const exceptions = async (where) => {
  const n = await page.locator('[data-testid="stException"]').count();
  if (n) problems.push(`${n} Python exception(s) on ${where}`);
};

console.time("first load + seed + login");
await page.goto(url);
try {
  await login();
} catch (err) {
  await shot("01_failed");
  console.error("Page text at failure:\n" + (await page.locator("body").innerText()).slice(0, 3000));
  throw err;
}
console.timeEnd("first load + seed + login");
await page.waitForTimeout(3000);
await shot("02_dashboard");
await exceptions("Dashboard");

for (const name of ["Patients", "Appointments", "Admissions & Beds", "Pharmacy & Medicines",
                    "Billing & Payments", "Reports", "User Management"]) {
  await page.getByRole("link", { name }).first().click();
  await page.getByRole("heading", { name }).first().waitFor({ timeout: 60_000 });
  await page.waitForTimeout(2500);
  await exceptions(name);
  await shot("03_" + name.replace(/\W+/g, "_"));
}

// Register a patient, reload, and check it persisted in IndexedDB.
await page.getByRole("link", { name: "Patients" }).first().click();
await page.getByRole("tab", { name: "Register" }).click();
await page.getByLabel("Full name *").fill("Persistence Check Patient");
await page.getByRole("button", { name: "Register patient" }).click();
await page.getByText("Registered Persistence Check Patient").waitFor({ timeout: 60_000 });
await page.waitForTimeout(3000); // let the IndexedDB sync finish
await page.goto(url);
await login();
await page.getByRole("link", { name: "Patients" }).first().click();
await page.getByLabel("Search by code, name or phone").fill("Persistence Check");
await page.keyboard.press("Enter");
await page.waitForTimeout(3000);
await shot("04_persisted");
if (!(await page.getByText("1 patient(s)").count())) problems.push("patient did not persist after reload");

await browser.close();
if (problems.length) {
  console.error("SMOKE TEST FAILED:\n" + problems.join("\n"));
  process.exit(1);
}
console.log("Browser smoke test passed.");
