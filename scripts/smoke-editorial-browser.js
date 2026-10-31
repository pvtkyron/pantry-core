const assert = require('node:assert/strict');
const {before, after, test} = require('node:test');
const {createServer} = require('node:http');
const {readFile} = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');

const root = path.resolve(__dirname, '..');
const types = {'.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.json':'application/json', '.svg':'image/svg+xml', '.png':'image/png', '.jpg':'image/jpeg', '.woff':'font/woff', '.woff2':'font/woff2'};
let server, browser, origin;

before(async () => {
  server = createServer(async (request, response) => {
    try {
      const url = new URL(request.url, 'http://localhost');
      if (url.pathname === '/__editorial_shadow__') {
        response.setHeader('Content-Type', 'text/html; charset=utf-8');
        response.end('<!doctype html><html lang="ja"><title>Shadow fixture</title><body></body></html>');
        return;
      }
      const relative = decodeURIComponent(url.pathname).replace(/^\/+/, '') || 'index.html';
      const file = path.resolve(root, relative);
      if (!file.startsWith(root + path.sep) || relative.split('/').some(part => part.startsWith('.'))) {
        response.writeHead(404).end();return;
      }
      const bytes = await readFile(file);
      response.setHeader('Content-Type', (types[path.extname(file)] || 'application/octet-stream') + '; charset=utf-8');
      response.end(bytes);
    } catch { response.writeHead(404).end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  origin = 'http://127.0.0.1:' + server.address().port;
  browser = await chromium.launch({headless:true, ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ? {executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH} : {})});
});
after(async () => {
  await browser?.close();
  if (server) await new Promise(resolve => server.close(resolve));
});

async function visit(route, action, options={}) {
  const context = await browser.newContext({viewport:{width:1440,height:900}, reducedMotion:'reduce', ...options});
  const page = await context.newPage(), errors=[];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(origin + route);
    await action(page, context);
    assert.deepEqual(errors, [], 'No uncaught browser exceptions');
  } finally { await context.close(); }
}

test('journal remains readable with JavaScript disabled', async () => {
  await visit('/journal.html', async page => {
    assert.equal(await page.locator('.story-row:visible').count(), 4);
    assert.equal(await page.locator('.journal-tools').isVisible(), false);
    await page.locator('.story-row h2 a').first().click();
    assert.equal(await page.locator('.article-body h2').count() > 0, true);
    assert.equal(await page.locator('a.skip[href="#main"]').count(), 1);
  }, {javaScriptEnabled:false});
});

test('journal searches aliases, combines topics, restores its URL and clears empty results', async () => {
  await visit('/journal.html', async page => {
    await page.locator('[data-story-search]').fill('ＧＩＴＨＵＢ source');
    assert.equal(await page.locator('.story-row:visible').count(), 1);
    assert.match(await page.locator('[data-story-count]').innerText(), /^1 \/ 4/);
    await page.reload();
    assert.equal(await page.locator('.story-row:visible').count(), 1);
    assert.equal(await page.locator('[data-story-search]').inputValue(), 'ＧＩＴＨＵＢ source');
    await page.locator('button[data-topic="gaming"]').click();
    assert.equal(await page.locator('[data-story-empty]').isVisible(), true);
    assert.equal(await page.locator('button[data-topic="gaming"]').getAttribute('aria-pressed'), 'true');
    await page.locator('[data-story-empty] [data-story-reset]').click();
    assert.equal(await page.locator('.story-row:visible').count(), 4);
    assert.equal(new URL(page.url()).search, '');
    assert.equal(await page.locator('[data-story-search]').evaluate(n => n === document.activeElement), true);
  });
});

test('global search supports arrows, focus containment, escape and scroll-state restoration', async () => {
  await visit('/journal.html', async page => {
    await page.evaluate(() => document.documentElement.style.overflow='clip');
    const trigger=page.locator('[data-search]').first();await trigger.focus();
    await page.keyboard.press('Control+k');
    const input=page.locator('.search-layer input');
    assert.equal(await input.evaluate(n=>n===document.activeElement), true);
    assert.equal(await page.locator('main').evaluate(n=>n.inert), true);
    await page.keyboard.press('ArrowDown');
    assert.match(await page.evaluate(()=>document.activeElement.textContent), /REV Core/);
    await page.keyboard.press('ArrowDown');
    assert.match(await page.evaluate(()=>document.activeElement.textContent), /REV Studio/);
    await input.fill('github architecture');await input.focus();
    await page.keyboard.press('Shift+Tab');
    assert.match(await page.evaluate(()=>document.activeElement.textContent), /GitHub/);
    await page.keyboard.press('Tab');
    assert.equal(await input.evaluate(n=>n===document.activeElement), true);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('.search-layer').isVisible(), false);
    assert.equal(await trigger.evaluate(n=>n===document.activeElement), true);
    assert.equal(await page.locator('main').evaluate(n=>n.inert), false);
    assert.equal(await page.evaluate(()=>document.documentElement.style.overflow), 'clip');
  });
});

