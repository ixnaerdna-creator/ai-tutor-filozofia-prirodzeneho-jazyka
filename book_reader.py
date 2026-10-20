"""Klikateľná čítačka antológie s jediným posuvným panelom.

Komponent Streamlit v2: HTML/CSS/JS sa vykonávajú na strane prehliadača.
Do Pythonu odosiela iba ID kliknutého odseku.
"""
import streamlit as st

READER_HTML = """
<div class="fpj-shell" lang="sk">
  <div class="fpj-tools">
    <input type="search" id="fpj-search" placeholder="Hľadať v štúdii…" aria-label="Vyhľadávanie v štúdii" autocomplete="off" />
    <button type="button" id="fpj-prev" aria-label="Predchádzajúci nález" title="Predchádzajúci nález">↑</button>
    <button type="button" id="fpj-next" aria-label="Nasledujúci nález" title="Nasledujúci nález">↓</button>
    <select id="fpj-chapters" aria-label="Prejsť na pododdiel alebo stranu"></select>
    <button type="button" id="fpj-start">Na začiatok</button>
    <button type="button" id="fpj-end-btn">Na koniec</button>
  </div>
  <div class="fpj-context" aria-live="polite">
    <span id="fpj-current"></span>
    <span id="fpj-found"></span>
  </div>
  <div class="fpj-scroll" id="fpj-scroll" tabindex="0" aria-label="Posuvný text vybranej štúdie">
    <div id="fpj-text"></div>
    <div id="fpj-bottom">Koniec vybranej štúdie</div>
  </div>
</div>
"""

READER_CSS = r"""
:host { display:block; width:100%; height:780px; }
*, *::before, *::after { box-sizing:border-box; }
.fpj-shell { height:780px; max-height:780px; min-height:780px; width:100%; overflow:hidden;
  display:flex; flex-direction:column; color:var(--st-text-color,#222);
  font-family:Georgia,'Times New Roman',serif; }
.fpj-tools { display:flex; flex:0 0 auto; flex-wrap:wrap; align-items:center;
  gap:6px; padding:5px 0 9px; font:12px system-ui,sans-serif; }
.fpj-tools input, .fpj-tools select { border:1px solid #9daab5; border-radius:5px;
  color:var(--st-text-color,#222); background:var(--st-background-color,#fff);
  padding:7px 8px; font:13px system-ui,sans-serif; min-height:35px; }
.fpj-tools input {flex:2 1 170px; min-width:130px;}
.fpj-tools select {flex:1 1 130px; min-width:120px; max-width:260px;}
.fpj-tools button {border:1px solid #aab4bf; color:var(--st-text-color,#222);
  background:var(--st-background-color,#fff); border-radius:5px; cursor:pointer;
  padding:7px 9px; min-height:35px; font:12px system-ui,sans-serif; white-space:nowrap;}
.fpj-tools button:hover {background:#e7edf3; color:#222;}
.fpj-tools button:focus-visible, .fpj-tools select:focus-visible, .fpj-tools input:focus-visible {
  outline:2px solid #3779b6; outline-offset:1px;}
.fpj-context {flex:0 0 auto; display:flex; justify-content:space-between; gap:8px; min-height:26px;
  color:var(--st-text-color,#555); opacity:.8; font:12px/1.3 system-ui,sans-serif;
  padding:0 4px 7px;}
#fpj-current {max-width:70%; overflow:hidden; white-space:nowrap; text-overflow:ellipsis;}
#fpj-found {flex:0 0 auto; white-space:nowrap;}
.fpj-scroll { flex:1 1 0; min-height:0; overflow-y:auto; overflow-x:hidden;
  scrollbar-width:auto; scrollbar-color:#59636e #e7eaef; scrollbar-gutter:stable;
  overscroll-behavior:contain; border-top:1px solid #d9dfe4;
  scroll-behavior:auto; }
.fpj-scroll::-webkit-scrollbar {width:16px;}
.fpj-scroll::-webkit-scrollbar-track {background:#e7eaef;}
.fpj-scroll::-webkit-scrollbar-thumb {background:#59636e; border:3px solid #e7eaef; border-radius:9px;}
#fpj-text {padding:12px 12px 4px 0;}
.fpj-heading {font:700 21px/1.4 Georgia,serif; margin:22px 0 14px;
  padding:0 0 9px; border-bottom:1px solid #bdc7d0; color:var(--st-text-color,#222);}
.fpj-heading:first-child {margin-top:0;}
.fpj-paragraph {display:block; width:100%; white-space:normal; text-align:left;
  background:transparent; color:var(--st-text-color,#222); border:0;
  border-left:3px solid transparent; padding:7px 9px 12px 10px; margin:0 0 7px;
  cursor:pointer; overflow-wrap:break-word;
  font:18px/1.55 Georgia,'Times New Roman',serif; border-radius:2px;}
.fpj-paragraph:hover {background:#edf4f9;}
.fpj-paragraph:focus-visible {outline:2px solid #3876ab; outline-offset:-2px;}
.fpj-paragraph.fpj-selected {border-left-color:#4a82ae; background:#edf5fc;}
.fpj-paragraph.fpj-hit {border-left-color:#ae7700; background:#ffecac; color:#272019;}
.fpj-location {display:block; color:#6b7480; margin-bottom:3px; font:11px/1.35 system-ui,sans-serif;}
.fpj-paragraph.fpj-hit .fpj-location {color:#735000;}
.fpj-note {font:14px/1.45 Georgia,serif; padding:4px 10px; margin:8px 0;
  border-left:2px solid #aeb7c2; opacity:.78;}
#fpj-bottom {padding:18px 8px 30px; margin:22px 0 0;
  border-top:1px solid #b9c1cb; color:var(--st-text-color,#555);
  font:13px system-ui,sans-serif;}
@media(max-width:700px){.fpj-paragraph{font-size:16px;} .fpj-tools button{padding:6px 7px;}}
"""

