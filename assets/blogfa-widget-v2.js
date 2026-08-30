(()=>{
if(window.__REV_BLOGFA_WIDGET_V2__)return;
window.__REV_BLOGFA_WIDGET_V2__=1;
if(window.__REV_BLOGFA_WIDGET_V3__)return;
const OWNER='pvtkyron',REPO='Live2dOnWebv1.0.0',FILE='assets/blogfa-widget-v3.js';
const src='https://cdn.jsdelivr.net/gh/'+OWNER+'/'+REPO+'@master/'+FILE+'?legacy=v2&rev='+Date.now();
const s=document.createElement('script');
s.async=true;
s.src=src;
s.dataset.revLegacyWidget='v2';
s.onerror=()=>console.error('[ProjectRev 旧ウィジェット v2] 日本語版v3ランタイムを読み込めませんでした');
document.head.appendChild(s);
})();
