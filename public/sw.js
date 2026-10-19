/* ホーム画面アプリ用のしくみ（オフラインでも一度開いた教材は見られる） */
var VERSION = "gtore-v1";
var SHELL = [
  "./",
  "index.html",
  "style.css",
  "app.js",
  "materials.json",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/apple-touch-icon.png",
  "vendor/pdfjs/pdf.min.js",
  "vendor/pdfjs/pdf.worker.min.js"
];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (url.origin !== location.origin) return;   // Googleドライブなどはそのまま

  var p = url.pathname;
  var cacheFirst = /\/vendor\//.test(p);

  if (cacheFirst) {
    // PDF表示部品：変わらないので保存分をすぐ使う
    e.respondWith(
      caches.match(req).then(function (hit) {
        return hit || fetch(req).then(function (res) {
          if (res.ok) { var copy = res.clone(); caches.open(VERSION).then(function (c) { c.put(req, copy); }); }
          return res;
        });
      })
    );
    return;
  }

  // 画面・materials.json・PDF：いつも最新をとりにいき、つながらないときだけ保存分を使う
  // （同じファイル名でPDFを差しかえても、すぐ新しいほうが表示されます）
  e.respondWith(
    fetch(req).then(function (res) {
      if (res.ok) { var copy = res.clone(); caches.open(VERSION).then(function (c) { c.put(req, copy); }); }
      return res;
    }).catch(function () {
      return caches.match(req, { ignoreSearch: req.mode === "navigate" }).then(function (hit) {
        return hit || caches.match("index.html");
      });
    })
  );
});