READER_JS = r"""
export default function({parentElement, data, setTriggerValue}) {
  const root=parentElement.querySelector('.fpj-shell');
  const scroll=root.querySelector('#fpj-scroll');
  const content=root.querySelector('#fpj-text');
  const searchInput=root.querySelector('#fpj-search');
  const chapterList=root.querySelector('#fpj-chapters');
  const prev=root.querySelector('#fpj-prev');
  const next=root.querySelector('#fpj-next');
  const first=root.querySelector('#fpj-start');
  const last=root.querySelector('#fpj-end-btn');
  const found=root.querySelector('#fpj-found');
  const current=root.querySelector('#fpj-current');
  const rows=Array.isArray(data?.paragraphs)?data.paragraphs:[];
  const storageKey='fpj.reader.v1.'+(data?.bookKey||'default');
  const normalized=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const entries=[], sections=[], pages=new Map();
  const fragment=document.createDocumentFragment();
  let hits=[], hitIndex=0, initialized=false, clickNumber=0;
  let rememberedScroll=0, rememberedSearch='';
  try {
    rememberedScroll=Number(sessionStorage.getItem(storageKey+'.scroll'))||0;
    rememberedSearch=sessionStorage.getItem(storageKey+'.search')||'';
  } catch(_) {}

  for (const row of rows) {
    if (row.type==='heading') {
      const h=document.createElement('h3');
      h.className='fpj-heading'; h.textContent=row.text;
      fragment.appendChild(h);
      sections.push({label:row.text, el:h});
      continue;
    }
    if (row.source_print_page!=null && !pages.has(String(row.source_print_page))) pages.set(String(row.source_print_page), null);
    if (row.type==='note') {
      const note=document.createElement('div');
      note.className='fpj-note'; note.textContent=row.text;
      fragment.appendChild(note);
      continue;
    }
    if (row.type!=='paragraph') continue;
    const p=document.createElement('button');
    p.type='button';
    p.className='fpj-paragraph'+(row.id===data?.selected?' fpj-selected':'');
    p.setAttribute('aria-label','Vysvetliť odsek '+row.id);
    const place=document.createElement('span'); place.className='fpj-location';
    const placeParts=[];
    if (row.source_print_page!=null) placeParts.push('s. '+row.source_print_page);
    if (row.subchapter) placeParts.push(row.subchapter);
    place.textContent=placeParts.join(' · ');
    const body=document.createElement('span'); body.textContent=row.text;
    p.append(place,body);
    p.addEventListener('click',()=>{
      for(const n of entries) n.el.classList.toggle('fpj-selected',n.id===row.id);
      remember(); setTriggerValue('selected', {id:row.id, nonce:Date.now()+'-'+(++clickNumber)});
    });
    fragment.appendChild(p);
    if (row.source_print_page!=null && pages.get(String(row.source_print_page))===null) pages.set(String(row.source_print_page),p);
    entries.push({id:row.id,el:p,searchable:normalized(
      [row.id,row.text].join(' '))});
  }
  content.replaceChildren(fragment);

  const topMax=()=>Math.max(0,scroll.scrollHeight-scroll.clientHeight);
  function remember() {
    if (!initialized) return;
    try {sessionStorage.setItem(storageKey+'.scroll',String(scroll.scrollTop));}catch(_){}
  }
  function jump(position) {
    scroll.scrollTop=Math.max(0,Math.min(topMax(),position));
    remember(); updateCurrent();
  }
  function reveal(node) {
    const diff=node.getBoundingClientRect().top-scroll.getBoundingClientRect().top;
    jump(scroll.scrollTop+diff-14);
  }
  function updateCurrent() {
    let label=sections.length?sections[0].label:'';
    const threshold=scroll.getBoundingClientRect().top+32;
    for(const section of sections) {
      if(section.el.getBoundingClientRect().top<=threshold) label=section.label;
      else break;
    }
    const firstVisible=entries.find(e=>e.el.getBoundingClientRect().bottom>scroll.getBoundingClientRect().top+12);
    if (firstVisible) { const foundPage=firstVisible.el.querySelector('.fpj-location')?.textContent||'';
      current.textContent=[label,foundPage].filter(Boolean).join(' · ');
    } else current.textContent=label;
  }
  function highlight() {
    for(const entry of entries) entry.el.classList.remove('fpj-hit');
    if(!hits.length) {found.textContent=searchInput.value.trim()?'Bez nálezov':'';return;}
    const chosen=entries[hits[hitIndex]];
    chosen.el.classList.add('fpj-hit');
    found.textContent=`Nález ${hitIndex+1} z ${hits.length} · ${chosen.id}`;
  }
  function runSearch(jumpToFirst=false) {
    const q=normalized(searchInput.value.trim());
    hits=[];
    if(q) entries.forEach((n,i)=>{if(n.searchable.includes(q))hits.push(i)});
    hitIndex=0;
    highlight();
    try {sessionStorage.setItem(storageKey+'.search',searchInput.value)}catch(_){}
    if(jumpToFirst&&hits.length)reveal(entries[hits[0]].el);
  }
  function nextHit(delta) {
    if(!hits.length)return;
    hitIndex=(hitIndex+delta+hits.length)%hits.length;
    highlight(); reveal(entries[hits[hitIndex]].el);
  }
  chapterList.replaceChildren();
  const beginning=document.createElement('option');
  beginning.value='top'; beginning.textContent='Začiatok textu'; chapterList.appendChild(beginning);
  sections.forEach((section,i)=>{
    const option=document.createElement('option');
    option.value=String(i); option.textContent=section.label;
    chapterList.appendChild(option);
  });
  for (const [page, node] of pages.entries()) {
    if(!node) continue;
    const option=document.createElement('option'); option.value='page:'+page;
    option.textContent='Strana '+page; chapterList.appendChild(option);
  }
  chapterList.disabled=sections.length===0&&pages.size===0;
  const onChapter=()=>{
    const value=chapterList.value;
    if(value==='top')jump(0);
    else if (value.startsWith('page:') && pages.get(value.slice(5))) reveal(pages.get(value.slice(5)));
    else if(sections[Number(value)])reveal(sections[Number(value)].el);
  };
  const onInput=()=>runSearch(true);
  const onSearchKey=e=>{
    if(e.key==='ArrowDown'||e.key==='Enter'){e.preventDefault();nextHit(1);}
    if(e.key==='ArrowUp'){e.preventDefault();nextHit(-1);}
  };
  const onPrev=()=>nextHit(-1), onNext=()=>nextHit(1);
  const onFirst=()=>jump(0), onLast=()=>jump(scroll.scrollHeight);
  const onScroll=()=>{remember(); updateCurrent();};
  searchInput.value=rememberedSearch;
  runSearch(false);
  chapterList.addEventListener('change',onChapter);
  searchInput.addEventListener('input',onInput);
  searchInput.addEventListener('keydown',onSearchKey);
  prev.addEventListener('click',onPrev);
  next.addEventListener('click',onNext);
  first.addEventListener('click',onFirst);
  last.addEventListener('click',onLast);
  scroll.addEventListener('scroll',onScroll,{passive:true});
  jump(rememberedScroll);
  initialized=true;
  updateCurrent();
  return ()=>{
    chapterList.removeEventListener('change',onChapter);
    searchInput.removeEventListener('input',onInput);
    searchInput.removeEventListener('keydown',onSearchKey);
    prev.removeEventListener('click',onPrev);
    next.removeEventListener('click',onNext);
    first.removeEventListener('click',onFirst);
    last.removeEventListener('click',onLast);
    scroll.removeEventListener('scroll',onScroll);
  };
}
"""

book_reader = st.components.v2.component(
    name="fpj_text_reader_v1", html=READER_HTML,
    css=READER_CSS, js=READER_JS, isolate_styles=True,
)
