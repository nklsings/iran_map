const puppeteer = require("puppeteer");
const fs = require("fs");

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Try to find system Chrome on macOS
const CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
];

function findChrome() {
    for (const p of CHROME_PATHS) {
        if (fs.existsSync(p)) return p;
    }
    return null;
}

process.on("unhandledRejection", (reason) => {
    console.error("❌ Unhandled Rejection:", reason?.stack || reason);
    process.exit(1);
});

(async () => {
    let browser;
    try {
        const chromePath = findChrome();
        console.log("🚀 Launching browser...");
        if (chromePath) {
            console.log(`   Using system browser: ${chromePath}`);
        } else {
            console.log("   Using bundled Chromium");
        }

        browser = await puppeteer.launch({
            headless: true,
            executablePath: chromePath || undefined,
            args: [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-extensions",
            ],
            protocolTimeout: 120000,
        });

        console.log("✅ Browser launched");
        const page = await browser.newPage();
        await page.setViewport({ width: 1280, height: 720 });

        console.log("🌐 Navigating to sunagiri.com...");
        await page.goto("https://www.sunagiri.com/en/situation-monitoring", {
            waitUntil: "networkidle2",
            timeout: 60000,
        });

        console.log("⏳ Waiting for page to fully render...");
        await delay(8000);

        fs.writeFileSync("rendered.html", await page.content(), "utf8");
        await page.screenshot({ path: "sunagiri.png", fullPage: true });

        console.log("✅ Saved rendered.html and sunagiri.png");
    } catch (err) {
        console.error("❌ Scrape failed:", err?.stack || err);
        process.exit(1);
    } finally {
        if (browser) {
            try {
                await browser.close();
            } catch (e) {
                // ignore close errors
            }
        }
    }
})();
