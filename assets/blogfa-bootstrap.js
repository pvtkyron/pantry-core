(()=>{
if(window.__REV_BOOTSTRAP__)return;
window.__REV_BOOTSTRAP__=1;
window.REV_BOOTSTRAP_VERSION='2026.08.20.1';
document.documentElement.lang='ja';
const OWNER='pvtkyron',REPO='Live2dOnWebv1.0.0',TG='https://t.me/project_rev',SCHEMA='https://schema.org';
const ROOT=document.getElementById('rev-root'),BLOG=(window.REV_BLOG_URL||location.origin+location.pathname).replace(/\/$/,'');
const NATIVE=window.REV_NATIVE_MODE||/^\/(post|archive|posts|category|tag|author)(?:\/|$)/i.test(location.pathname);
if(NATIVE){document.documentElement.classList.add('rev-native-mode');return;}
if(!ROOT)return;
let BASE='https://cdn.jsdelivr.net/gh/'+OWNER+'/'+REPO+'@master/';
const resolveBase=async()=>{
    try{
        const r=await fetch('https://api.github.com/repos/'+OWNER+'/'+REPO+'/commits/master',{cache:'no-store',headers:{Accept:'application/vnd.github+json'}});
        if(r.ok){const j=await r.json();if(j&&j.sha)BASE='https://cdn.jsdelivr.net/gh/'+OWNER+'/'+REPO+'@'+j.sha+'/';}
    }catch(e){}
};
const get=async p=>{
    const r=await fetch(BASE+p,{cache:'no-store'});
    if(!r.ok)throw Error(p+' HTTP '+r.status);
    return r.text();
};
const clean=s=>{try{return decodeURIComponent(String(s||'').replace(/^\/+|\/+$/g,''));}catch(e){return'';}};
const route=()=>{const q=clean(new URLSearchParams(location.search).get('rev')||'home');return/^[a-z0-9/_-]+$/i.test(q)&&!q.includes('..')?q:'404';};
const file=r=>r==='home'?'index.html':r+'.html';
const routeUrl=r=>BLOG+(r==='home'?'':'?rev='+encodeURIComponent(r));
const routeFrom=(href,current)=>{
    try{
        if(!href||href[0]==='#'||/^(mailto:|tel:|javascript:)/i.test(href)||/^https:\/\/t\.me\//i.test(href))return null;
        let f='';
        if(/^https?:\/\//i.test(href)){
            const u=new URL(href);
            if(u.hostname==='pvtkyron.github.io')f=u.pathname.split('/Live2dOnWebv1.0.0/')[1]||'index.html';
            else if(u.hostname==='cdn.jsdelivr.net'&&u.pathname.includes('/Live2dOnWebv1.0.0@'))f=u.pathname.split(/Live2dOnWebv1\.0\.0@[^/]+\//)[1]||'index.html';
            else return null;
        }else{
            f=new URL(href,'https://rev.local/'+current).pathname.replace(/^\//,'');
        }
        if(f==='sitemap.xml')return'sitemap';
        if(f==='robots.txt')return'about';
        if(!f.endsWith('.html'))return null;
        f=f.replace(/\.html$/,'');
        return f==='index'?'home':f;
    }catch(e){return null;}
};
const meta=(name,value,prop=false)=>{
    let n=document.head.querySelector('meta['+(prop?'property':'name')+'="'+name+'"]');
    if(!n){n=document.createElement('meta');n.setAttribute(prop?'property':'name',name);document.head.appendChild(n);}
    n.content=value;
};
const canonical=r=>{
    let c=document.head.querySelector('link[rel="canonical"]');
    if(!c){c=document.createElement('link');c.rel='canonical';document.head.appendChild(c);}
    c.href=routeUrl(r);
};
const schema=(r,title,desc)=>{
    document.head.querySelectorAll('script[data-rev-schema]').forEach(n=>n.remove());
    const add=o=>{const s=document.createElement('script');s.type='application/ld+json';s.dataset.revSchema='1';s.textContent=JSON.stringify(o);document.head.appendChild(s);};
    if(r==='home')add({'@context':SCHEMA,'@type':'WebSite',name:'Project Rev マーケット',inLanguage:'ja',url:BLOG,sameAs:[TG]});
    else add({'@context':SCHEMA,'@type':'BreadcrumbList',itemListElement:[{'@type':'ListItem',position:1,name:'Project Rev マーケット',item:BLOG},{'@type':'ListItem',position:2,name:title,item:routeUrl(r)}]});
    if(r.startsWith('posts/'))add({'@context':SCHEMA,'@type':'Article',headline:title,description:desc,inLanguage:'ja',url:routeUrl(r),dateModified:'2026-08-20',author:{'@type':'Organization',name:'Project Rev'},publisher:{'@type':'Organization',name:'Project Rev'}});
};
const applyHead=(doc,r)=>{
    const title=doc.title||'Project Rev マーケット',desc=doc.querySelector('meta[name="description"]')?.content||'Project Revのデジタルツール、購入ガイド、ユーティリティ、更新情報。';
    document.documentElement.lang='ja';document.title=title;meta('description',desc);meta('robots','index,follow,max-image-preview:large,max-snippet:-1');meta('og:title',title,true);meta('og:description',desc,true);meta('og:url',routeUrl(r),true);meta('twitter:card','summary_large_image');canonical(r);schema(r,title,desc);
};
const wire=current=>{
    ROOT.querySelectorAll('[data-lang-toggle],.fa-copy').forEach(n=>n.remove());
    ROOT.querySelectorAll('a[href]').forEach(a=>{
        const href=a.getAttribute('href');
        if(/^https:\/\/t\.me\//i.test(href||'')){a.target=a.target||'_blank';a.rel='noopener';return;}
        const r=routeFrom(href,current);if(!r)return;
        a.href=routeUrl(r);a.dataset.revRoute=r;
        a.addEventListener('click',e=>{if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;e.preventDefault();history.pushState({rev:r},'',routeUrl(r));render();});
    });
    ROOT.querySelectorAll('[data-rev-url="tg"]').forEach(a=>{a.href=TG;a.target='_blank';a.rel='noopener';});
    const top=ROOT.querySelector('.topbar'),nav=ROOT.querySelector('#site-nav')||top?.querySelector('nav');let menu=ROOT.querySelector('[data-menu-toggle]');
    if(nav&&!nav.id)nav.id='site-nav';
    if(top&&nav&&!menu){menu=document.createElement('button');menu.className='menu-toggle';menu.dataset.menuToggle='';menu.setAttribute('aria-label','ナビゲーションを開く');menu.setAttribute('aria-expanded','false');menu.textContent='☰';top.appendChild(menu);}
    if(menu&&nav)menu.addEventListener('click',()=>{const on=nav.classList.toggle('nav-active');menu.setAttribute('aria-expanded',String(on));menu.setAttribute('aria-label',on?'ナビゲーションを閉じる':'ナビゲーションを開く');menu.textContent=on?'×':'☰';});
    const stats=[...ROOT.querySelectorAll('[data-count]')];
    if(stats.length&&'IntersectionObserver'in window){const io=new IntersectionObserver(es=>es.forEach(e=>{if(!e.isIntersecting)return;const n=e.target,t=Number(n.dataset.count||0),s=n.dataset.suffix||'',start=performance.now();const tick=now=>{const p=Math.min((now-start)/700,1),v=Math.round(t*(1-Math.pow(1-p,3)));n.textContent=v.toLocaleString('ja-JP')+s;if(p<1)requestAnimationFrame(tick);};requestAnimationFrame(tick);io.unobserve(n);}),{threshold:.45});stats.forEach(n=>io.observe(n));}
};
const render=async()=>{
    const r=route(),f=file(r);ROOT.setAttribute('aria-busy','true');
    try{
        const doc=new DOMParser().parseFromString(await get(f),'text/html');
        doc.querySelectorAll('script,#waifu').forEach(n=>n.remove());
        ROOT.innerHTML=doc.body.innerHTML;applyHead(doc,r);wire(f);ROOT.removeAttribute('aria-busy');scrollTo(0,0);
    }catch(e){
        console.error('[ProjectRev ルート]',e);ROOT.removeAttribute('aria-busy');
        ROOT.innerHTML='<main class="page-hero"><div class="eyebrow">PROJECT REV / 読み込みエラー</div><h1>マーケットのデータを読み込めませんでした。</h1><p>Blogfa側のページは動いています。いちど再読み込みするか、CDNが復旧するまでTelegramをご利用ください。</p><div class="hero-actions"><a class="cta hot" href="'+BLOG+'">ホーム</a><a class="cta" href="'+TG+'" target="_blank" rel="noopener">Telegram ↗</a></div></main>';
    }
};
const style=()=>{
    const l=document.createElement('link');l.rel='stylesheet';l.href=BASE+'assets/store.css';l.dataset.revStyle='1';document.head.appendChild(l);
    const j=document.createElement('link');j.rel='stylesheet';j.href=BASE+'assets/ja.css';j.dataset.revJaStyle='1';document.head.appendChild(j);
    const s=document.createElement('style');s.dataset.revHero='1';s.textContent='.hero-stage{background-image:url("'+BASE+'assets/hero-grid.svg")!important}';document.head.appendChild(s);
};
const live2d=async()=>{
    try{
        await new Promise((ok,bad)=>{const s=document.createElement('script');s.src=BASE+'dist/live2d_bundle.js';s.onload=ok;s.onerror=bad;document.body.appendChild(s);});
        let code=await get('waifu-tips.js');
        code=code.replace(/'modelUrl'\s*:\s*'[^']*'/,"'modelUrl': "+JSON.stringify(BASE+'model')).replace(/'tipsMessage'\s*:\s*'[^']*'/,"'tipsMessage': "+JSON.stringify(BASE+'waifu-tips.json')).replace(/'homePageUrl'\s*:\s*'[^']*'/,"'homePageUrl': "+JSON.stringify(BLOG)).replace(/'aboutPageUrl'\s*:\s*'[^']*'/,"'aboutPageUrl': "+JSON.stringify(routeUrl('about'))).replace(/#0396FF/gi,'#ff5f8f').replace(/#43CBFF/gi,'#ff9fba').replace(/export\s*\{\s*showMessage\s*,\s*initModel\s*\};?/,'');
        const s=document.createElement('script');s.text=code;s.dataset.revSource='waifu-tips.js';document.body.appendChild(s);
    }catch(e){console.warn('[ProjectRev Live2D]',e);const w=document.getElementById('waifu');if(w)w.style.display='none';}
};
document.addEventListener('click',e=>{const h=e.target.closest&&e.target.closest('.icon-home');if(!h)return;e.preventDefault();e.stopImmediatePropagation();history.pushState({rev:'home'},'',BLOG);render();},true);
addEventListener('popstate',render);
(async()=>{await resolveBase();style();await render();live2d();})().catch(e=>console.error('[ProjectRev ブートストラップ]',e));
})();