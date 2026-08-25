// Service worker Firebase Cloud Messaging — application PARENT (web).
// =====================================================================
//
// Obligatoire sur le web : sans ce fichier, `getToken()` peut réussir mais AUCUN message
// n'est délivré. L'erreur classique — « unsupported MIME type ('text/html') » — signifie
// simplement que le fichier est absent et que le serveur de dev renvoie index.html à sa place.
//
// Il est volontairement autonome : un service worker s'exécute hors de la page, il ne voit ni
// le bundle Flutter, ni `Env`, ni le jeton de session. D'où la configuration recopiée
// ci-dessous — elle est **publique** (elle part de toute façon dans le bundle du navigateur).
//
// La clé VAPID, elle, n'a rien à faire ici : elle est passée à `getToken()` côté application.

importScripts('https://www.gstatic.com/firebasejs/11.10.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/11.10.0/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: 'AIzaSyAZt9QIlQvMFaK_zIdlPuivjUfS0fKKx0o',
  authDomain: 'transport-scolaire-meknes.firebaseapp.com',
  projectId: 'transport-scolaire-meknes',
  storageBucket: 'transport-scolaire-meknes.firebasestorage.app',
  messagingSenderId: '780428837188',
  appId: '1:780428837188:web:96d69c6461cb0484dbd711',
});

const messaging = firebase.messaging();

// Message reçu alors que l'onglet n'a pas le focus. MS4 envoie une charge `notification`,
// que le navigateur afficherait seul ; on la reprend ici pour porter l'icône de l'application
// et pour regrouper par type — sinon dix arrivées de bus empilent dix bulles identiques.
messaging.onBackgroundMessage((payload) => {
  const n = payload.notification || {};
  const d = payload.data || {};
  self.registration.showNotification(n.title || 'Transport scolaire', {
    body: n.body || '',
    icon: '/icons/Icon-192.png',
    badge: '/icons/Icon-192.png',
    tag: d.type || 'transport',
    data: d,
  });
});

// Ramener l'onglet déjà ouvert au premier plan plutôt que d'en ouvrir un second.
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((liste) => {
      for (const c of liste) {
        if ('focus' in c) return c.focus();
      }
      return clients.openWindow('/');
    }),
  );
});
