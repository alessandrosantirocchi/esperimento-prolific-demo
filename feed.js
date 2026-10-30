// InstaLab — social feed simulator. Edit posts.json to replace stimuli.
// No real Instagram API, accounts, or external communication.
export default function (component) {
  const { parentElement, data, setStateValue } = component;
  const root = parentElement.querySelector('#instalab-root');
  if (!root) return;
  const posts = Array.isArray(data?.posts) ? data.posts : [];
  const stories = Array.isArray(data?.stories) ? data.stories : [];
  const participantId = data?.participant_id || 'DEMO_SESSION';
  const escape = (v) => String(v ?? '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
  const shorten = (n) => new Intl.NumberFormat('it-IT').format(n);
  const ico = (name, filled=false, size=25) => {
    const shapes = {
      home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
      search: '<circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/>',
      compass: '<circle cx="12" cy="12" r="9"/><path d="m15.7 8.3-2.4 5-5 2.4 2.4-5z"/>',
      reels: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 5l4 5M16 5l4 5M10 13l5 3-5 3z"/>',
      message: '<path d="M21 3 3 10l7.5 2.4L13 20l8-17z"/><path d="m10.5 12.4 10.5-9.4"/>',
      heart: '<path d="M20.8 4.6a5.4 5.4 0 0 0-7.7 0L12 5.7l-1.1-1.1a5.4 5.4 0 0 0-7.7 7.7L12 21l8.8-8.7a5.4 5.4 0 0 0 0-7.7z"/>',
      plus: '<rect x="3" y="3" width="18" height="18" rx="5"/><path d="M12 7v10M7 12h10"/>',
      menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
      comment: '<path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 9.4 9.4 0 0 1-4-.9L3 21l1.9-5.5A8.5 8.5 0 1 1 21 11.5z"/>',
      bookmark: '<path d="M5 3.5h14v17L12 16l-7 4.5z"/>',
      more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
      chevron: '<path d="m9 18 6-6-6-6"/>',
      close: '<path d="M18 6 6 18M6 6l12 12"/>',
      check: '<path d="m5 12 4 4L19 6"/>',
      smile: '<circle cx="12" cy="12" r="9"/><path d="M8 14c1 2 7 2 8 0"/><path d="M8 9h.01M16 9h.01"/>',
      grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
      clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
      volume: '<path d="M5 10H2v4h3l5 4V6zM14 9a4 4 0 0 1 0 6"/>',
      profile: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-5 16-5 16 0"/>',
      info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.1"/>',
      arrow: '<path d="M12 19V5m-7 7 7-7 7 7"/>',
    };
    const paint = filled ? 'currentColor' : 'none';
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="${paint}" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${shapes[name] || ''}</svg>`;
  };
  const timeLabel = (m) => m < 60 ? `${m} min` : m < 1440 ? `${Math.floor(m/60)} h` : `${Math.floor(m/1440)} g`;
  const history = Array.isArray(data?.history) ? data.history : [];
  let s = root.__instalab_state;
  if (!s || s.participantId !== participantId) {
    s = { participantId, tab:'home', overlay:null, overlayPost:null, storyIndex:0, query:'',
          liked:new Set(), disliked:new Set(), saved:new Set(), followed:new Set(), comments:{}, expanded:new Set(),
          events:history.slice(), started:Date.now(), seen:new Set() };
    for (const e of history) {
      if (e.event_type === 'like') s.liked.add(e.post_id);
      if (e.event_type === 'unlike') s.liked.delete(e.post_id);
      if (e.event_type === 'dislike') s.disliked.add(e.post_id);
      if (e.event_type === 'remove_dislike') s.disliked.delete(e.post_id);
      if (e.event_type === 'save') s.saved.add(e.post_id);
      if (e.event_type === 'unsave') s.saved.delete(e.post_id);
      if (e.event_type === 'follow') s.followed.add(e.details?.username);
      if (e.event_type === 'unfollow') s.followed.delete(e.details?.username);
      if (e.event_type === 'comment_submit') {
        (s.comments[e.post_id] ||= []).push({ username:'you', text:e.details?.text || '' });
      }
      if (e.event_id) s.seen.add(e.event_id);
    }
    root.__instalab_state = s;
  }
  s.disliked ||= new Set();

  let observer;
  const signal = (type, postId=null, details={}) => {
    const event = {
      event_id:`${Date.now()}-${Math.random().toString(36).slice(2,11)}`,
      event_type:type, post_id:postId, client_ts:new Date().toISOString(),
      elapsed_ms:Date.now()-s.started, details
    };
    s.events.push(event);
    // Keep all events in the browser for the demo session; Python deduplicates IDs.
    setStateValue('events', s.events);
  };
  const postBy = (id) => posts.find(p => p.id === id);
  const profileAvatar = (image, extra='') => image
    ? `<img class="avatar-img ${extra}" alt="" src="${escape(image)}" />`
    : `<span class="avatar-fallback ${extra}">${ico('profile',false,20)}</span>`;
  const navItem = (tab, iconName, label, hideOnCompact=false) =>
    `<button class="nav-entry ${s.tab===tab?'selected':''} ${hideOnCompact?'compact-hide':''}" data-action="nav" data-tab="${tab}" aria-label="${escape(label)}">${ico(iconName, s.tab===tab)}<span>${escape(label)}</span></button>`;

  const storyList = () => `<div class="stories" aria-label="Storie">
    ${stories.map((a,i)=>`<button class="story" data-action="story" data-index="${i}" title="Apri storia di ${escape(a.username)}">
      <span class="story-ring ${a.own?'own':''}"><span class="story-inside">${profileAvatar(a.image_url)}</span>${a.own?'<b class="story-plus">+</b>':''}</span>
      <span class="story-name">${escape(a.username)}</span>
    </button>`).join('')}
   </div>`;
  const eachComment = c => `<div class="comment-line"><strong>${escape(c.username)}</strong> ${escape(c.text)}</div>`;
  const post = (p) => {
    const isLiked = s.liked.has(p.id), isSaved = s.saved.has(p.id);
    const list = [...(p.comments || []), ...(s.comments[p.id] || [])];
    const shown = s.expanded.has(p.id) ? list : list.slice(-2);
    // Display one source-sheet tile without modifying the original stimulus.
    const region = p.image_region;
    const imageStyle = region ? `position:absolute;max-width:none;width:${region.source_width/region.width*100}%;height:auto;left:${-region.x/region.width*100}%;top:${-region.y/region.height*100}%;` : `object-position:${escape(p.image_position || 'center')};`;
    return `<article class="post" data-post="${escape(p.id)}">
       <header class="post-header">
         <button class="avatar-button" data-action="profile" data-user="${escape(p.username)}">${profileAvatar(p.avatar_url)}</button>
         <div class="post-header-main"><div class="post-name-row"><button class="username-link" data-action="profile" data-user="${escape(p.username)}">${escape(p.username)}</button>${p.verified?'<span class="verified" aria-label="Account verificato">✓</span>':''}<span class="time-dot">·</span><span class="time-small">${timeLabel(Number(p.minutes_ago)||42)}</span></div><div class="post-location">${escape(p.location || '')}</div></div>
         <button class="icon-button options" data-action="post_more" data-post="${escape(p.id)}" aria-label="Opzioni">${ico('more')}</button>
       </header>
       <div class="photo-wrap" data-doublepost="${escape(p.id)}">
          ${p.image_url?`<img class="post-photo" style="${imageStyle}" loading="lazy" src="${escape(p.image_url)}" alt="Foto del post di ${escape(p.username)}" />`:'<div class="photo-placeholder">Carica uno stimolo in posts.json</div>'}
          <div class="burst-heart">${ico('heart',true,105)}</div>
       </div>
       <div class="post-actions">
         <div class="post-actions-left">
           <button class="icon-button ${isLiked?'liked':''}" data-action="like" data-post="${escape(p.id)}" aria-label="${isLiked?'Rimuovi mi piace':'Mi piace'}" aria-pressed="${isLiked}">${ico('heart',isLiked,28)}</button>
           <button class="icon-button" data-action="dislike" data-post="${escape(p.id)}" aria-label="${s.disliked.has(p.id)?'Rimuovi dislike':'Dislike'}" aria-pressed="${s.disliked.has(p.id)}"><span aria-hidden="true">👎</span></button>
           <button class="icon-button" data-action="open_comments" data-post="${escape(p.id)}" aria-label="Commenta">${ico('comment',false,27)}</button>
         </div>
         <button class="icon-button ${isSaved?'saved':''}" data-action="save" data-post="${escape(p.id)}" aria-label="${isSaved?'Rimuovi dai salvati':'Salva'}" aria-pressed="${isSaved}">${ico('bookmark',isSaved,27)}</button>
       </div>
       <div class="post-body">
         <div class="likes"><strong>${shorten((Number(p.initial_likes)||0)+(isLiked?1:0))} Mi piace</strong></div>
         <div class="caption-line"><strong>${escape(p.username)}</strong> ${escape(p.caption)}</div>
         ${list.length>2&&!s.expanded.has(p.id)?`<button class="muted-link" data-action="expand" data-post="${escape(p.id)}">Visualizza tutti i ${list.length} commenti</button>`:''}
         <div class="comments-preview">${shown.map(eachComment).join('')}</div>
         <form class="comment-form" data-comment-post="${escape(p.id)}"><input type="text" maxlength="280" placeholder="Aggiungi un commento..." aria-label="Scrivi un commento" autocomplete="off" /><button type="submit" class="submit-comment">Pubblica</button></form>
       </div>
     </article>`;
  };
  const home = () => `<div class="feed-area"><main class="timeline">${storyList()}<div class="post-list">${posts.map(post).join('')}</div><div class="end-feed"><div class="end-check">${ico('check')}</div><strong>Sei in pari</strong><span>Hai visto tutti i post di questa simulazione</span></div></main></div>`;
  const explore = (savedOnly=false) => `<section class="other-page"><header class="other-header"><h2>${savedOnly?'Elementi salvati':'Esplora'}</h2><p>${savedOnly?'I post che hai salvato':'Scopri i post della simulazione'}</p></header><div class="explore-grid">${posts.filter(p=>!savedOnly||s.saved.has(p.id)).map(p=>`<button class="explore-tile" data-action="open_post" data-post="${escape(p.id)}"><img src="${escape(p.image_url)}" alt=""/><span>${ico('heart',true,18)} ${shorten(Number(p.initial_likes)||0)}</span></button>`).join('')||'<div class="empty-state">Non hai ancora salvato nessun post.</div>'}</div></section>`;
  const search = () => `<section class="other-page"><header class="other-header"><h2>Cerca</h2><p>Cerca profili e post dimostrativi</p></header><div class="search-box">${ico('search')}<input autofocus class="search-input" type="search" placeholder="Cerca" value="${escape(s.query)}" aria-label="Cerca nel feed" /></div><div class="search-results">${posts.filter(p=>p.username.toLowerCase().includes(s.query.toLowerCase())||p.caption.toLowerCase().includes(s.query.toLowerCase())).map(p=>`<button class="search-result" data-action="open_post" data-post="${escape(p.id)}">${profileAvatar(p.avatar_url)}<span><strong>${escape(p.username)}</strong><small>${escape(p.location)}</small></span>${ico('chevron',false,18)}</button>`).join('')}</div></section>`;
  const profile = () => `<section class="other-page profile-page"><div class="profile-header"><span class="large-avatar">${ico('profile',false,48)}</span><div><div class="profile-username">you.research <span class="demo-tag">Account demo</span></div><div class="profile-stats"><span><strong>0</strong> post</span><span><strong>0</strong> follower</span><span><strong>${s.followed.size}</strong> seguiti</span></div><p>Profilo di simulazione per studi di ricerca.</p></div></div><div class="profile-tabs"><button class="active">${ico('grid',false,17)} Post</button><button data-action="nav" data-tab="saved">${ico('bookmark',false,17)} Elementi salvati</button></div><div class="empty-state">I post del feed sono esempi, non appartengono a questo profilo.</div></section>`;
  const misc = (tab) => `<section class="other-page"><header class="other-header"><h2>${({reels:'Reels',messages:'Messaggi',notifications:'Notifiche',create:'Crea'})[tab]||tab}</h2><p>Funzionalità dimostrativa</p></header><div class="empty-panel">${ico(tab==='messages'?'message':tab==='notifications'?'heart':tab==='reels'?'reels':'plus',false,45)}<h3>${tab==='messages'?'I tuoi messaggi':tab==='notifications'?'Le tue notifiche':'Area dimostrativa'}</h3><p>Questa sezione può essere personalizzata per un futuro scenario sperimentale.</p><button data-action="nav" data-tab="home">Torna al feed</button></div></section>`;
  const storyModal = () => {
    const item = stories[s.storyIndex];
    if (!item) return '';
    return `<div class="overlay story-overlay" data-close-overlay="true"><button class="overlay-close" data-action="close" aria-label="Chiudi">${ico('close',false,28)}</button><div class="story-view" role="dialog" aria-label="Storia"><div class="story-progress"><span></span></div><div class="story-view-header">${profileAvatar(item.image_url)}<strong>${escape(item.username)}</strong><span>ora</span></div>${item.image_url?`<img src="${escape(item.image_url)}" alt="Storia demo"/>`:''}<div class="story-caption">Un momento da condividere ✨</div><button class="story-next" data-action="next_story" aria-label="Storia successiva">${ico('chevron',false,30)}</button></div></div>`;
  };
  const modal = () => {
    if (!s.overlay) return '';
    if (s.overlay==='story') return storyModal();
    if (s.overlay==='post') {
      const p=postBy(s.overlayPost);if(!p) return '';
      return `<div class="overlay" data-close-overlay="true"><div class="post-modal" role="dialog" aria-label="Post"><button class="modal-close" data-action="close">${ico('close')}</button>${post(p)}</div></div>`;
    }
    const p=postBy(s.overlayPost);
    const title={post_more:'Opzioni del post',more:'Informazioni'}[s.overlay]||'Informazioni';
    return `<div class="overlay" data-close-overlay="true"><div class="simple-modal" role="dialog" aria-label="${title}"><h3>${title}</h3>
      ${s.overlay==='post_more' ? `<button class="modal-option" data-action="save" data-post="${escape(s.overlayPost)}">${ico('bookmark',false,20)} Salva / Rimuovi dai salvati</button>` : '<p>InstaLab è un prototipo per esperimenti sulla percezione dei contenuti social. Nessun collegamento reale con Instagram.</p>'}
       <button class="cancel" data-action="close">Annulla</button></div></div>`;
  };

  const render = () => {
    const y=window.scrollY;
    const body = s.tab==='home'?home():s.tab==='explore'?explore():s.tab==='saved'?explore(true):s.tab==='search'?search():s.tab==='profile'?profile():misc(s.tab);
    root.innerHTML = `<div class="instalab-shell"><div class="page-content">${body}</div>${modal()}</div>`;
    window.requestAnimationFrame(()=>window.scrollTo({top:y,behavior:'instant'}));
  };

  const perform = (btn) => {
    const action=btn.dataset.action;
    const id=btn.dataset.post||null;
    if(action==='nav') { s.tab=btn.dataset.tab; s.overlay=null; signal('navigate',null,{page:s.tab}); window.scrollTo(0,0); }
    else if(action==='like') {
      if(s.disliked.delete(id))signal('remove_dislike',id);
      if(s.liked.has(id)){s.liked.delete(id);signal('unlike',id);} else{s.liked.add(id);signal('like',id,{method:'button'});}
    }
    else if(action==='dislike') {
      if(s.liked.delete(id))signal('unlike',id);
      if(s.disliked.has(id)){s.disliked.delete(id);signal('remove_dislike',id);}else{s.disliked.add(id);signal('dislike',id);}
    }
    else if(action==='save') {
      if(s.saved.has(id)){s.saved.delete(id);signal('unsave',id);}else{s.saved.add(id);signal('save',id);}
      if(s.overlay==='post_more')s.overlay=null;
    }
    else if(action==='expand'){ s.expanded.add(id); signal('expand_comments',id); }
    else if(action==='open_comments') { const input=root.querySelector(`form[data-comment-post="${CSS.escape(id)}"] input`);if(input){input.focus();input.scrollIntoView({block:'center',behavior:'smooth'});}signal('open_comments',id);return; }
    else if(action==='follow') { const u=btn.dataset.user;if(s.followed.has(u)){s.followed.delete(u);signal('unfollow',null,{username:u});}else{s.followed.add(u);signal('follow',null,{username:u});} }
    else if(action==='profile') { signal('open_profile',null,{username:btn.dataset.user}); s.tab='profile';window.scrollTo(0,0); }
    else if(action==='story'){s.storyIndex=Number(btn.dataset.index)||0;s.overlay='story';signal('story_open',null,{username:stories[s.storyIndex]?.username});}
    else if(action==='next_story'){s.storyIndex=(s.storyIndex+1)%stories.length;signal('story_open',null,{username:stories[s.storyIndex]?.username});}
    else if(action==='post_more'||action==='more'){s.overlay=action;s.overlayPost=id;if(id)signal('open_'+action,id);}
    else if(action==='open_post'){s.overlay='post';s.overlayPost=id;signal('open_post',id);}
    else if(action==='close'){s.overlay=null;}
    else if(action==='more'){s.overlay='more';}
    render();
  };
  root.onclick = (e) => {
    const btn=e.target.closest('button[data-action]');
    if(btn&&root.contains(btn)){e.preventDefault();perform(btn);return;}
    if(e.target.matches('[data-close-overlay]')){s.overlay=null;render();}
  };
  root.onsubmit = (e) => {
    const form=e.target.closest('form[data-comment-post]'); if(!form)return;
    e.preventDefault();
    const id=form.dataset.commentPost, input=form.querySelector('input');
    const value=(input?.value||'').trim(); if(!value)return;
    (s.comments[id] ||= []).push({username:'you.research',text:value});
    signal('comment_submit',id,{text:value,length:value.length});
    render();
  };
  root.oninput = (e) => {
    if(e.target.matches('.search-input')) {
      const pos=e.target.selectionStart;
      s.query=e.target.value;
      const holder=root.querySelector('.search-results');
      if(holder)holder.innerHTML=posts.filter(p=>p.username.toLowerCase().includes(s.query.toLowerCase())||p.caption.toLowerCase().includes(s.query.toLowerCase())).map(p=>`<button class="search-result" data-action="open_post" data-post="${escape(p.id)}">${profileAvatar(p.avatar_url)}<span><strong>${escape(p.username)}</strong><small>${escape(p.location)}</small></span>${ico('chevron',false,18)}</button>`).join('');
    }
  };
  root.ondblclick = (e) => {
    const p=e.target.closest('[data-doublepost]');if(!p)return;
    const id=p.dataset.doublepost;
    if(s.disliked.delete(id))signal('remove_dislike',id);
    if(!s.liked.has(id)){s.liked.add(id);signal('like',id,{method:'double_click'});}
    const heart=p.querySelector('.burst-heart');if(heart){heart.classList.remove('animate');void heart.offsetWidth;heart.classList.add('animate');}
    // Update icon and count after the heart burst animation.
    window.setTimeout(()=>{if(root.isConnected)render();},300);
  };
  // Track first impressions for each post; exact dwell time needs experimental validation.
  if(typeof IntersectionObserver!=='undefined' && s.tab==='home' && !s.overlay){
    observer=new IntersectionObserver(entries=>{
      for(const entry of entries){
        const id=entry.target.getAttribute('data-post');
        if(entry.isIntersecting&&!s.seen.has(id)){
          s.seen.add(id);signal('post_impression',id,{threshold:0.6});
        }
      }
    },{threshold:0.6});
  }
  render();
  if(observer){root.querySelectorAll('article[data-post]').forEach(el=>observer.observe(el));}
  return () => { if(observer)observer.disconnect(); root.onclick=null;root.onsubmit=null;root.oninput=null;root.ondblclick=null; };
}
