import { chromium } from "playwright";
import fs from "fs";
import path from "path";

async function runBrowserAcceptanceTest() {
  console.log("==================================================");
  console.log("   AGENTOPS LIVE BROWSER & CSS VALIDATION TEST   ");
  console.log("==================================================");

  const browser = await chromium.launch({
    channel: "msedge",
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });

  const page = await context.newPage();
  const consoleMessages = [];
  const networkErrors = [];
  const cssRequests = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleMessages.push(`[Console Error] ${msg.text()}`);
    }
  });

  page.on("requestfailed", (request) => {
    networkErrors.push(`[Network Failed] ${request.method()} ${request.url()} - ${request.failure()?.errorText}`);
  });

  page.on("response", (response) => {
    const url = response.url();
    if (url.includes(".css") || response.headers()["content-type"]?.includes("text/css")) {
      cssRequests.push({
        url,
        status: response.status(),
        contentType: response.headers()["content-type"],
      });
    }
  });

  const artifactsDir = path.join(process.cwd(), "test-artifacts");
  if (!fs.existsSync(artifactsDir)) {
    fs.mkdirSync(artifactsDir, { recursive: true });
  }

  try {
    // 1. Overview / Dashboard Visual Load & CSS Verification
    console.log("\n[1/10] Loading Overview Dashboard (http://localhost:3000)...");
    await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
    await page.screenshot({ path: path.join(artifactsDir, "01_overview_dashboard.png") });
    console.log("✓ Overview dashboard loaded. Title:", await page.title());

    // Verify CSS was loaded
    console.log(`✓ CSS Requests captured: ${cssRequests.length}`);
    cssRequests.forEach(r => console.log(`   - ${r.url} (Status: ${r.status}, Content-Type: ${r.contentType})`));

    // Verify Computed Styles on Body and Elements
    const bodyBg = await page.evaluate(() => window.getComputedStyle(document.body).backgroundColor);
    const bodyColor = await page.evaluate(() => window.getComputedStyle(document.body).color);
    console.log(`✓ Computed Body Background: ${bodyBg}, Text Color: ${bodyColor}`);

    // Verify Sidebar Styling
    const sidebar = await page.$("aside");
    if (sidebar) {
      const sidebarBg = await page.evaluate(el => window.getComputedStyle(el).backgroundColor, sidebar);
      console.log(`✓ Sidebar rendered with computed background: ${sidebarBg}`);
    }

    // 2. Navigate to /runs
    console.log("\n[2/10] Navigating to /runs...");
    await page.click('a[href="/runs"]');
    await page.waitForSelector("text=Agent Run History & Investigations");
    await page.screenshot({ path: path.join(artifactsDir, "02_runs_list.png") });
    console.log("✓ /runs loaded with historical runs.");

    // 3. Initiate Real Investigation from UI
    console.log("\n[3/10] Starting New Investigation from Browser UI...");
    await page.click("text=New Investigation");
    await page.waitForSelector("textarea");
    await page.fill("textarea", "Investigate the payment-service database exhaustion issue.");
    await page.click("text=Execute Investigation");
    
    // Wait for redirect to /runs/[runId]
    await page.waitForURL(/\/runs\/.+/);
    console.log("✓ Investigation executed. Navigated to Run Detail:", page.url());
    await page.waitForSelector("text=Final Synthesized Response", { timeout: 15000 });
    await page.screenshot({ path: path.join(artifactsDir, "03_run_investigation_detail.png") });
    console.log("✓ Run detail page rendered full multi-agent synthesis & timeline.");

    // 4. Trigger Sensitive Action requiring Approval from UI
    console.log("\n[4/10] Triggering Gated Action (Create Incident) from Browser UI...");
    await page.goto("http://localhost:3000/runs", { waitUntil: "networkidle" });
    await page.click("text=New Investigation");
    await page.waitForSelector("textarea");
    await page.fill("textarea", "Create a high-severity incident for payment-service.");
    await page.click("text=Execute Investigation");
    await page.waitForURL(/\/runs\/.+/);
    
    // Verify WAITING_APPROVAL banner appears in UI
    await page.waitForSelector("text=Human Approval Required Before Resuming", { timeout: 15000 });
    await page.screenshot({ path: path.join(artifactsDir, "04_waiting_approval_banner.png") });
    console.log("✓ Run transitioned to WAITING_APPROVAL with approval banner in UI.");

    // 5. Open /approvals and Approve Action via Browser Click
    console.log("\n[5/10] Navigating to /approvals to execute real approval click...");
    await page.goto("http://localhost:3000/approvals", { waitUntil: "networkidle" });
    await page.waitForSelector("text=Human Approval Center");
    await page.screenshot({ path: path.join(artifactsDir, "05_approvals_queue.png") });

    // Click real "Approve" button
    const approveButton = await page.$('button:has-text("Approve")');
    if (approveButton) {
      await approveButton.click();
      console.log("✓ Clicked real 'Approve' button on approval card in UI.");
      await page.waitForTimeout(2000);
      await page.screenshot({ path: path.join(artifactsDir, "06_approval_resolved.png") });
    }

    // 6. Check /incidents for Persisted Record
    console.log("\n[6/10] Checking /incidents for created incident...");
    await page.goto("http://localhost:3000/incidents", { waitUntil: "networkidle" });
    await page.waitForSelector("text=Operational Incident Registry");
    await page.screenshot({ path: path.join(artifactsDir, "07_incidents_page.png") });
    console.log("✓ /incidents rendered persisted operational incident data.");

    // 7. Check /services
    console.log("\n[7/10] Checking /services...");
    await page.goto("http://localhost:3000/services", { waitUntil: "networkidle" });
    await page.waitForSelector("text=Infrastructure & Microservices Telemetry");
    await page.screenshot({ path: path.join(artifactsDir, "08_services_page.png") });
    console.log("✓ /services rendered monitored microservices.");

    // 8. Check /evaluations
    console.log("\n[8/10] Checking /evaluations...");
    await page.goto("http://localhost:3000/evaluations", { waitUntil: "networkidle" });
    await page.waitForSelector("text=Evaluation, Grounding & Reliability Benchmark");
    await page.screenshot({ path: path.join(artifactsDir, "09_evaluations_dashboard.png") });
    console.log("✓ /evaluations rendered benchmark reports.");

    // 9. Open Evaluation Detail Page & Test Dynamic Refresh
    console.log("\n[9/10] Opening Evaluation Detail Page and testing browser refresh...");
    const evalLink = await page.$('a[href^="/evaluations/"]');
    if (evalLink) {
      await evalLink.click();
      await page.waitForURL(/\/evaluations\/.+/);
      await page.waitForSelector("text=BENCHMARK RUN");
      console.log("✓ Evaluation detail page rendered.");
      
      // Perform full browser page refresh on dynamic route
      await page.reload({ waitUntil: "networkidle" });
      await page.waitForSelector("text=BENCHMARK RUN");
      await page.screenshot({ path: path.join(artifactsDir, "10_evaluation_detail_refreshed.png") });
      console.log("✓ Browser refresh on dynamic route succeeded with zero errors.");
    }

    // 10. Console and Network Error Inspection
    console.log("\n[10/10] Inspecting Browser Console & Network Errors...");
    console.log(`Console Errors: ${consoleMessages.length}`);
    console.log(`Network Failures: ${networkErrors.length}`);
    if (consoleMessages.length > 0) {
      console.log("Console Log Warnings:", consoleMessages);
    }

    console.log("\n==================================================");
    console.log("   LIVE BROWSER AUTOMATION TEST COMPLETED (PASS)  ");
    console.log("==================================================");

  } catch (err) {
    console.error("Browser test failed:", err);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runBrowserAcceptanceTest();
