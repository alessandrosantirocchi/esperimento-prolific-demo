// Timing is independent of rendering: the same tracker survives component reruns.
const FEED_TRACKING_VERSION = 1;
const feedEventId = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;

function feedOutbox(session, history) {
  const key = `instalab-outbox:${session}`;
  let pending = [];
  try { pending = JSON.parse(sessionStorage.getItem(key) || '[]'); } catch (_) {}
  if (!Array.isArray(pending)) pending = [];
  const acknowledged = new Set(history.map(e => e.event_id));
  pending = pending.filter(e => e && !acknowledged.has(e.event_id));
  const persist = () => { try {
    if (pending.length) sessionStorage.setItem(key, JSON.stringify(pending));
    else sessionStorage.removeItem(key);
  } catch (_) { /* In-memory events remain available if browser storage is blocked. */ } };
  persist();
  return {pending, push(event) {pending.push(event);persist();}};
}

function feedVisibleRatio(image) {
  if (!image.isConnected || image.dataset.decoded !== 'true' || !image.naturalWidth) return 0;
  const rect = image.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return 0;
  const viewport = window.visualViewport;
  let left = Math.max(rect.left, viewport?.offsetLeft || 0);
  let top = Math.max(rect.top, viewport?.offsetTop || 0);
  let right = Math.min(rect.right, (viewport?.offsetLeft || 0) + (viewport?.width || innerWidth));
  let bottom = Math.min(rect.bottom, (viewport?.offsetTop || 0) + (viewport?.height || innerHeight));
  // Include clipping by Streamlit's scrolling container, crossing shadow roots.
  for (let node = image; node; node = node.parentElement || node.getRootNode()?.host) {
    const style = getComputedStyle(node);
    if (style.visibility === 'hidden' || style.display === 'none') return 0;
    const box = node.getBoundingClientRect();
    if (node !== image && /auto|scroll|hidden|clip/.test(style.overflowX)) {
      left = Math.max(left, box.left);right = Math.min(right, box.right);
    }
    if (node !== image && /auto|scroll|hidden|clip/.test(style.overflowY)) {
      top = Math.max(top, box.top);bottom = Math.min(bottom, box.bottom);
    }
  }
  return Math.max(0, right-left) * Math.max(0, bottom-top) / (rect.width * rect.height);
}

function createFeedTracker(history) {
  const active = new Map(), indices = new Map();
  for (const e of history) if (e.event_type === 'feed_view') {
    indices.set(e.post_id, Math.max(indices.get(e.post_id) || 0, e.details?.exposure_index || 0));
  }
  let root, images, emit, observer, interval, frame, rendering = false;
  let focused = document.hasFocus(), attached = false;
  let started = history.some(e => e.event_type === 'feed_tracking_started');
  let finalized = history.some(e => e.event_type === 'feed_tracking_finalized');
  const report = (id, exposure, closed, reason, now = performance.now()) => emit('feed_view', id, {
    tracking_version: FEED_TRACKING_VERSION, exposure_id: exposure.id,
    exposure_index: exposure.index, started_client_ts: exposure.client,
    duration_ms: Math.max(0, Math.round(now-exposure.start)), closed, reason
  });
  const close = (id, reason, now) => {
    const exposure = active.get(id);
    if (!exposure) return;
    active.delete(id);report(id, exposure, true, reason, now);
  };
  const pause = reason => {
    const now = performance.now();
    for (const id of [...active.keys()]) close(id, reason, now);
  };
  const update = () => {
    if (finalized || rendering) return;
    const now = performance.now(), visible = new Set();
    if (root?.isConnected && !document.hidden && focused && document.hasFocus()) {
      for (const image of images()) if (feedVisibleRatio(image) >= 0.75) {
        const id = image.closest('article[data-post]')?.dataset.post;
        if (id) visible.add(id);
      }
    }
    for (const id of [...active.keys()]) if (!visible.has(id)) close(id, 'visibility_or_focus', now);
    for (const id of visible) if (!active.has(id)) {
      const index = (indices.get(id) || 0) + 1;
      indices.set(id, index);
      const exposure = {id: feedEventId(), index, start: now, client: new Date().toISOString()};
      active.set(id, exposure);report(id, exposure, false, 'start', now);
    }
  };
  const schedule = () => {if (!frame) frame = requestAnimationFrame(() => {frame = null;update();});};
  const blur = () => {focused = false;pause('blur');};
  const focus = () => {focused = true;update();};
  const visibility = () => {if (document.hidden) pause('hidden');else update();};
  const pagehide = () => pause('pagehide');
  const stop = () => {
    clearInterval(interval);cancelAnimationFrame(frame);frame = null;
    observer?.disconnect();
    document.removeEventListener('scroll', schedule, true);
    document.removeEventListener('visibilitychange', visibility);
    window.removeEventListener('resize', schedule);
    window.removeEventListener('blur', blur);window.removeEventListener('focus', focus);
    window.removeEventListener('pagehide', pagehide);
    window.visualViewport?.removeEventListener('resize', schedule);
    window.visualViewport?.removeEventListener('scroll', schedule);
    attached = false;
  };
  const tracker = {
    connect(nextRoot, getImages, signal) {
      root = nextRoot;images = getImages;emit = signal;
      if (finalized) return;
      if (!started) {started = true;emit('feed_tracking_started', null, {tracking_version: FEED_TRACKING_VERSION});}
      if (!attached) {
        attached = true;focused = document.hasFocus();
        document.addEventListener('scroll', schedule, {capture:true, passive:true});
        document.addEventListener('visibilitychange', visibility);
        window.addEventListener('resize', schedule);
        window.addEventListener('blur', blur);window.addEventListener('focus', focus);
        window.addEventListener('pagehide', pagehide);
        window.visualViewport?.addEventListener('resize', schedule);
        window.visualViewport?.addEventListener('scroll', schedule);
        if (typeof IntersectionObserver !== 'undefined') {
          observer = new IntersectionObserver(schedule, {threshold:[0, 0.75, 1]});
        }
        interval = setInterval(() => {
          update();
          for (const [id, exposure] of active) report(id, exposure, false, 'checkpoint');
          if (!root?.isConnected) {pause('unmount');stop();}
        }, 2000);
      }
    },
    beforeRender() {rendering = true;},
    afterRender() {
      if (finalized) return;
      rendering = false;observer?.disconnect();
      for (const image of images()) observer?.observe(image);
      update();
    },
    update,
    finalize() {
      if (finalized) return;
      update();pause('phase_end');finalized = true;stop();
      emit('feed_tracking_finalized', null, {tracking_version: FEED_TRACKING_VERSION});
    },
    cleanup() {setTimeout(() => {if (!root?.isConnected) {pause('unmount');stop();}}, 0);}
  };
  return tracker;
}