test('mobile navigation closes on Escape and outside click; layouts fit narrow screens', async () => {
  await visit('/journal.html', async page => {
    await page.setViewportSize({width:390,height:844});
    const menu=page.locator('[data-menu]');await menu.click();
    assert.equal(await menu.getAttribute('aria-expanded'), 'true');
    await page.keyboard.press('Escape');
    assert.equal(await menu.getAttribute('aria-expanded'), 'false');
    assert.equal(await menu.evaluate(n=>n===document.activeElement), true);
    await menu.click();await page.locator('.journal-pick p').click();
    assert.equal(await menu.getAttribute('aria-expanded'), 'false');
    for (const width of [320,390,768,1440]) {
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth), true, 'Journal width '+width);
    }
    await page.goto(origin+'/posts/buyer-guide.html');
    for (const width of [320,390,768,1440]) {
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth), true, 'Article width '+width);
    }
  });
});

test('reader preferences persist and sharing reports success or clipboard denial', async () => {
  await visit('/posts/buyer-guide.html', async (page, context) => {
    await page.locator('[data-reader-size="large"]').click();
    await page.goto(origin+'/posts/github-first.html');
    assert.equal(await page.locator('.article-body').evaluate(n=>n.classList.contains('reader-large')), true);
    assert.equal(await page.locator('[data-reader-size="large"]').getAttribute('aria-pressed'), 'true');
    await context.grantPermissions(['clipboard-read','clipboard-write']);
    await page.locator('.article-share').click();
    await page.waitForFunction(()=>document.querySelector('.reader-status').textContent.includes('コピーしました'));
    assert.equal(await page.evaluate(()=>navigator.clipboard.readText()), 'https://pvtkyron.github.io/pantry-core/posts/github-first.html');
    await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw Error('denied')}}}));
    await page.locator('.article-share').click();
    await page.waitForFunction(()=>document.querySelector('.reader-status').textContent.includes('コピーできません'));
    assert.equal(await page.locator('.article-share').isEnabled(), true);
  });
});

test('table of contents follows the article and progress completes before related links', async () => {
  await visit('/posts/buyer-guide.html', async page => {
    const last=page.locator('.toc-links a').last(),anchor=await last.getAttribute('href');
    await last.click();
    await page.waitForFunction(hash=>document.querySelector('.toc-links a[aria-current="location"]')?.getAttribute('href')===hash, anchor);
    assert.equal(new URL(page.url()).hash, anchor);
    await page.locator('.article-body').evaluate(n=>window.scrollTo({top:scrollY+n.getBoundingClientRect().bottom-innerHeight+60,behavior:'instant'}));
    await page.waitForFunction(()=>document.querySelector('.reading-progress').style.transform==='scaleX(1)');
    await page.setViewportSize({width:390,height:844});await page.reload();
    assert.equal(await page.locator('.toc-toggle').getAttribute('aria-expanded'), 'false');
    await page.locator('.toc-toggle').click();
    assert.equal(await page.locator('.toc-links').isVisible(), true);
  });
});

