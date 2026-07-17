self.addEventListener('push', function(e){
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch(err) {}
  e.waitUntil(self.registration.showNotification(d.title || 'RaoOS', {
    body: d.body || '',
    icon: 'icon-192.png',
    badge: 'icon-192.png',
    tag: d.tag || undefined,
    data: { url: (d.url || './') }
  }));
});

self.addEventListener('notificationclick', function(e){
  e.notification.close();
  var target = (e.notification.data && e.notification.data.url) || './';
  e.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(ws){
    for (var i = 0; i < ws.length; i++) {
      if (ws[i].url.indexOf('/life-os/') !== -1) { ws[i].navigate(target); return ws[i].focus(); }
    }
    return clients.openWindow(target);
  }));
});
