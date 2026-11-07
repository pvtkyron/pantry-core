(()=>{
if(window.__REV_STORE_UI__)return;
window.__REV_STORE_UI__=1;
const __revStoreScript=document.currentScript,__revStoreBase=new URL('./',__revStoreScript&&__revStoreScript.src||location.href);if(!document.querySelector('script[data-rev-discovery]')){const s=document.createElement('script');s.src=new URL('rev-discovery.js',__revStoreBase).href;s.defer=true;s.dataset.revDiscovery='1';document.head.appendChild(s)}
document.documentElement.classList.add('js-enhanced');
const $=(q,r=document)=>r.querySelector(q),$$=(q,r=document)=>[...r.querySelectorAll(q)];
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
const top=$('.topbar'),nav=top&&$('nav',top);
let menu=top&&$('[data-menu-toggle]',top);
if(top&&nav&&!menu){menu=document.createElement('button');menu.className='menu-toggle';menu.dataset.menuToggle='';menu.textContent='☰';top.appendChild(menu);}
if(menu&&nav){if(!nav.id)nav.id='site-nav';menu.setAttribute('aria-controls',nav.id);menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label','ナビゲーションを開く');}
const closeMenu=()=>{if(!menu||!nav)return;nav.classList.remove('nav-active');menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label','ナビゲーションを開く');menu.textContent='☰';};
if(menu&&nav){menu.addEventListener('click',()=>{const on=nav.classList.toggle('nav-active');menu.setAttribute('aria-expanded',String(on));menu.setAttribute('aria-label',on?'ナビゲーションを閉じる':'ナビゲーションを開く');menu.textContent=on?'×':'☰';});nav.addEventListener('click',e=>{if(e.target.closest('a'))closeMenu();});}
addEventListener('keydown',e=>{if(e.key==='Escape')closeMenu();});
addEventListener('resize',()=>{if(innerWidth>760)closeMenu();},{passive:true});
if(top)addEventListener('scroll',()=>top.classList.toggle('scrolled',scrollY>18),{passive:true});
if(nav){const page=location.pathname.split('/').pop()||'index.html';$$('a[href]',nav).forEach(a=>{try{const f=new URL(a.href,location.href).pathname.split('/').pop()||'index.html';if(f===page){a.classList.add('active');a.setAttribute('aria-current','page');}else{a.classList.remove('active');a.removeAttribute('aria-current');}}catch{}});}
const filter=$('.filterbar'),cards=$$('.product-card');
if(filter&&cards.length){const buttons=$$('button',filter);buttons.forEach(btn=>{btn.setAttribute('aria-pressed',String(btn.classList.contains('active')));btn.addEventListener('click',()=>{const key=btn.dataset.filter||btn.textContent.trim().toLowerCase();buttons.forEach(b=>{const on=b===btn;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});cards.forEach(card=>{const type=card.dataset.type||($('.eyebrow',card)?.textContent||'').trim().toLowerCase(),hidden=key!=='all'&&!type.includes(key);card.classList.toggle('is-hidden',hidden);card.setAttribute('aria-hidden',String(hidden));});});});}
const reveal=$$('.reveal,.section,.story-grid>a,.reason,.seo-market>div,.gaming-corner').filter((n,i,a)=>a.indexOf(n)===i);
if(reduced)reveal.forEach(n=>n.classList.add('is-visible'));else if('IntersectionObserver'in window){reveal.forEach(n=>{if(!n.classList.contains('reveal'))n.classList.add('section-reveal');});const io=new IntersectionObserver(es=>es.forEach(e=>{if(!e.isIntersecting)return;e.target.classList.add('is-visible');io.unobserve(e.target);}),{threshold:.08,rootMargin:'0px 0px -28px'});reveal.forEach(n=>io.observe(n));}else reveal.forEach(n=>n.classList.add('is-visible'));
if(!reduced)$$('.product-card,.story-grid>a,.reason,.seo-market>div,.gaming-corner').forEach(el=>el.addEventListener('pointermove',e=>{const r=el.getBoundingClientRect();el.style.setProperty('--mx',`${e.clientX-r.left}px`);el.style.setProperty('--my',`${e.clientY-r.top}px`);},{passive:true}));
const article=$('.article');
if(article){const bar=document.createElement('div');bar.className='reading-progress';bar.setAttribute('aria-hidden','true');document.body.appendChild(bar);const progress=()=>{const max=document.documentElement.scrollHeight-innerHeight;bar.style.width=`${max>0?Math.min(100,scrollY/max*100):0}%`;};addEventListener('scroll',progress,{passive:true});progress();}
$$('[data-count]').forEach(n=>{const target=Number(n.dataset.count||0),suffix=n.dataset.suffix||'';if(!target)return;if(reduced){n.textContent=target.toLocaleString('ja-JP')+suffix;return;}let ran=false;const run=()=>{if(ran)return;ran=true;const start=performance.now();const tick=now=>{const p=Math.min((now-start)/700,1),v=Math.round(target*(1-Math.pow(1-p,3)));n.textContent=v.toLocaleString('ja-JP')+suffix;if(p<1)requestAnimationFrame(tick);};requestAnimationFrame(tick);};if('IntersectionObserver'in window){const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){run();io.disconnect();}}),{threshold:.4});io.observe(n);}else run();});
const waifuMessage=$('#waifu-message');
if(waifuMessage){let fixing=false;const localize=()=>{if(fixing)return;const before=waifuMessage.innerHTML,after=before.replace(/Emergency Food/gi,'非常食モデル').replace(/official sample/gi,'公式サンプル').replace(/>LICENSE</gi,'>ライセンス<').replace(/SDK3 bronya/gi,'SDK3 ブローニャ');if(after!==before){fixing=true;waifuMessage.innerHTML=after;fixing=false;}};new MutationObserver(localize).observe(waifuMessage,{childList:true,subtree:true,characterData:true});localize();}
})();