test('Blogfa Shadow DOM has one mount, working TOC, scoped scrolling and keyboard search', async () => {
  await visit('/__editorial_shadow__?rev=posts/buyer-guide', async page => {
    await page.addScriptTag({url:origin+'/assets/rev-editorial.js'});
    const mounted=await page.evaluate(async () => {
      const [html,css]=await Promise.all([fetch('/posts/buyer-guide.html').then(r=>r.text()),fetch('/assets/rev-editorial.css').then(r=>r.text())]);
      const parsed=new DOMParser().parseFromString(html,'text/html');parsed.querySelectorAll('script').forEach(n=>n.remove());
      const host=document.createElement('div');host.id='shadow-fixture';host.style.cssText='position:fixed;inset:0;overflow:auto';
      const shadow=host.attachShadow({mode:'open'}),style=document.createElement('style'),shell=document.createElement('div');
      style.textContent=':host{--paper:#f2ede3;--paper-3:#fffdf8;--ink:#11110f;--muted:#69645c;--line:#cfc5b5;--red:#d63b24;--white:#fffdf8;--max:1280px;--pad:20px;--read:760px;--serif:serif;--sans:sans-serif;--mono:monospace}'+css;
      shell.innerHTML=parsed.body.innerHTML;shadow.append(style,shell);document.body.append(host);
      const options={resolveHref:p=>'?rev='+p.replace(/\.html$/,''),scrollTarget:host};
      return [window.REV_EDITORIAL_MOUNT(shadow,options),window.REV_EDITORIAL_MOUNT(shadow,options)];
    });
    assert.deepEqual(mounted,[true,false]);
    const host=page.locator('#shadow-fixture');
    assert.equal(await host.locator('.article-toolbar').count(),1);
    await host.locator('.toc-links a').last().click();
    await page.waitForFunction(()=>document.querySelector('#shadow-fixture').scrollTop>0);
    assert.equal(await page.evaluate(()=>scrollY),0);
    await host.locator('[data-search]').first().click();
    await page.keyboard.press('ArrowDown');
    assert.match(await host.evaluate(n=>n.shadowRoot.activeElement.textContent),/REV Core/);
    await page.keyboard.press('Escape');
    assert.equal(await host.locator('.search-layer').isVisible(),false);
    assert.equal(await host.evaluate(n=>n.style.overflow),'auto');
  });
});

async function nativeBlog(page, {visualFailure=false, networkFailure=false}={}) {
  await page.route(origin+'/?rev=journal', route=>route.fulfill({contentType:'text/html',body:'<!doctype html><html lang="ja"><title>Native blog</title><body><main id="native-post" aria-hidden="false"><h1>Original native article</h1><input id="native-draft"><button id="native-action">Native action</button></main><aside id="already-hidden" hidden aria-hidden="true">Hidden sidebar</aside></body></html>'}));
  await page.route(/^https:\/\/(?:api\.github\.com|raw\.githubusercontent\.com|cdn\.jsdelivr\.net)\//, async route=>{
    if(networkFailure){await route.fulfill({status:503,body:'Unavailable'});return}
    const url=new URL(route.request().url());
    if(url.pathname.endsWith('/commits/main')){await route.fulfill({json:{sha:'1'.repeat(40)}});return}
    const relative=url.pathname.match(/(?:\/[0-9a-f]{40}\/|\/contents\/)(.+)$/)?.[1];
    if(relative&&['journal.html','assets/rev-editorial.css','assets/rev-editorial.js','assets/gpt-workspace.js'].includes(relative)){
      await route.fulfill({contentType:types[path.extname(relative)],body:await readFile(path.join(root,relative))});return;
    }
    await route.fulfill({status:404,body:'Missing fixture'});
  });
  await page.goto(origin+'/?rev=journal');
  await page.locator('#native-draft').fill('Keep this unsent draft');
  await page.evaluate(fail=>{
    window.originalNative=document.querySelector('#native-post');window.nativeClicks=0;
    document.querySelector('#native-action').addEventListener('click',()=>window.nativeClicks++);
    if(fail){const original=window.getComputedStyle;window.getComputedStyle=function(node,...args){return node.id==='rev-project-host'?{backgroundColor:'transparent'}:original.call(this,node,...args)}}
  },visualFailure);
}

