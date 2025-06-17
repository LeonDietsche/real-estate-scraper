// homegate-scraper.js
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');

puppeteer.use(StealthPlugin());

async function scrapeTitles(urls) {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  const results = [];

  for (const url of urls) {
    try {
      console.error(`🔎 Visiting: ${url}`); // log to stderr
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForSelector('title');
      const title = await page.title();
      results.push({ url, title });
    } catch (err) {
      console.error(`❌ Failed ${url}: ${err.message}`);
      results.push({ url, title: null });
    }
  }

  await browser.close();

  // ONLY data to stdout
  process.stdout.write(JSON.stringify(results));
}

process.stdin.setEncoding('utf8');
let input = '';
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  const urls = JSON.parse(input);
  scrapeTitles(urls);
});
