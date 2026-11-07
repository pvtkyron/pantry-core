(()=>{
if(window.__REV_EDITORIAL__)return;window.__REV_EDITORIAL__=1;
const VERSION='2026.08.20.7';
const norm=s=>(s||'').toLowerCase().normalize('NFKC').replace(/\s+/g,' ').trim();
const INDEX=[
['01','製品','REV Core','最小構成から始める入口。公開リリース、セットアップ、変更履歴。','products/rev-core.html','core essential entry'],['02','製品','REV Studio','広い設定と制作ワークフローを組みたい人向け。','products/rev-studio.html','studio creator build'],['03','製品','REV Toolkit','実用ヘルパー、リファレンス、ワークフロー部品。','products/rev-toolkit.html','toolkit utility helper'],['04','製品','REV Vault','変更履歴とバージョンの文脈を追うアーカイブ。','products/rev-vault.html','vault archive version'],['05','製品','REV Priority','人による案内とセットアップ支援。','products/rev-priority.html','priority support human'],['06','製品','REV Bundle','複数ラインを広くまとめて検討する構成。','products/rev-bundle.html','bundle broad'],['A1','記事','PUBGプレイヤー向け購入ガイド','ゲーム用ユーティリティを雰囲気で買わないための確認項目。','posts/pubg-player-market-guide.html','pubg game version'],['A2','記事','自分に合うラインを選ぶ方法','最大の箱ではなく、目的から最小の適切なラインを選ぶ。','posts/buyer-guide.html','buyer choose guide'],['A3','記事','Project Revのリリース基準','見える変更、明確なバージョン、謎箱を減らす基準。','posts/project-rev-standard.html','standard release'],['A4','記事','なぜGitHubを情報源にするのか','持ち運べるソースと長く残るURLを維持する理由。','posts/github-first.html','github source architecture'],['FQ','案内','よくある質問','購入、Blogfa、Live2D、クロール、サポートの回答。','faq.html','faq help'],['AB','案内','Project Revについて','サイトの思想、構成、GitHubとTelegramの役割。','about.html','about manifesto']
];
const defaultHref=p=>{const deep=location.pathname.includes('/products/')||location.pathname.includes('/posts/');return(deep?'../':'./')+p};
const mountChatgpt=(root,doc,href)=>{
const box=root.querySelector?.('[data-chatgpt-workspace]');if(!box||box.__revGptMounted)return;box.__revGptMounted=true;
const worker=String(box.dataset.worker||'').replace(/\/$/,''),status=box.querySelector('[data-gpt-status]'),msg=box.querySelector('[data-gpt-msg]'),form=box.querySelector('[data-gpt-login]'),account=box.querySelector('[data-gpt-account]'),list=box.querySelector('[data-gpt-sessions]'),selected=box.querySelector('[data-gpt-selected]'),TOKEN='rev:gpt:web-token:v1',CLIENT='rev:gpt:client-id:v1';
const setMsg=(v,bad=false)=>{if(msg){msg.textContent=v;msg.classList.toggle('error',bad)}},setStatus=v=>{if(status)status.textContent=v};
const client=()=>{let v='';try{v=localStorage.getItem(CLIENT)||''}catch{}if(!/^[0-9a-f-]{36}$/i.test(v)){v=crypto.randomUUID();try{localStorage.setItem(CLIENT,v)}catch{}}return v};
const token=()=>{try{return sessionStorage.getItem(TOKEN)||''}catch{return''}},saveToken=v=>{try{v?sessionStorage.setItem(TOKEN,v):sessionStorage.removeItem(TOKEN)}catch{}};
const call=async(pathname,{method='GET',body=null,auth=true}={})=>{const headers={};if(body!==null)headers['content-type']='application/json';if(auth&&token())headers.authorization='Bearer '+token();const r=await fetch(worker+pathname,{method,headers,body:body===null?undefined:JSON.stringify(body),cache:'no-store'}),d=await r.json().catch(()=>({}));if(!r.ok){const e=new Error(d.error||('Request failed ('+r.status+').'));e.status=r.status;throw e}return d};
const render=items=>{if(!list)return;list.replaceChildren();if(!items.length){const e=doc.createElement('div');e.className='gpt-empty';e.textContent='保存セッションはありません。';list.appendChild(e);return}for(const x of items){const row=doc.createElement('div');row.className='gpt-session';const copy=doc.createElement('div'),b=doc.createElement('b'),small=doc.createElement('small'),use=doc.createElement('button');b.textContent=x.name||'ChatGPT session';small.textContent=((Number(x.size)||0)/1024).toFixed(1)+' KB';copy.append(b,small);use.type='button';use.textContent='Select';use.onclick=async()=>{try{use.disabled=true;setMsg('セッションを確認しています…');const d=await call('/web/session/select',{method:'POST',body:{id:x.id}}),v=d?.selected||x;if(selected){selected.querySelector('b').textContent=v.name||'ChatGPT session';selected.querySelector('span').textContent='選択済み。Open ChatGPTから元のChatGPTを開けます。'}try{sessionStorage.setItem('rev:gpt:selected:v1',JSON.stringify({id:v.id,name:v.name||'ChatGPT session'}))}catch{}setMsg('セッションを選択しました。')}catch(e){setMsg(e.message||String(e),true)}finally{use.disabled=false}};row.append(copy,use);list.appendChild(row)}};const load=async()=>{if(!token()){setStatus('LOGIN');if(form)form.hidden=false;if(account)account.hidden=true;return}try{await call('/web/session');const d=await call('/web/sessions');setStatus('READY');if(form)form.hidden=true;if(account)account.hidden=false;render(Array.isArray(d.items)?d.items:[]);setMsg('保存セッションを選択できます。ChatGPT本体はOpenAIの元ページを開きます。')}catch(e){if(e.status===401)saveToken('');setStatus('LOGIN');if(form)form.hidden=false;if(account)account.hidden=true;setMsg(e.message||String(e),true)}};
form?.addEventListener('submit',async e=>{e.preventDefault();const input=form.elements.license,license=String(input?.value||'').trim();if(!license)return;try{setStatus('…');setMsg('KeyAuthを確認しています…');const d=await call('/web/login',{method:'POST',body:{license,clientId:client()},auth:false});saveToken(String(d.accessToken||''));input.value='';await load()}catch(err){setStatus('LOGIN');setMsg(err.message||String(err),true)}});
box.querySelector('[data-gpt-logout]')?.addEventListener('click',async()=>{try{if(token())await call('/web/logout',{method:'POST'})}catch{}saveToken('');if(selected){selected.querySelector('b').textContent='未選択';selected.querySelector('span').textContent='KeyAuthログイン後、保存セッションを選択できます。'}await load()});
box.querySelector('[data-gpt-open]')?.addEventListener('click',()=>window.open('https://chatgpt.com/','project-rev-chatgpt'));load();
};
const mountSearch=(root,doc,$,$$,href,active,signal)=>{
  const layer=doc.createElement('div');
  layer.className='search-layer';layer.hidden=true;
  layer.innerHTML='<section class="search-panel" role="dialog" aria-modal="true" aria-label="サイト内検索" aria-describedby="search-help"><div class="search-top"><input type="search" autocomplete="off" placeholder="製品、記事、PUBG、バージョン…" aria-label="検索"><button class="search-close" type="button" aria-label="検索を閉じる">×</button></div><div class="search-caption"><span data-search-count role="status" aria-live="polite"></span><span id="search-help">↑ ↓ で選択 · Enter で開く · Esc で閉じる</span></div><div class="search-results"></div></section>';
  (root===doc?doc.body:root).appendChild(layer);
  const input=$('input',layer),results=$('.search-results',layer),count=$('[data-search-count]',layer);
  const scrollRoot=root===doc?doc.documentElement:root.host;
  let previousFocus,previousOverflow='',background=[];
  const mark=item=>$$('.search-result',results).forEach(a=>a.classList.toggle('active',a===item));
  const render=()=>{
    const terms=norm(input.value).split(' ').filter(Boolean);
    const matches=INDEX.filter(row=>terms.every(t=>norm(row.slice(1).join(' ')).includes(t)));
    results.replaceChildren();count.textContent=`${matches.length} 件の結果`;
    for(const row of matches){
      const a=doc.createElement('a'),small=doc.createElement('small'),copy=doc.createElement('span'),title=doc.createElement('b'),summary=doc.createElement('p');
      a.className='search-result';a.href=href(row[4]);small.textContent=row[0]+' / '+row[1];title.textContent=row[2];summary.textContent=row[3];copy.append(title,summary);a.append(small,copy);results.append(a);
    }
    if(!matches.length){const empty=doc.createElement('p');empty.className='search-empty';empty.textContent='一致する項目がありません。短い言葉や、別のキーワードで探してみてください。';results.append(empty)}
    mark($('.search-result',results));
  };
  const close=()=>{
    if(layer.hidden)return;
    layer.hidden=true;
    if(scrollRoot)scrollRoot.style.overflow=previousOverflow;
    background.forEach(([node,inert])=>node.inert=inert);background=[];
    if(previousFocus?.isConnected)previousFocus.focus({preventScroll:true});
  };
  const open=()=>{
    if(!layer.hidden){input.focus();return}
    previousFocus=active();previousOverflow=scrollRoot?.style.overflow||'';
    background=[...(root===doc?doc.body.children:root.children)].filter(n=>n!==layer).map(n=>[n,n.inert]);
    background.forEach(([node])=>node.inert=true);
    layer.hidden=false;if(scrollRoot)scrollRoot.style.overflow='hidden';input.value='';render();input.focus();
  };
  signal.addEventListener('abort',()=>{close();layer.remove()},{once:true});
  input.addEventListener('input',render);
  results.addEventListener('focusin',e=>mark(e.target.closest('.search-result')));
  $('.search-close',layer).addEventListener('click',close);
  layer.addEventListener('click',e=>{if(e.target===layer)close()});
  $$('[data-search]').forEach(b=>b.addEventListener('click',open));
  doc.addEventListener('keydown',e=>{
    const focused=active(),typing=focused?.matches?.('input,textarea,select,[contenteditable]:not([contenteditable="false"])');
    if(((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k')||(!typing&&e.key==='/')){e.preventDefault();open();return}
    if(layer.hidden)return;
    if(e.key==='Escape'){e.preventDefault();close();return}
    const rows=$$('.search-result',results);
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){
      e.preventDefault();if(!rows.length)return;
      const index=rows.indexOf(focused),next=index<0?(e.key==='ArrowDown'?0:rows.length-1):(index+(e.key==='ArrowDown'?1:-1)+rows.length)%rows.length;
      rows[next].focus();return;
    }
    if(e.key==='Enter'&&focused===input){e.preventDefault();rows[0]?.click();return}
    if(e.key==='Tab'){
      const items=[input,$('.search-close',layer),...rows],index=items.indexOf(focused);
      if(e.shiftKey&&(index<=0)){e.preventDefault();items.at(-1).focus()}
      else if(!e.shiftKey&&(index<0||index===items.length-1)){e.preventDefault();input.focus()}
    }
  },{signal});
};

const mountJournal=(root,doc,$,$$)=>{
  const stories=$('[data-stories]');if(!stories)return;
  const rows=$$('.story-row',stories),input=$('[data-story-search]'),buttons=$$('[data-topic]'),count=$('[data-story-count]'),empty=$('[data-story-empty]'),clear=$$('[data-story-reset]');
  let topic='all';
  if(root===doc){const p=new URL(location.href).searchParams;if(input)input.value=p.get('q')||'';if(buttons.some(b=>b.dataset.topic===p.get('topic')))topic=p.get('topic')}
  const apply=()=>{
    const terms=norm(input?.value).split(' ').filter(Boolean);let visible=0;
    rows.forEach(row=>{
      row.hidden=!((topic==='all'||row.dataset.topic===topic)&&terms.every(t=>norm(row.textContent+' '+(row.dataset.search||'')).includes(t)));
      if(!row.hidden)visible++;
    });
    buttons.forEach(b=>{const selected=b.dataset.topic===topic;b.classList.toggle('active',selected);b.setAttribute('aria-pressed',String(selected))});
    if(count)count.textContent=`${visible} / ${rows.length} 記事`;
    if(empty)empty.hidden=visible!==0;
    clear.forEach(b=>b.hidden=b.closest('[data-story-empty]')?false:!terms.length&&topic==='all');
    if(root===doc){
      const url=new URL(location.href);const q=input?.value.trim()||'';
      q?url.searchParams.set('q',q):url.searchParams.delete('q');topic==='all'?url.searchParams.delete('topic'):url.searchParams.set('topic',topic);
      if(url.href!==location.href)try{history.replaceState(history.state,'',url)}catch{}
    }
  };
  input?.addEventListener('input',apply);
  buttons.forEach(b=>b.addEventListener('click',()=>{topic=b.dataset.topic;apply()}));
  clear.forEach(b=>b.addEventListener('click',()=>{topic='all';if(input)input.value='';apply();input?.focus()}));
  const tools=$('.journal-tools');if(tools)tools.hidden=false;
  apply();
};

const mountArticle=(root,doc,$,$$,opt,signal)=>{
  const article=$('.article-body');if(!article)return;
  const headings=$$('h2',article),toc=$('.article-toc'),links=[];
  headings.forEach((h,i)=>{if(!h.id)h.id='section-'+(i+1)});
  if(toc&&headings.length){
    const toggle=doc.createElement('button'),list=doc.createElement('div');
    toggle.type='button';toggle.className='toc-toggle';toggle.textContent=`目次 · ${headings.length} セクション`;
    list.className='toc-links';list.id='article-toc-links';list.hidden=matchMedia('(max-width:760px)').matches;
    toggle.setAttribute('aria-controls',list.id);toggle.setAttribute('aria-expanded',String(!list.hidden));
    toggle.addEventListener('click',()=>{list.hidden=!list.hidden;toggle.setAttribute('aria-expanded',String(!list.hidden))});
    headings.forEach((h,i)=>{
      const a=doc.createElement('a');a.href='#'+h.id;a.textContent=String(i+1).padStart(2,'0')+' — '+h.textContent;
      a.addEventListener('click',e=>{
        e.preventDefault();h.tabIndex=-1;h.focus({preventScroll:true});h.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth',block:'start'});
        if(root===doc)try{const url=new URL(location.href);url.hash=h.id;history.replaceState(history.state,'',url)}catch{}
      });
      links.push(a);list.append(a);
    });
    toc.replaceChildren(toggle,list);
  }
  const toolbar=doc.createElement('div');toolbar.className='article-toolbar';
  toolbar.innerHTML='<div class="reader-sizes" role="group" aria-label="本文の文字サイズ"><button type="button" data-reader-size="standard" aria-pressed="true">標準</button><button type="button" data-reader-size="large" aria-pressed="false">大きく</button></div><button type="button" class="article-share">リンクをコピー ↗</button><span class="reader-status" role="status" aria-live="polite"></span>';
  $('.article-mast')?.append(toolbar);
  const share=$('.article-share',toolbar),status=$('.reader-status',toolbar),sizes=$$('[data-reader-size]',toolbar);
  const setSize=value=>{article.classList.toggle('reader-large',value==='large');sizes.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.readerSize===value)));schedule()};
  sizes.forEach(b=>b.addEventListener('click',()=>{const value=b.dataset.readerSize;setSize(value);try{localStorage.setItem('rev:reader-size',value)}catch{}}));
  share.addEventListener('click',async()=>{
    share.disabled=true;
    try{
      const canonical=root===doc?doc.querySelector('link[rel="canonical"]')?.href:null,url=new URL(canonical||location.href);url.hash=location.hash;
      await navigator.clipboard.writeText(url.href);status.textContent='リンクをコピーしました。';
    }catch{status.textContent='コピーできませんでした。アドレスバーのURLを共有してください。'}
    finally{share.disabled=false}
  });
  const bar=doc.createElement('div');bar.className='reading-progress';bar.setAttribute('aria-hidden','true');(root===doc?doc.body:root).append(bar);
  const scrollTarget=opt.scrollTarget||(root===doc?window:root.host);let frame=0;
  const progress=()=>{
    frame=0;const rect=article.getBoundingClientRect(),hostRect=root.host?.getBoundingClientRect(),top=hostRect?.top||0,viewHeight=root===doc?innerHeight:root.host?.clientHeight||innerHeight;
    const offset=Math.max(top,$('.site-header')?.getBoundingClientRect().bottom||top)+24;
    const distance=Math.max(1,rect.height-(viewHeight-(offset-top)-24)),ratio=Math.max(0,Math.min(1,(offset-rect.top)/distance));
    bar.style.transform=`scaleX(${ratio})`;
    let current=0;headings.forEach((h,i)=>{if(h.getBoundingClientRect().top<=offset+40)current=i});
    links.forEach((a,i)=>{if(i===current)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current')});
  };
  function schedule(){if(!frame)frame=requestAnimationFrame(progress)}
  scrollTarget?.addEventListener('scroll',schedule,{passive:true,signal});window.addEventListener('resize',schedule,{passive:true,signal});
  signal.addEventListener('abort',()=>{if(frame)cancelAnimationFrame(frame);bar.remove();toolbar.remove()},{once:true});
  let saved='standard';try{if(localStorage.getItem('rev:reader-size')==='large')saved='large'}catch{}
  setSize(saved);
};

const mount=(root=document,opt={})=>{
if(!root||root.__revEditorialMounted)return false;root.__revEditorialMounted=VERSION;
const lifecycle=new AbortController(),signal=lifecycle.signal;
root.__revEditorialDispose=()=>{lifecycle.abort();delete root.__revEditorialMounted};
const doc=root.ownerDocument||root,$=(q,r=root)=>r.querySelector(q),$$=(q,r=root)=>[...r.querySelectorAll(q)],href=typeof opt.resolveHref==='function'?opt.resolveHref:defaultHref,active=()=>root===doc?doc.activeElement:(root.activeElement||doc.activeElement);
const nav=$('.site-nav'),menu=$('[data-menu]');
if(nav&&!nav.querySelector('[data-rev-chatgpt]')){const a=doc.createElement('a');a.dataset.revChatgpt='1';a.href=href('chatgpt.html');a.textContent='ChatGPT';const about=[...nav.querySelectorAll('a')].find(x=>/about\.html|このサイト/.test(x.getAttribute('href')||x.textContent));nav.insertBefore(a,about||nav.lastElementChild);}
if(nav&&menu){
  if(!nav.id)nav.id='site-navigation';menu.setAttribute('aria-controls',nav.id);
  const close=()=>{nav.classList.remove('nav-active');menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label','メニューを開く');menu.textContent='☰'};
  menu.addEventListener('click',()=>{const on=nav.classList.toggle('nav-active');menu.setAttribute('aria-expanded',String(on));menu.setAttribute('aria-label',on?'メニューを閉じる':'メニューを開く');menu.textContent=on?'×':'☰'});
  nav.addEventListener('click',e=>{if(e.target.closest('a'))close()});
  doc.addEventListener('keydown',e=>{if(e.key==='Escape'&&nav.classList.contains('nav-active')){close();menu.focus()}},{signal});
  doc.addEventListener('click',e=>{const path=e.composedPath();if(nav.classList.contains('nav-active')&&!path.includes(nav)&&!path.includes(menu))close()},{signal});
  addEventListener('resize',()=>{if(innerWidth>1060)close()},{passive:true,signal});
  close();
}
if(nav&&!opt.resolveHref){const here=location.pathname.split('/').pop()||'index.html';$$('a[href]',nav).forEach(a=>{try{const f=new URL(a.href,location.href).pathname.split('/').pop()||'index.html';if(f===here){a.classList.add('active');a.setAttribute('aria-current','page')}}catch{}})}
mountSearch(root,doc,$,$$,href,active,signal);
const catalog=$('[data-catalog]');if(catalog){const cards=$$('.catalog-card',catalog),search=$('[data-catalog-search]'),select=$('[data-catalog-sort]'),buttons=$$('[data-filter]'),count=$('[data-result-count]');let type='all';const apply=()=>{const q=norm(search?.value),visible=cards.filter(c=>{const okType=type==='all'||c.dataset.type===type,okQ=!q||norm(c.textContent+' '+(c.dataset.search||'')).includes(q);c.hidden=!(okType&&okQ);return okType&&okQ});if(select){const order=select.value,sorted=[...visible].sort((a,b)=>order==='name'?a.dataset.name.localeCompare(b.dataset.name,'ja'):order==='reverse'?Number(b.dataset.no)-Number(a.dataset.no):Number(a.dataset.no)-Number(b.dataset.no));sorted.forEach(c=>catalog.appendChild(c))}if(count)count.textContent=`${visible.length} / ${cards.length} ライン`};search?.addEventListener('input',apply);select?.addEventListener('change',apply);buttons.forEach(b=>b.addEventListener('click',()=>{type=b.dataset.filter;buttons.forEach(x=>x.classList.toggle('active',x===b));apply()}));apply()}
mountJournal(root,doc,$,$$);
mountArticle(root,doc,$,$$,opt,signal);
mountChatgpt(root,doc,href);
return true};
window.REV_EDITORIAL_MOUNT=mount;
const auto=()=>{if(document.querySelector('.site-header'))mount(document)};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',auto,{once:true});else auto();
})();