test('Blogfa visual failure keeps the native article, form values and event listeners', async () => {
  await visit('/__editorial_shadow__', async page=>{
    await nativeBlog(page,{visualFailure:true});
    await page.addScriptTag({url:origin+'/assets/blogfa-widget-v3.js'});
    await page.waitForFunction(()=>window.REV_WIDGET_HEALTH?.().status==='rolled-back');
    assert.equal(await page.locator('#native-post').isVisible(),true);
    assert.equal(await page.locator('#native-draft').inputValue(),'Keep this unsent draft');
    assert.equal(await page.evaluate(()=>document.querySelector('#native-post')===window.originalNative),true);
    assert.equal(await page.locator('#rev-project-host').count(),0);
    assert.equal(await page.evaluate(()=>document.documentElement.classList.contains('rev-project-only')),false);
    assert.equal(await page.evaluate(()=>{const e=new KeyboardEvent('keydown',{key:'k',ctrlKey:true,bubbles:true,cancelable:true});document.dispatchEvent(e);return e.defaultPrevented}),false);
    await page.locator('#native-action').click();assert.equal(await page.evaluate(()=>window.nativeClicks),1);
  });
});

test('Blogfa watchdog restores the same native nodes after a healthy host is lost', async () => {
  await visit('/__editorial_shadow__', async page=>{
    await nativeBlog(page);
    await page.addScriptTag({url:origin+'/assets/blogfa-widget-v3.js'});
    await page.waitForFunction(()=>window.REV_WIDGET_HEALTH?.().status==='healthy');
    assert.equal(await page.locator('#native-post').count(),1);
    assert.equal(await page.locator('#native-post').isVisible(),false);
    await page.evaluate(()=>document.querySelector('#rev-project-host').remove());
    await page.waitForFunction(()=>window.REV_WIDGET_HEALTH?.().status==='rolled-back');
    assert.equal(await page.locator('#native-post').isVisible(),true);
    assert.equal(await page.locator('#native-post').getAttribute('aria-hidden'),'false');
    assert.equal(await page.locator('#native-post').evaluate(n=>n.inert),false);
    assert.equal(await page.locator('#already-hidden').isVisible(),false);
    assert.equal(await page.locator('#native-draft').inputValue(),'Keep this unsent draft');
    assert.equal(await page.evaluate(()=>window.__REV_WIDGET_READY__),0);
    assert.equal(await page.evaluate(()=>{const e=new KeyboardEvent('keydown',{key:'k',ctrlKey:true,bubbles:true,cancelable:true});document.dispatchEvent(e);return e.defaultPrevented}),false);
  });
});

test('Blogfa supervisor removes the loading cover when all widget providers fail', async () => {
  await visit('/__editorial_shadow__', async page=>{
    await nativeBlog(page,{networkFailure:true});
    await page.evaluate(()=>window.__REV_RESPONSIVE_RUNTIME__=1);
    await page.addScriptTag({url:origin+'/assets/blogfa-supervisor.js'});
    await page.waitForFunction(()=>window.REV_SYSTEM_HEALTH?.().widget?.status==='failed');
    assert.equal(await page.locator('#rev-project-boot').count(),0);
    assert.equal(await page.locator('#native-post').isVisible(),true);
    assert.equal(await page.locator('#native-draft').inputValue(),'Keep this unsent draft');
  });
});
