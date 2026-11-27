// Capture the website's Rusty Conduit GUI screenshots into site/img/gui/.
//
// The shots come from the GUI's browser dev mode, which serves the real Manage
// Window with the demo data in rusty-conduit-gui/src-tauri/ui/src/lib/mock.ts
// (documentation-only addresses). No real config, vault, or host is touched.
//
//   1. cd rusty-conduit-gui/src-tauri/ui && npm run dev        # leave running
//   2. npm i --prefix /tmp/rcs-pw playwright-core                # once
//   3. NODE_PATH=/tmp/rcs-pw/node_modules node scripts/site-gui-screenshots.cjs
//
// Needs Google Chrome installed. Writes gui-<shot>-<dark|light>.webp.
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

const URL = process.env.GUI_URL || "http://127.0.0.1:5173/";
const OUT = process.argv[2] || path.join(__dirname, "..", "site", "img", "gui");

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const converter = await browser.newPage();

  async function save(page, name) {
    await page.waitForTimeout(600);
    const png = await page.screenshot();
    const webp = await converter.evaluate(async (b64) => {
      const img = new Image();
      img.src = "data:image/png;base64," + b64;
      await img.decode();
      const c = document.createElement("canvas");
      c.width = img.width;
      c.height = img.height;
      c.getContext("2d").drawImage(img, 0, 0);
      return c.toDataURL("image/webp", 0.86).split(",")[1];
    }, png.toString("base64"));
    fs.writeFileSync(path.join(OUT, name + ".webp"), Buffer.from(webp, "base64"));
    console.log("wrote", name + ".webp");
  }

  for (const scheme of ["dark", "light"]) {
    const page = await browser.newPage({
      viewport: { width: 1200, height: 760 },
      deviceScaleFactor: 2,
      colorScheme: scheme,
    });
    page.on("pageerror", (e) => console.error("page error:", e.message));
    await page.goto(URL, { waitUntil: "networkidle" });

    // Auto Switch routing table with a Route Tester result.
    await page.getByPlaceholder("Host, host:port, or URL").fill("wiki.corp.example:443");
    await page.getByRole("button", { name: "Test route" }).last().click();
    await save(page, `gui-routing-${scheme}`);

    // New Proxy wizard, Auto Switch picked.
    await page.getByRole("button", { name: "+ New Proxy" }).click();
    await page.getByText("Auto Switch", { exact: true }).last().click();
    await save(page, `gui-wizard-${scheme}`);
    await page.getByRole("button", { name: "Cancel" }).click();

    // Tunnel with a jump host added (not saved).
    await page.getByRole("button", { name: /^Staging bastion/ }).click();
    await page.getByText("+ Add jump").click();
    const inputs = page.locator("main input:visible");
    await inputs.nth(0).fill("198.51.100.5");
    await inputs.nth(2).fill("demo");
    await inputs.nth(3).fill("Jump host");
    await page.locator("main").getByText("Staging bastion", { exact: true }).last().click();
    await save(page, `gui-tunnel-${scheme}`);
    await page.getByRole("button", { name: "Discard" }).click();

    // Vault: SSH keys and MITM CAs.
    await page.getByText("Vault", { exact: true }).first().click();
    await save(page, `gui-vault-${scheme}`);
    await page.close();
  }
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
