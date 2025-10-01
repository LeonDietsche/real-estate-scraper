// modules/scrapers/homegate-scraper.js
// Rich PDP extractor with stealth + polite pacing & block backoff

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

// ---- Env knobs (match Python defaults) ----
const asFloat = (name, def) => {
  const v = process.env[name];
  const n = v ? Number(v) : def;
  return Number.isFinite(n) ? n : def;
};

const CRAWL_MIN_DELAY_SEC = asFloat('CRAWL_MIN_DELAY_SEC', 2.0);     // base delay between actions
const CRAWL_JITTER_SEC    = asFloat('CRAWL_JITTER_SEC', 2.0);        // extra 0..JITTER
const BACKOFF_MIN_SEC     = asFloat('CRAWL_BACKOFF_MIN', 10);        // on block
const BACKOFF_MAX_SEC     = asFloat('CRAWL_BACKOFF_MAX', 300);
const ATTEMPTS_PER_PDP    = Math.max(1, Number(process.env.CRAWL_PDP_ATTEMPTS ?? 2));

// ---- Helpers ----
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rand = (a, b) => a + Math.random() * (b - a);
const politePause = async () =>
  sleep((CRAWL_MIN_DELAY_SEC + Math.random() * CRAWL_JITTER_SEC) * 1000);

const jitter = (min = 900, max = 1800) => Math.floor(rand(min, max));
const backoff = async () =>
  sleep(rand(BACKOFF_MIN_SEC * 1000, BACKOFF_MAX_SEC * 1000));

function looksBlocked(title, url, htmlSample = '') {
  const t = (title || '').toLowerCase();
  const u = (url || '').toLowerCase();
  const h = (htmlSample || '').toLowerCase();
  return (
    t.includes('cloudflare') ||
    t.includes('access denied') ||
    u.includes('challenge') ||
    u.includes('blocked') ||
    h.includes('cloudflare') ||
    h.includes('attention required')
  );
}

// Trim "window.__INITIAL_STATE__ = {...}" → "{...}"
function stripInitialState(raw) {
  if (!raw) return null;
  let s = raw.trim();
  s = s.replace(/^window\.__INITIAL_STATE__\s*=\s*/, '');
  s = s.replace(/^window\[["']__INITIAL_STATE__["']\]\s*=\s*/, '');
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

    const price = gross != null ? `${currency} ${gross}` : null;

    return { title, price, rooms, location };
  } catch {
    return null;
  }
}

async function extractFromPDP(page, url) {
  const scriptTxt = await page.evaluate(() => {
    const nodes = Array.from(document.querySelectorAll('script'));
    const node = nodes.find(
      (s) => s.textContent && s.textContent.includes('__INITIAL_STATE__')
    );
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
      rooms: data.rooms ?? null,
    };
  } catch {
    return null;
  }
}

async function scrapePDPs(urls) {
  const launchOptions = {
    headless: true,
    // If you really want the real Chrome channel:
    // channel: process.env.CHANNEL || 'chrome',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
    ],
  };

  const browser = await puppeteer.launch(launchOptions);
  const page = await browser.newPage();

  // Realistic headers/viewport
  await page.setExtraHTTPHeaders({
    'Accept-Language': 'de-CH,de;q=0.9,en;q=0.8',
  });
  await page.setViewport({ width: 1440, height: 900 });

  // Keep traffic light; __INITIAL_STATE__ lives in HTML, so we can block heavy assets
  await page.setRequestInterception(true);
  page.on('request', (req) => {
    const type = req.resourceType();
    if (['image', 'font', 'media', 'stylesheet', 'other'].includes(type)) {
      req.abort();
    } else {
      req.continue();
    }
  });

  // Warm-up hit (gives us cookies/session)
  try {
    await politePause();
    await page.goto('https://www.homegate.ch/', {
      waitUntil: 'domcontentloaded',
      timeout: 30000,
    });
    await sleep(600 + jitter());
  } catch {}

  const results = [];

  for (const url of urls) {
    let out = { url, title: null, price: null, rooms: null, location: null };

    for (let attempt = 1; attempt <= ATTEMPTS_PER_PDP; attempt++) {
      try {
        console.error(`🔎 Visiting PDP [${attempt}/${ATTEMPTS_PER_PDP}]: ${url}`);

        await politePause();
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

        // Short, human-ish pause before reading
        await sleep(jitter());
        if (Math.random() < 0.12) await sleep(2500 + jitter());

        const title = await page.title().catch(() => '');
        const htmlSample = await page
          .$eval('body', (b) => (b && b.innerText ? b.innerText.slice(0, 800) : ''))
          .catch(() => '');

        if (looksBlocked(title, page.url(), htmlSample)) {
          console.error('⚠️  Block/Cloudflare detected, backing off...');
          await backoff();
          if (attempt < ATTEMPTS_PER_PDP) continue;
          break;
        }

        const rich = await extractFromPDP(page, url);
        if (rich) {
          out = rich;
        } else {
          out.title = title || null; // graceful fallback
        }
        break; // success for this URL
      } catch (err) {
        console.error(`❌ Error for ${url}: ${err?.message || err}`);
        // exponential-ish pause before next attempt
        const pause = 800 * Math.pow(2, attempt - 1) + jitter(400, 900);
        await sleep(pause);
        if (attempt === ATTEMPTS_PER_PDP) {
          // give up (keep fallback out)
        }
      }
    }

    results.push(out);
  }

  await browser.close();
  return results;
}

// stdin → URLs → stdout JSON
process.stdin.setEncoding('utf8');
let input = '';
process.stdin.on('data', (chunk) => (input += chunk));
process.stdin.on('end', async () => {
  try {
    const urls = JSON.parse(input || '[]');
    const data = await scrapePDPs(urls);
    process.stdout.write(JSON.stringify(data));
  } catch (e) {
    console.error('Fatal error:', e?.message || e);
    process.stdout.write('[]');
  }
});
