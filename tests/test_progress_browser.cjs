/* Browser smoke against generated, disposable snapshots; no provider or GitHub writes. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');

async function main() {
  const dir = process.argv[2];
  const html = await fs.readFile(path.join(dir, 'initial/index.html'));
  const initial = await fs.readFile(path.join(dir, 'initial/progress.json'));
  const update = JSON.parse(await fs.readFile(path.join(dir, 'updated/progress.json')));
  // Deliberate unsafe-looking data tests rendering as text, independently of export filtering.
  update.current.summary += ' <img src=x onerror=alert(1)>';
  let snapshot = null;
  const server = http.createServer((req, res) => {
    if (req.url === '/') return res.writeHead(200, {'Content-Type':'text/html'}).end(html);
    if (req.url === '/progress.json' && snapshot) {
      return res.writeHead(200, {'Content-Type':'application/json','Cache-Control':'no-store'}).end(snapshot);
    }
    res.writeHead(404).end();
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    const proxy = process.env.TRACKER_BROWSER_PROXY;
    browser = await chromium.launch({executablePath:process.env.CHROME_EXECUTABLE || undefined,
      proxy:proxy ? {server:proxy,bypass:'127.0.0.1,localhost'} : undefined});
    const page = await browser.newPage({viewport:{width:375,height:812},isMobile:true,deviceScaleFactor:2,
      ignoreHTTPSErrors:process.env.TRACKER_TEST_PROXY_CA === '1'});
    const url = 'http://127.0.0.1:' + server.address().port + '/';
    let navigations = 0;
    page.on('framenavigated', () => { navigations++; });
    await page.goto(url);
    await page.waitForFunction(() => document.querySelector('#notice').textContent.includes('snapshot unavailable'));
    assert.equal(await page.locator('#snapshot').isVisible(), false);
    snapshot = initial;
    await page.waitForFunction(() => document.querySelector('#timeline').textContent.includes('Retrieval is due.'));
    const visitorStart = performance.now();
    assert.equal(await page.locator('#sample').isVisible(), true);
    assert.match(await page.locator('#work').textContent(), /My contribution.*verify that boundary/);
    const evidence = page.getByRole('link', {name: /Inspect evidence for Ask Guru/});
    assert.equal(await evidence.isVisible(), true);
    const destination = await evidence.getAttribute('href');
    assert.match(destination, /\/commit\/[0-9a-f]{40}$/);
    const visitorMs = Math.round(performance.now() - visitorStart);
    const started = performance.now();
    snapshot = JSON.stringify(update);
    await page.waitForFunction(() => document.querySelector('#timeline').textContent.includes('criteria demonstrated'));
    const delayMs = Math.round(performance.now() - started);
    assert.equal(navigations, 1);
    assert.equal(await page.locator('#evidence img').count(), 0);
    assert.match(await page.locator('#evidence').textContent(), /<img src=x/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    if (process.env.TRACKER_SCREENSHOT) {
      snapshot = await fs.readFile(path.join(dir, 'updated/progress.json'));
      await page.waitForFunction(() => !document.querySelector('#evidence').textContent.includes('<img'));
      await page.screenshot({path:process.env.TRACKER_SCREENSHOT,fullPage:true});
    }
    snapshot = null;
    await page.waitForFunction(() => document.querySelector('#notice').textContent.includes('last published snapshot'));
    assert.match(await page.locator('#evidence').textContent(), /No curriculum pass/);
    const refreshNavigations = navigations;
    const [external] = await Promise.all([
      page.waitForNavigation({waitUntil:'commit',timeout:15000}), evidence.click(),
    ]);
    assert.equal(external.url(), destination);
    assert.equal(external.status(), 200);
    console.log(JSON.stringify({browser:browser.version(), signedOut:true, width:375,
      noHorizontalOverflow:true, unavailableClear:true, lastSnapshotRetained:true,
      exportedTextEscaped:true, navigationsBeforeEvidenceClick:refreshNavigations, updateToDisplayMs:delayMs,
      selectedWorkLocatedMs:visitorMs, evidenceStatus:external.status()}));
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
