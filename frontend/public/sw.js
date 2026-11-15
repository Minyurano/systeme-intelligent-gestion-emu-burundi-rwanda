/* UMURAGE — service worker : l'application s'ouvre et se consulte sans réseau.
   - Interface : mise en cache, la page s'ouvre même hors ligne.
   - API (lecture) : réseau d'abord, sinon la dernière réponse connue.
   - Le cache de l'API est effacé par l'application à chaque déconnexion (appareil partagé).
   - Les enregistrements faits hors ligne sont mis en file d'attente par l'application
     et envoyés au retour du réseau. */
const VERSION = "umurage-v3.9";
const COQUILLE = ["/", "/index.html", "/logo.svg", "/manifest.webmanifest", "/icone-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(COQUILLE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((cles) => Promise.all(cles.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return;

  // Fichiers de l'interface (noms uniques à chaque version) : cache d'abord
  if (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/static/")) {
    e.respondWith(
      caches.match(req).then((r) => r || fetch(req).then((rep) => {
        const copie = rep.clone();
        caches.open(VERSION).then((c) => c.put(req, copie));
        return rep;
      }))
    );
    return;
  }

  // Lectures de l'API : réseau d'abord, dernière réponse connue hors ligne
  if (url.pathname.startsWith("/api/") && !url.pathname.includes("/auth/")) {
    e.respondWith(
      fetch(req).then((rep) => {
        if (rep.ok) {
          const copie = rep.clone();
          caches.open(VERSION + "-api").then((c) => c.put(req, copie));
        }
        return rep;
      }).catch(() => caches.open(VERSION + "-api").then((c) => c.match(req, { ignoreVary: true })).then((r) => r || new Response(
        JSON.stringify({ detail: "Hors ligne : cette donnée n'a pas encore été consultée sur cet appareil." }),
        { status: 503, headers: { "Content-Type": "application/json" } }
      )))
    );
    return;
  }

  // Navigation : l'application elle-même
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).catch(() => caches.match("/index.html")));
  }
});
