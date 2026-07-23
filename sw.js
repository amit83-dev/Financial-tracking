/* Service worker אופציונלי ל"הכלי שלי לשוק ההון".
   מעלים אותו פעם אחת לצד index.html כדי לקבל עבודה לא מקוונת.
   האפליקציה עובדת מצוין גם בלעדיו — הוא רק מוסיף קאשינג. */
const CACHE = 'shukhon-v1';
const CORE  = ['./', './index.html'];

self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE).catch(()=>{})));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
         .then(() => self.clients.claim())
  );
});

/* network-first על הדף עצמו (כדי לקבל עדכונים), cache-first על השאר */
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const isDoc = req.mode === 'navigate' || (req.destination === 'document');
  if (isDoc) {
    e.respondWith(
      fetch(req).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put('./index.html', copy)).catch(()=>{});
        return res;
      }).catch(() => caches.match('./index.html').then(r => r || caches.match('./')))
    );
  } else {
    e.respondWith(
      caches.match(req).then(hit => hit || fetch(req).then(res => {
        if (res && res.status === 200 && res.type === 'basic') {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(req, copy)).catch(()=>{});
        }
        return res;
      }).catch(() => hit))
    );
  }
});
