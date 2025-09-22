// modules/scrapers/homegate-scraper.js
// Rich PDP extractor with stealth + gentle pacing

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');

puppeteer.use(StealthPlugin());

// ---- Helpers ----
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const jitter = (min = 900, max = 1800) =>
  Math.floor(Math.random() * (max - min + 1)) + min;

// Trim "window.__INITIAL_STATE__ = {...}" → "{...}"
function stripInitialState(raw) {
  if (!raw) return null;
  let s = raw.trim();
  // common prefixes
  s = s.replace(/^window\.__INITIAL_STATE__\s*=\s*/, '');
  s = s.replace(/^window\[["']__INITIAL_STATE__["']\]\s*=\s*/, '');
  // sometimes there's a trailing semicolon
  if (s.endsWith(';')) s = s.slice(0, -1);
  return s;
}

function extractListingFromState(state) {
  try {
    const node = state?.listing?.listing;
    if (!node) return null;

    const title =
      node?.localization?.de?.text?.title ||
      node?.localization?.en?.text?.title ||
      '';

    const currency = node?.prices?.currency || 'CHF';
    const gross = node?.prices?.rent?.gross ?? null;

    const rooms = node?.characteristics?.numberOfRooms ?? null;

    const street = node?.address?.street || '';
    const postalCode = node?.address?.postalCode || '';
    const region = node?.address?.region || node?.address?.locality || '';
    const location = [street, postalCode, region].filter(Boolean).join(', ');

    // Build a nice price string like "CHF 3300"
    const price = gross != null ? `${currency} ${gross}` : null;

    return { title, price, rooms, location };
  } catch {
    return null;
  }
}

async function extractFromPDP(page, url) {
  // Look for the inline script that contains __INITIAL_STATE__
  const scriptTxt = await page.evaluate(() => {
    const nodes = Array.from(document.querySelectorAll('script'));
    const node = nodes.find(s => s.textContent && s.textContent.includes('__INITIAL_STATE__'));
    return node ? node.textContent : '';
  });

  if (!scriptTxt) return null;

  const jsonTxt = stripInitialState(scriptTxt);
  if (!jsonTxt) return null;

  try {
    const state = JSON.parse(jsonTxt);
    const data = extractListingFromState(state);
    if (!data) return null;
    return {
      url,
      title: data.title || null,
      price: data.price || null,
      location: data.location || null,
      rooms: data.rooms ?? null
    };
  } catch {
    return null;
  }
}

async function scrapePDPs(urls) {
  // Prefer real Chrome channel to reduce fingerprinting differences
  const launchOptions = {
    headless: true,
    // You can set CHANNEL via env if you want a specific one:
    // e.g. set CHANNEL=chrome or CHANNEL=msedge
    channel: process.env.CHANNEL || 'chrome',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
    ],
  };

  const browser = await puppeteer.launch(launchOptions);
  const page = await browser.newPage();

  // Light fingerprint hygiene
  await page.setExtraHTTPHeaders({
    'Accept-Language': 'de-CH,de;q=0.9,en;q=0.8',
  });
  await page.setViewport({ width: 1440, height: 900 });

  // Block heavy/tracky resources; HTML is enough for __INITIAL_STATE__
  await page.setRequestInterception(true);
  page.on('request', (req) => {
    const type = req.resourceType();
    if (['image', 'font', 'media', 'stylesheet', 'other'].includes(type)) {
      req.abort();
    } else {
      req.continue();
    }
  });

  // Warm-up: hit homepage (keeps cookies/session realistic)
  try {
    await page.goto('https://www.homegate.ch/', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await sleep(1200 + jitter());
  } catch {}

  const results = [];

  for (let i = 0; i < urls.length; i++) {
    const url = urls[i];
    try {
      console.error(`🔎 Visiting PDP: ${url}`);
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

      // Short, human-ish pause before reading
      await sleep(jitter());
      if (Math.random() < 0.12) await sleep(2500 + jitter());

      const rich = await extractFromPDP(page, url);

      if (rich) {
        results.push(rich);
      } else {
        // graceful fallback to title only
        let title = null;
        try { title = await page.title(); } catch {}
        results.push({ url, title, price: null, rooms: null, location: null });
      }
    } catch (err) {
      console.error(`❌ Failed ${url}: ${err.message}`);
      results.push({ url, title: null, price: null, rooms: null, location: null });
    }
  }

  await browser.close();
  return results;
}

// stdin → URLs → stdout JSON
process.stdin.setEncoding('utf8');
let input = '';
process.stdin.on('data', chunk => (input += chunk));
process.stdin.on('end', async () => {
  try {
    const urls = JSON.parse(input || '[]');
    const data = await scrapePDPs(urls);
    process.stdout.write(JSON.stringify(data));
  } catch (e) {
    // In case of catastrophic failure, still output a JSON array to not break Python
    console.error('Fatal error:', e?.message || e);
    process.stdout.write('[]');
  }
});
