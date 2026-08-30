(()=>{
if(window.__REV_EDITORIAL_BLOGFA__)return;window.__REV_EDITORIAL_BLOGFA__=1;
const VERSION='2026.08.20.7',OWNER='pvtkyron',REPO='Live2dOnWebv1.0.0',cdn='https://cdn.jsdelivr.net/gh/'+OWNER+'/'+REPO+'@master/assets/blogfa-editorial.css?rev='+VERSION,api='https://api.github.com/repos/'+OWNER+'/'+REPO+'/contents/assets/blogfa-editorial.css?ref=master';
const timeout=(fn,ms)=>{const c=new AbortController(),t=setTimeout(()=>c.abort(),ms);return fn(c.signal).finally(()=>clearTimeout(t))},add=css=>{if(document.querySelector('style[data-rev-editorial-native]'))return;const s=document.createElement('style');s.dataset.revEditorialNative=VERSION;s.textContent=css;document.head.appendChild(s)};
const get=async()=>{for(const x of [{u:cdn,h:{}},{u:api,h:{Accept:'application/vnd.github.raw+json'}}]){try{const r=await timeout(signal=>fetch(x.u,{cache:'no-store',headers:x.h,signal}),6500);if(r.ok){const css=await r.text();if(css.includes('Project Rev Blogfa Editorial '+VERSION)&&css.includes('--rev-paper:#f2ede3'))return css}}catch{}}throw Error('Blogfa Editorial CSS unavailable')};
get().then(add).catch(e=>console.warn('[ProjectRev Editorial]',e));
})();
