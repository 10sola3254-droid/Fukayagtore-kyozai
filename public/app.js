/* =========================================================
   学習空間 深谷上柴教室 Gトレ教材
   ・教材の一覧は materials.json だけで管理します
   ・AI機能 / ログイン / データベースは使っていません
   ========================================================= */
(function () {
  "use strict";

  // 教科（表示の順番・アイコン文字）
  var SUBJECTS = [
    { name: "数学", icon: "数" },
    { name: "英語", icon: "英" },
    { name: "国語", icon: "国" },
    { name: "理科", icon: "理" },
    { name: "社会", icon: "社" }
  ];

  var view = document.getElementById("view");
  var crumbs = document.getElementById("crumbs");
  var backBtn = document.getElementById("backBtn");
  var navBar = document.getElementById("navBar");

  var DATA = null;      // { 教科名: [単元, ...] }
  var LOAD_ERROR = "";
  var currentPdfTask = null;

  /* ---------------- 文字のととのえ ---------------- */
  function norm(s) {
    return String(s == null ? "" : s).normalize("NFKC").replace(/\s+/g, " ").trim();
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* ---------------- 並び順 ---------------- */
  // 「中1」「中2」「中3」（小・高にも対応）→ 数字にする
  function gradeRank(name) {
    var m = norm(name).match(/^(小|中|高)\s*([0-9])/);
    if (!m) return 999;
    return { "小": 0, "中": 10, "高": 20 }[m[1]] + Number(m[2]);
  }
  function gradeLabel(name) {
    var m = norm(name).match(/^((?:小|中|高)\s*[0-9])/);
    return m ? m[1].replace(/\s/g, "") : "";
  }
  // 「3章-13・14」→ [3, 13]
  function chapterKey(name) {
    var m = norm(name).match(/^([0-9]+)\s*章\s*(?:[-‐－ー―]\s*([0-9]+))?/);
    if (!m) return null;
    return [Number(m[1]), m[2] ? Number(m[2]) : 0];
  }
  var collator = new Intl.Collator("ja", { numeric: true });

  function compareTopics(a, b) {
    var ka = chapterKey(a.title), kb = chapterKey(b.title);
    if (ka && !kb) return -1;          // 「○章-○○」があるものを先に
    if (!ka && kb) return 1;
    if (ka && kb) {
      if (ka[0] !== kb[0]) return ka[0] - kb[0];
      if (ka[1] !== kb[1]) return ka[1] - kb[1];
      var c = collator.compare(norm(a.title), norm(b.title));
      if (c) return c;
    }
    return a.order - b.order;          // それ以外は materials.json に書いた順
  }

  function unitChapter(unit) {
    var own = chapterKey(unit.name.replace(/^(?:小|中|高)\s*[0-9]\s*/, ""));
    if (own) return own[0];
    var min = Infinity;
    unit.topics.forEach(function (t) {
      var k = chapterKey(t.title);
      if (k && k[0] < min) min = k[0];
    });
    return min;
  }
  function compareUnits(a, b) {
    var g = gradeRank(a.name) - gradeRank(b.name);
    if (g) return g;
    var ca = unitChapter(a), cb = unitChapter(b);
    if (ca !== cb) return ca === Infinity ? 1 : cb === Infinity ? -1 : ca - cb;
    return a.order - b.order;
  }

  // 細かい単元名を「3章-13・14」と「一次関数の式の求め方」に分ける
  function splitTopic(title) {
    var m = String(title).match(/^\s*([0-9０-９]+\s*章\s*[-‐－ー―]\s*\S+)[\s　]+(.+)$/);
    if (m) return { code: m[1], text: m[2] };
    return { code: "", text: title };
  }

  /* ---------------- materials.json を読む ---------------- */
  function pick(obj, keys) {
    for (var i = 0; i < keys.length; i++) {
      if (obj[keys[i]] != null) return String(obj[keys[i]]);
    }
    return "";
  }

  function buildData(list) {
    if (list && !Array.isArray(list)) list = list["教材"] || list.materials || [];
    var bySubject = {};
    SUBJECTS.forEach(function (s) { bySubject[s.name] = []; });

    list.forEach(function (row, i) {
      if (!row || typeof row !== "object") return;
      var subject = norm(pick(row, ["教科", "subject"]));
      var unitName = String(pick(row, ["単元", "unit"])).trim();
      var title = String(pick(row, ["細かい単元", "topic", "title"])).trim();
      var url = String(pick(row, ["URL", "url"])).trim();
      if (!subject || !unitName || !title) return;
      if (!bySubject[subject]) {
        console.warn("materials.json: 知らない教科名です →", subject, "（数学・英語・国語・理科・社会のどれかにしてください）");
        return;
      }
      var units = bySubject[subject];
      var unit = null;
      for (var j = 0; j < units.length; j++) {
        if (norm(units[j].name) === norm(unitName)) { unit = units[j]; break; }
      }
      if (!unit) { unit = { name: unitName, topics: [], order: i }; units.push(unit); }
      unit.topics.push({ title: title, url: url, order: i });
    });

    Object.keys(bySubject).forEach(function (s) {
      bySubject[s].forEach(function (u) { u.topics.sort(compareTopics); });
      bySubject[s].sort(compareUnits);
    });
    return bySubject;
  }

  function loadData() {
    return fetch("materials.json", { cache: "no-cache" })
      .then(function (res) {
        if (!res.ok) throw new Error("materials.json が読みこめませんでした（" + res.status + "）");
        return res.text();
      })
      .then(function (text) {
        var json;
        try {
          json = JSON.parse(text.replace(/^﻿/, ""));
        } catch (e) {
          var pos = (String(e.message).match(/position\s+(\d+)/) || [])[1];
          var line = pos ? text.slice(0, Number(pos)).split("\n").length : null;
          throw new Error("materials.json の書き方にまちがいがあります" +
            (line ? "（" + line + "行目あたり）" : "") +
            "。\n「,」のつけ忘れ・つけすぎや、「\"」の閉じ忘れがないか確認してください。");
        }
        DATA = buildData(json);
      })
      .catch(function (e) {
        LOAD_ERROR = e.message || String(e);
        DATA = buildData([]);
      });
  }

  /* ---------------- URL（PDFの場所）を調べる ---------------- */
  function resolveMaterial(raw) {
    var url = String(raw || "").trim();
    if (!url) return null;

    // (b) Googleドライブの共有リンク → スマホで見やすいプレビュー表示
    if (/^https?:\/\/(drive|docs)\.google\.com\//i.test(url)) {
      var id = (url.match(/\/d\/([a-zA-Z0-9_-]{10,})/) || url.match(/[?&]id=([a-zA-Z0-9_-]{10,})/) || [])[1];
      if (id) {
        var isDocs = /docs\.google\.com\/(document|spreadsheets|presentation)\//i.exec(url);
        var base = isDocs
          ? "https://docs.google.com/" + isDocs[1] + "/d/" + id
          : "https://drive.google.com/file/d/" + id;
        return { type: "drive", embed: base + "/preview", open: base + "/view" };
      }
      return { type: "link", open: url };
    }

    // その他のWebサイトのURL
    if (/^https?:\/\//i.test(url)) return { type: "link", open: url };

    // (a) public/materials フォルダのPDF
    var path = url.replace(/^\.?\//, "").replace(/^public\//, "");
    if (path.indexOf("/") === -1) path = "materials/" + path;   // ファイル名だけでもOK
    // HTMLで作った教材（音声つきの教材など）→ アプリの中で表示
    if (/\.html?$/i.test(path)) return { type: "page", src: encodeURI(decodeURI(path)), open: encodeURI(decodeURI(path)) };
    return { type: "pdf", src: encodeURI(decodeURI(path)), open: encodeURI(decodeURI(path)) };
  }

  /* ---------------- 画面の場所（ルート） ---------------- */
  function findSubject(name) {
    var n = norm(name);
    for (var i = 0; i < SUBJECTS.length; i++) if (SUBJECTS[i].name === n) return SUBJECTS[i].name;
    return null;
  }
  function findByName(items, name, getName) {
    var n = norm(name);
    if (!n) return null;
    var exact = items.filter(function (it) { return norm(getName(it)) === n; });
    if (exact.length) return exact[0];
    // 一部だけでも、1つにしぼれれば開く（QRコードの打ちまちがい対策）
    var part = items.filter(function (it) { return norm(getName(it)).indexOf(n) !== -1; });
    return part.length === 1 ? part[0] : null;
  }

  function routeFromURL() {
    var q = new URLSearchParams(location.search);
    var r = { subject: null, unit: null, topic: null, missing: "" };
    var s = q.get("subject");
    if (!s) return r;
    r.subject = findSubject(s);
    if (!r.subject) { r.missing = "教科「" + s + "」"; return r; }
    var u = q.get("unit");
    if (!u) return r;
    var unit = findByName(DATA[r.subject], u, function (x) { return x.name; });
    if (!unit) { r.missing = "単元「" + u + "」"; return r; }
    r.unit = unit;
    var t = q.get("topic");
    if (!t) return r;
    var byCode = unit.topics.filter(function (x) { return norm(splitTopic(x.title).code) === norm(t); });
    var topic = byCode.length === 1 ? byCode[0] : findByName(unit.topics, t, function (x) { return x.title; });
    if (!topic) { r.missing = "細かい単元「" + t + "」"; return r; }
    r.topic = topic;
    return r;
  }

  function urlFor(subject, unit, topic) {
    var q = new URLSearchParams();
    if (subject) q.set("subject", subject);
    if (unit) q.set("unit", unit.name);
    if (topic) q.set("topic", topic.title);
    var s = q.toString();
    return location.pathname + (s ? "?" + s : "");
  }

  // 次の画面へ（スマホの「戻る」操作でも1つ前にもどれる）
  function go(subject, unit, topic) {
    var cur = routeFromURL();
    var d = depthOf(subject, unit, topic);
    var fromParent = d === depthOf(cur.subject, cur.unit, cur.topic) + 1;   // 1つ下の画面へ進んだとき
    history.pushState({ app: true, depth: d, fromParent: fromParent }, "", urlFor(subject, unit, topic));
    render(true);
  }
  function depthOf(s, u, t) { return t ? 3 : u ? 2 : s ? 1 : 0; }

  // 「もどる」ボタン：1つ上の画面へ
  function goUp() {
    var r = routeFromURL();
    var parent;
    if (r.topic) parent = [r.subject, r.unit, null];
    else if (r.unit) parent = [r.subject, null, null];
    else parent = [null, null, null];
    var st = history.state;
    if (st && st.app && st.depth === depthOf(r.subject, r.unit, r.topic) && st.depth > 0 && st.fromParent) {
      history.back();
    } else {
      history.replaceState({ app: true, depth: depthOf(parent[0], parent[1], parent[2]) }, "", urlFor(parent[0], parent[1], parent[2]));
      render(true);
    }
  }

  /* ---------------- 画面をつくる ---------------- */
  function setCrumbs(r) {
    var items = [];
    var hasMore = !!r.subject;
    items.push(hasMore ? '<li><a href="' + esc(urlFor()) + '" data-go="home">ホーム</a></li>' : '<li aria-current="page">ホーム</li>');
    if (r.subject) {
      items.push(r.unit
        ? '<li><a href="' + esc(urlFor(r.subject)) + '" data-go="subject">' + esc(r.subject) + "</a></li>"
        : '<li aria-current="page">' + esc(r.subject) + "</li>");
    }
    if (r.unit) {
      items.push(r.topic
        ? '<li><a href="' + esc(urlFor(r.subject, r.unit)) + '" data-go="unit">' + esc(r.unit.name) + "</a></li>"
        : '<li aria-current="page">' + esc(r.unit.name) + "</li>");
    }
    if (r.topic) {
      var sp = splitTopic(r.topic.title);
      items.push('<li aria-current="page">' + esc(sp.code || sp.text) + "</li>");
    }
    crumbs.innerHTML = items.join("");
    crumbs.querySelectorAll("a[data-go]").forEach(function (a) {
      a.addEventListener("click", function (ev) {
        ev.preventDefault();
        var g = a.getAttribute("data-go");
        if (g === "home") go(null);
        else if (g === "subject") go(r.subject);
        else go(r.subject, r.unit);
      });
    });
  }

  function render(fromNav) {
    stopPdf();
    var r = routeFromURL();
    document.body.setAttribute("data-subject", r.subject || "");
    var screen = r.topic ? "viewer" : r.unit ? "topics" : r.subject ? "units" : "home";
    document.body.setAttribute("data-screen", screen);
    setCrumbs(r);

    var notice = "";
    if (r.missing) notice = '<p class="notice">' + esc(r.missing) + " が見つかりませんでした。下から選んでください。</p>";
    if (LOAD_ERROR) notice = '<p class="notice error">' + esc(LOAD_ERROR) + "</p>" + notice;

    if (screen === "home") renderHome(notice);
    else if (screen === "units") renderUnits(r, notice);
    else if (screen === "topics") renderTopics(r, notice);
    else renderViewer(r);

    var titles = { home: "", units: r.subject, topics: r.unit && r.unit.name, viewer: r.topic && r.topic.title };
    document.title = (titles[screen] ? titles[screen] + "｜" : "") + "学習空間 深谷上柴教室　Gトレ教材";
    if (fromNav) { window.scrollTo(0, 0); view.focus({ preventScroll: true }); }
    updateBarHeight();
  }

  function renderHome(notice) {
    var html = notice + '<h1 class="screen-title">教科をえらぼう</h1><ul class="list">';
    SUBJECTS.forEach(function (s) {
      var units = DATA[s.name];
      var empty = units.length === 0;
      html += '<li><button type="button" class="subject-btn' + (empty ? " is-empty" : "") + '" data-s="' + s.name + '"' +
        (empty ? ' aria-disabled="true"' : "") + ">" +
        '<span class="subject-icon" aria-hidden="true">' + s.icon + "</span>" +
        '<span class="subject-name">' + s.name + "</span>" +
        '<span class="subject-meta">' +
        (empty ? '<span class="chip">準備中</span>' : units.length + '単元<span class="chev" aria-hidden="true">›</span>') +
        "</span></button></li>";
    });
    html += "</ul>" + installCardHTML() +
      '<button type="button" class="qr-open-btn" id="qrOpenBtn">' +
      '<span class="qr-open-icon" aria-hidden="true">' + QR_ICON_SVG + "</span>" +
      '<span class="qr-open-text"><strong>QRコードを表示</strong>ほかの端末でも開けます</span>' +
      '<span class="chev" aria-hidden="true">›</span></button>';
    view.innerHTML = html;
    view.querySelectorAll(".subject-btn").forEach(function (b) {
      b.addEventListener("click", function () {
        if (b.classList.contains("is-empty")) return;
        go(b.getAttribute("data-s"));
      });
    });
    document.getElementById("qrOpenBtn").addEventListener("click", openQrSheet);
    wireInstallCard();
  }

  /* ---------------- ほかの端末で開く（QRコード） ---------------- */
  var QR_ICON_SVG = '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round">' +
    '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>' +
    '<path d="M14 14h3v3h-3zM20 14v.01M14 20h.01M17 20h4v-3" stroke-linecap="round"/></svg>';

  function appHomeURL() {
    // 教科などの選択をふくまない、アプリのトップのURL
    return location.origin + location.pathname.replace(/index\.html$/, "");
  }

  function qrSvg(text) {
    if (typeof qrcode !== "function") return "";
    var q = qrcode(0, "M");
    q.addData(text);
    q.make();
    return q.createSvgTag({ cellSize: 1, margin: 2, scalable: true });
  }

  function openQrSheet() {
    var old = document.getElementById("qrSheet");
    if (old) old.remove();
    var url = appHomeURL();
    var svg = qrSvg(url);
    var opener = document.activeElement;
    var sheet = document.createElement("div");
    sheet.className = "qr-sheet";
    sheet.id = "qrSheet";
    sheet.innerHTML =
      '<div class="qr-panel" role="dialog" aria-modal="true" aria-labelledby="qrTitle">' +
      '<button type="button" class="install-close qr-close" id="qrClose" aria-label="とじる">×</button>' +
      '<h2 class="qr-title" id="qrTitle">ほかの端末で開く</h2>' +
      '<p class="qr-lead">開きたいスマホ・タブレットのカメラで読みとってください。</p>' +
      (svg ? '<div class="qr-code">' + svg + "</div>"
           : '<p class="notice error">QRコードを作れませんでした。下のURLを使ってください。</p>') +
      '<p class="qr-url">' + esc(url) + "</p>" +
      '<button type="button" class="qr-copy" id="qrCopy">URLをコピー</button>' +
      "</div>";
    document.body.appendChild(sheet);
    document.body.classList.add("has-sheet");

    function close() {
      document.removeEventListener("keydown", onKey);
      sheet.remove();
      document.body.classList.remove("has-sheet");
      if (opener && opener.focus) opener.focus();
    }
    function onKey(e) { if (e.key === "Escape") close(); }
    document.addEventListener("keydown", onKey);
    sheet.addEventListener("click", function (e) { if (e.target === sheet) close(); });
    document.getElementById("qrClose").addEventListener("click", close);

    var copyBtn = document.getElementById("qrCopy");
    copyBtn.addEventListener("click", function () {
      var done = function () { copyBtn.textContent = "コピーしました ✓"; };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(done, function () { fallbackCopy(url); done(); });
      } else { fallbackCopy(url); done(); }
    });
    document.getElementById("qrClose").focus();
  }

  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    ta.remove();
  }

  function renderUnits(r, notice) {
    var units = DATA[r.subject];
    var html = notice + '<h1 class="screen-title">' + esc(r.subject) + "：単元をえらぼう</h1>";
    if (!units.length) {
      view.innerHTML = html + '<p class="empty">この教科の教材は準備中です。</p>';
      return;
    }
    // 学年ごとにまとめる
    var groups = [];
    units.forEach(function (u, idx) {
      var g = gradeLabel(u.name) || "その他";
      var last = groups[groups.length - 1];
      if (!last || last.label !== g) groups.push(last = { label: g, units: [] });
      last.units.push({ u: u, idx: idx });
    });
    groups.forEach(function (g) {
      html += '<section class="grade-group"><h2 class="grade-label">' + esc(g.label) + '</h2><ul class="list">';
      g.units.forEach(function (x) {
        var u = x.u;
        var ready = u.topics.filter(function (t) { return !!resolveMaterial(t.url); }).length;
        var shown = u.name.replace(/^(?:小|中|高)\s*[0-9]\s*/, "") || u.name;
        var note = "教材 " + u.topics.length + "つ" + (ready && ready < u.topics.length ? "（準備中 " + (u.topics.length - ready) + "）" : "");
        html += '<li><button type="button" class="item-btn" data-i="' + x.idx + '">' +
          '<span class="item-main"><span class="item-title">' + esc(shown) + '</span><span class="item-note">' + esc(note) + "</span></span>" +
          '<span class="item-right">' + (ready ? '<span class="chev" aria-hidden="true">›</span>' : '<span class="chip">準備中</span>') + "</span>" +
          "</button></li>";
      });
      html += "</ul></section>";
    });
    view.innerHTML = html;
    view.querySelectorAll(".item-btn").forEach(function (b) {
      b.addEventListener("click", function () { go(r.subject, units[Number(b.getAttribute("data-i"))]); });
    });
  }

  function renderTopics(r, notice) {
    var html = notice + '<h1 class="screen-title">' + esc(r.unit.name) + '</h1><p class="screen-sub">開きたい教材をえらぼう</p><ul class="list">';
    r.unit.topics.forEach(function (t, i) {
      var sp = splitTopic(t.title);
      var ok = !!resolveMaterial(t.url);
      html += '<li><button type="button" class="item-btn topic' + (ok ? "" : " is-soon") + '" data-i="' + i + '"' + (ok ? "" : ' aria-disabled="true"') + ">" +
        '<span class="item-main">' + (sp.code ? '<span class="topic-code">' + esc(sp.code) + "</span>" : "") +
        '<span class="item-title">' + esc(sp.text) + "</span></span>" +
        '<span class="item-right">' + (ok ? '<span class="open-pill">開く<span aria-hidden="true">›</span></span>' : '<span class="chip">準備中</span>') + "</span>" +
        "</button></li>";
    });
    html += "</ul>";
    view.innerHTML = html;
    view.querySelectorAll(".item-btn").forEach(function (b) {
      b.addEventListener("click", function () {
        if (b.classList.contains("is-soon")) return;
        go(r.subject, r.unit, r.unit.topics[Number(b.getAttribute("data-i"))]);
      });
    });
  }

  /* ---------------- PDFを表示 ---------------- */
  function renderViewer(r) {
    var m = resolveMaterial(r.topic.url);
    var sp = splitTopic(r.topic.title);
    var label = esc(sp.code ? sp.code + " " + sp.text : sp.text);

    if (!m) {
      view.innerHTML = '<div class="viewer-msg"><p>この教材は<strong>準備中</strong>です。</p><p>' + label + "</p></div>";
      return;
    }
    if (m.type === "link") {
      view.innerHTML = '<div class="viewer-msg"><p>' + label + '</p><a class="big-link" href="' + esc(m.open) +
        '" target="_blank" rel="noopener">教材を開く</a></div>';
      return;
    }
    if (m.type === "drive") {
      view.innerHTML =
        '<div class="viewer-tools"><span class="viewer-title">' + label + "</span>" +
        '<a class="tool-btn text" href="' + esc(m.open) + '" target="_blank" rel="noopener">ドライブで開く</a></div>' +
        '<div class="drive-wrap"><iframe class="drive-frame" src="' + esc(m.embed) + '" title="' + label +
        '" allow="autoplay; fullscreen" loading="eager"></iframe></div>';
      sizeDriveFrame();
      return;
    }
    if (m.type === "page") {
      view.innerHTML =
        '<div class="viewer-tools"><span class="viewer-title">' + label + "</span>" +
        '<a class="tool-btn text" href="' + esc(m.open) + '" target="_blank" rel="noopener">別画面</a></div>' +
        '<div class="drive-wrap"><iframe class="drive-frame" src="' + esc(m.src) + '" title="' + label +
        '" allow="autoplay" loading="eager"></iframe></div>';
      sizeDriveFrame();
      return;
    }
    // (a) materials フォルダのPDF → アプリの中でページを表示
    view.innerHTML =
      '<div class="viewer-tools">' +
      '<span class="viewer-title" id="pgInfo">' + label + "</span>" +
      '<button type="button" class="tool-btn" id="zoomOut" aria-label="小さくする">－</button>' +
      '<button type="button" class="tool-btn" id="zoomIn" aria-label="大きくする">＋</button>' +
      '<button type="button" class="tool-btn print-btn" id="printBtn" aria-label="印刷" disabled>' + PRINT_ICON_SVG + "<span>印刷</span></button>" +
      '<a class="tool-btn text" href="' + esc(m.open) + '" target="_blank" rel="noopener" id="openBtn">別画面</a>' +
      '<div class="set-row" id="setRow">' +
      '<div class="set-tabs" id="setTabs" role="tablist" aria-label="教材の種類" hidden></div>' +
      '<a class="dl-btn" id="dlBtn" href="' + esc(m.src) + '" download="' + esc(dlName(r.topic.title, "")) + '">' +
      DL_ICON_SVG + "<span>ダウンロード</span></a></div>" +
      "</div>" +
      '<div class="pdf-pages" id="pdfPages"></div>';
    document.getElementById("printBtn").addEventListener("click", openPrintSheet);

    var topic = r.topic;
    loadSets(m).then(function (sets) {
      if (routeFromURL().topic !== topic) return;   // もう別の画面に移っている
      var want = new URLSearchParams(location.search).get("set");
      if (sets) {
        var tabs = document.getElementById("setTabs");
        var all = [{ key: "", name: "全部", desc: "まとめ・A問題・B問題すべて" }].concat(sets);
        tabs.innerHTML = all.map(function (x) {
          return '<button type="button" role="tab" data-set="' + esc(x.key) + '" title="' + esc(x.desc) + '">' + esc(x.name) + "</button>";
        }).join("");
        tabs.hidden = false;
        tabs.addEventListener("click", function (e) {
          var b = e.target.closest("[data-set]");
          if (b) choose(b.getAttribute("data-set"), true);
        });
      }
      // A問題・B問題に分けていない教材は、この行を出さない（ダウンロードは理科の分けた教材だけ）
      if (!sets) document.getElementById("setRow").remove();
      var start = sets && sets.some(function (x) { return x.key === want; }) ? want : "";
      choose(start, false);

      function choose(key, fromTap) {
        var set = sets && sets.filter(function (x) { return x.key === key; })[0];
        var mm = set ? { type: "pdf", src: m.src.replace(/[^/]+$/, encodeURI(set.file)), open: m.open.replace(/[^/]+$/, encodeURI(set.file)) } : m;
        if (sets) {
          document.querySelectorAll("#setTabs [data-set]").forEach(function (b) {
            b.setAttribute("aria-selected", String(b.getAttribute("data-set") === key));
          });
          var q = new URLSearchParams(location.search);
          if (key) q.set("set", key); else q.delete("set");
          history.replaceState(history.state, "", location.pathname + "?" + q.toString());
        }
        var dl = document.getElementById("dlBtn");
        if (dl) {
          dl.href = mm.src;
          dl.setAttribute("download", dlName(topic.title, set ? set.name : ""));
          dl.setAttribute("aria-label", (set ? set.name : "全部") + "をダウンロード");
        }
        document.getElementById("openBtn").href = mm.open;
        if (fromTap && currentPdfTask && currentPdfTask.material && currentPdfTask.material.src === mm.src) return;

        // 前の教材を片づけてから開きなおす
        stopPdf();
        var oldBar = document.getElementById("quizBar");
        if (oldBar) oldBar.remove();
        ["zoomIn", "zoomOut"].forEach(function (id) {
          var b = document.getElementById(id);
          b.replaceWith(b.cloneNode(true));
        });
        document.getElementById("printBtn").disabled = true;
        document.getElementById("pgInfo").innerHTML = label;
        document.getElementById("pdfPages").innerHTML =
          '<div class="viewer-msg" id="pdfMsg"><div class="spinner"></div>読みこみ中…</div><div class="pdf-stack" id="pdfStack"></div>';
        if (fromTap) window.scrollTo(0, 0);
        openPdf(mm, label);
      }
    });
  }

  /* ---------------- 理科：まとめ＋A問題／まとめ＋B問題 の切りかえとダウンロード ---------------- */
  // PDFと同じ名前の .sets.json があるときだけ「全部／A問題／B問題」のボタンが出ます（tools/split_rika.py で作成）
  function loadSets(m) {
    var url = m.src.replace(/\.pdf$/i, ".sets.json");
    if (url === m.src) return Promise.resolve(null);
    return fetch(url, { cache: "no-cache" })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (j) { return j && j.sets && j.sets.length ? j.sets : null; })
      .catch(function () { return null; });
  }

  function dlName(title, setName) {
    var t = String(title || "教材").replace(/[\\/:*?"<>|]/g, "・").trim();
    return "Gトレ_" + t + (setName ? "（" + setName + "）" : "") + ".pdf";
  }

  var DL_ICON_SVG = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>';

  function sizeDriveFrame() {
    var f = view.querySelector(".drive-frame");
    if (!f) return;
    var top = f.getBoundingClientRect().top + window.scrollY;
    f.style.height = Math.max(420, window.innerHeight - top) + "px";
  }

  function stopPdf() {
    clearPrintArea();
    var ps = document.getElementById("printSheet");
    if (ps) { ps.remove(); document.body.classList.remove("has-sheet"); }
    document.body.classList.remove("has-quiz"); document.body.classList.remove("quiz-many");
    if (currentPdfTask) { currentPdfTask.cancelled = true; currentPdfTask.cleanup(); currentPdfTask = null; }
  }

  function openPdf(m, label) {
    var task = { cancelled: false, observers: [], doc: null, zoom: 1, pages: [], cleanup: function () {
      task.observers.forEach(function (o) { o.disconnect(); });
      window.removeEventListener("resize", task.onResize);
      if (task.doc) task.doc.destroy();
    } };
    task.material = m;
    currentPdfTask = task;
    var msg = document.getElementById("pdfMsg");
    var stack = document.getElementById("pdfStack");
    var info = document.getElementById("pgInfo");

    function fail(text) {
      if (task.cancelled) return;
      msg.innerHTML = '<p class="notice error">' + text + '</p><a class="big-link" href="' + esc(m.open) + '" target="_blank" rel="noopener">PDFをそのまま開く</a>';
    }

    if (!window.pdfjsLib) { fail("PDFを表示する部品が読みこめませんでした。"); return; }
    pdfjsLib.GlobalWorkerOptions.workerSrc = "vendor/pdfjs/pdf.worker.min.js";

    fetch(m.src).then(function (res) {
      if (!res.ok) throw new Error(res.status === 404
        ? "PDFファイルが見つかりません。\n（" + decodeURI(m.src) + "）\nファイル名と materials.json のURLが同じか確認してください。"
        : "PDFが読みこめませんでした（" + res.status + "）");
      return res.arrayBuffer();
    }).then(function (buf) {
      if (task.cancelled) return;
      return pdfjsLib.getDocument({
        data: buf,
        cMapUrl: "vendor/pdfjs/cmaps/",
        cMapPacked: true,
        standardFontDataUrl: "vendor/pdfjs/standard_fonts/"
      }).promise;
    }).then(function (doc) {
      if (!doc || task.cancelled) { if (doc) doc.destroy(); return; }
      task.doc = doc;
      msg.remove();
      var pb = document.getElementById("printBtn");
      if (pb) pb.disabled = false;
      return setupPages(task, doc, stack, info, label).then(function () { return initQuiz(task, m); });
    }).catch(function (e) {
      fail(esc(e && e.message ? e.message : "PDFが読みこめませんでした。"));
    });
  }

  function setupPages(task, doc, stack, info, label) {
    var n = doc.numPages;
    var visible = new Set();
    var chain = Promise.resolve();
    for (var i = 1; i <= n; i++) {
      (function (num) {
        chain = chain.then(function () { return doc.getPage(num); }).then(function (page) {
          if (task.cancelled) return;
          var vp = page.getViewport({ scale: 1 });
          var box = document.createElement("div");
          box.className = "pdf-page";
          box.style.aspectRatio = vp.width + " / " + vp.height;
          stack.appendChild(box);
          task.pages.push({ num: num, page: page, box: box, canvas: null, renderedWidth: 0, rendering: null });
        });
      })(i);
    }
    return chain.then(function () {
      if (task.cancelled) return;
      applyZoom(task, stack);

      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          var p = task.pages.find(function (x) { return x.box === en.target; });
          if (!p) return;
          if (en.isIntersecting) { visible.add(p); renderPage(task, p); } else visible.delete(p);
        });
        // ページ番号表示
        var nums = Array.from(visible).map(function (p) { return p.num; }).sort(function (a, b) { return a - b; });
        if (nums.length) info.textContent = nums[0] + " / " + n + " ページ";
      }, { rootMargin: "600px 0px" });
      task.pages.forEach(function (p) { io.observe(p.box); });
      task.observers.push(io);

      var zoomTimer;
      function rerender() {
        clearTimeout(zoomTimer);
        zoomTimer = setTimeout(function () { visible.forEach(function (p) { renderPage(task, p); }); }, 150);
      }
      document.getElementById("zoomIn").addEventListener("click", function () {
        task.zoom = Math.min(3, Math.round((task.zoom + 0.25) * 100) / 100); applyZoom(task, stack); rerender();
      });
      document.getElementById("zoomOut").addEventListener("click", function () {
        task.zoom = Math.max(1, Math.round((task.zoom - 0.25) * 100) / 100); applyZoom(task, stack); rerender();
      });
      task.onResize = function () { applyZoom(task, stack); rerender(); };
      window.addEventListener("resize", task.onResize);
      if (!task.pages.length) info.textContent = label;
    });
  }


  /* ---------------- ○×チェック（確認問題 → 解説 → チェックテスト） ----------------
     PDFと同じ名前の .json（位置データ）があるときだけ動きます。
     ・確認問題の下の表をタップして ○ × をつける
     ・×の単元の解説に色がつく → 読み終えたらチェックテストへ → ×の番号の問題に色がつく
     ・記録はこのスマホの中だけに残ります（ログイン・サーバーなし）            */
  var CIRC = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫";

  function loadQuizState(key) {
    try {
      var v = JSON.parse(localStorage.getItem(key) || "null");
      if (v && v.marks) return v;
    } catch (e) {}
    return { marks: {}, phase: "mark" };
  }
  function saveQuizState(q) {
    try { localStorage.setItem(q.key, JSON.stringify(q.st)); } catch (e) {}
  }

  function initQuiz(task, m) {
    var url = m.src.replace(/\.pdf$/i, ".json");
    if (url === m.src) return;
    return fetch(url, { cache: "no-cache" }).then(function (res) {
      return res.ok ? res.json() : null;
    }).then(function (cfg) {
      if (!cfg || task.cancelled || !cfg.questions || !cfg.questions.length) return;
      task.quiz = { cfg: cfg, key: "gtore-quiz:" + m.src, st: null, resetArmed: false };
      task.quiz.st = loadQuizState(task.quiz.key);
      document.body.classList.add("has-quiz");
      buildQuizBar(task);
      refreshQuiz(task);
    }).catch(function () {});
  }

  function quizWrong(q) {
    return q.cfg.questions.filter(function (x) { return q.st.marks[x.n] === "x"; });
  }

  function placeRect(el, r) {
    el.style.left = (r.x * 100) + "%";
    el.style.top = (r.y * 100) + "%";
    el.style.width = (r.w * 100) + "%";
    el.style.height = (r.h * 100) + "%";
  }

  function mkEl(cls, text) {
    var d = document.createElement("div");
    d.className = cls;
    if (text) d.textContent = text;
    return d;
  }

  function renderQuizLayers(task) {
    var q = task.quiz, cfg = q.cfg, st = q.st;
    var wrong = quizWrong(q);
    var wrongUnits = {};
    wrong.forEach(function (x) { (wrongUnits[x.unit] = wrongUnits[x.unit] || []).push(x); });

    task.pages.forEach(function (p) {
      var old = p.box.querySelector(".quiz-layer");
      if (old) old.remove();
      var layer = mkEl("quiz-layer");
      var any = false;

      // 確認問題の表：○×のマス
      if (p.num === cfg.pages.quiz) {
        (cfg.cells || []).forEach(function (c) {
          var b = document.createElement("button");
          b.type = "button";
          b.className = "q-cell";
          b.setAttribute("aria-label", (cfg.mode === "hokushin" ? "問題" + c.n : "確認問題" + CIRC[c.n - 1]) + " " + ({ o: "○", x: "×" }[st.marks[c.n]] || "まだ"));
          placeRect(b, c);
          var mark = st.marks[c.n];
          if (mark) {
            var g = mkEl("q-glyph " + mark, mark === "o" ? "○" : "×");
            b.appendChild(g);
          }
          b.addEventListener("click", function () { cycleMark(task, c.n); });
          layer.appendChild(b);
          any = true;
        });
      }

      // 解説：×だった問題の単元に色をつける
      if (st.phase === "explain" || st.phase === "test") {
        (cfg.explain || []).forEach(function (e) {
          if (e.page !== p.num) return;
          // e.for：この解説を読むべき問題の番号（位置データに入っている）
          var hit = e.for ? wrong.filter(function (x) { return e.for.indexOf(x.n) !== -1; }) : (wrongUnits[e.unit] || []);
          if (!hit.length) return;
          var nums = hit.map(function (x) { return CIRC[x.n - 1]; }).join("");
          var area = mkEl("hl hl-area hl-explain");
          placeRect(area, e.area);
          var head = mkEl("hl hl-head hl-explain");
          placeRect(head, e.heading);
          head.appendChild(mkEl("hl-badge", "確認問題" + nums + "が × → ここを読もう"));
          layer.appendChild(area); layer.appendChild(head);
          any = true;
        });
      }

      // チェックテスト：×だった番号の問題に色をつける
      if (st.phase === "test") {
        (cfg.test || []).forEach(function (t) {
          if (t.page !== p.num || st.marks[t.n] !== "x") return;
          var box = mkEl("hl hl-area hl-test");
          placeRect(box, t.rect);
          box.appendChild(mkEl("hl-badge", "確認問題" + CIRC[t.n - 1] + "が ×"));
          layer.appendChild(box);
          any = true;
        });
      }

      if (any) p.box.appendChild(layer);
    });
  }

  function cycleMark(task, n) {
    var q = task.quiz, cur = q.st.marks[n];
    var next = !cur ? "o" : cur === "o" ? "x" : null;
    if (next) q.st.marks[n] = next; else delete q.st.marks[n];
    // ○×を変えたら、まず解説の段階からやり直し（色がずれないように）
    if (q.st.phase === "test") q.st.phase = "explain";
    if (q.cfg.mode === "hokushin") q.st.phase = "mark";
    if (!quizWrong(q).length) q.st.phase = "mark";
    q.resetArmed = false;
    saveQuizState(q);
    refreshQuiz(task);
  }

  function buildQuizBar(task) {
    var bar = document.createElement("div");
    bar.className = "quiz-bar";
    bar.id = "quizBar";
    bar.innerHTML = '<div class="qb-chips" id="qbChips"></div>' +
      '<div class="qb-row"><span class="qb-hint" id="qbHint"></span>' +
      '<button type="button" class="qb-reset" id="qbReset">やり直す</button></div>' +
      '<button type="button" class="qb-main" id="qbMain"></button>';
    view.appendChild(bar);
    document.getElementById("qbMain").addEventListener("click", function () {
      var act = task.quiz.action;
      if (act) act();
    });
    document.getElementById("qbReset").addEventListener("click", function () {
      var q = task.quiz;
      if (!q.resetArmed) {
        q.resetArmed = true;
        this.textContent = "ほんとうに消す？";
        setTimeout(function () {
          if (q.resetArmed) { q.resetArmed = false; var b = document.getElementById("qbReset"); if (b) b.textContent = "やり直す"; }
        }, 3000);
        return;
      }
      q.st = { marks: {}, phase: "mark" };
      q.resetArmed = false;
      saveQuizState(q);
      refreshQuiz(task);
      this.textContent = "やり直す";
    });
  }

  function refreshQuiz(task) {
    var q = task.quiz;
    renderQuizLayers(task);
    var chips = document.getElementById("qbChips");
    if (!chips) return;
    chips.innerHTML = "";
    chips.classList.toggle("many", q.cfg.questions.length > 12);
    document.body.classList.toggle("quiz-many", q.cfg.questions.length > 12);
    q.cfg.questions.forEach(function (x) {
      var b = document.createElement("button");
      b.type = "button";
      var mk = q.st.marks[x.n];
      b.className = "qc" + (mk ? " " + mk : "");
      b.innerHTML = '<span class="qc-n">' + esc(x.label || CIRC[x.n - 1] || x.n) + '</span><span class="qc-m">' + (mk === "o" ? "○" : mk === "x" ? "×" : "−") + "</span>";
      b.addEventListener("click", function () { cycleMark(task, x.n); });
      chips.appendChild(b);
    });

    var wrong = quizWrong(q);
    var marked = Object.keys(q.st.marks).length, total = q.cfg.questions.length;
    var hint = document.getElementById("qbHint"), main = document.getElementById("qbMain");
    var phase = q.st.phase;
    q.action = null;
    main.hidden = false;
    var panel = document.getElementById("qbPanel");
    if (panel) panel.remove();
    if (q.cfg.mode === "hokushin") {
      // 北辰チェックテスト：×の問題 → もどるGトレ教材を開く
      if (phase === "review" && wrong.length) {
        hint.textContent = "×の問題は、この教材にもどって復習しよう";
        buildReviewPanel(task, wrong);
        main.textContent = "‹ ○×にもどる";
        q.action = function () { q.st.phase = "mark"; saveQuizState(q); refreshQuiz(task); };
      } else if (wrong.length) {
        hint.textContent = "× が " + wrong.length + "問";
        main.textContent = "×の問題のGトレ教材を見る ›";
        q.action = function () { q.st.phase = "review"; saveQuizState(q); refreshQuiz(task); quizScrollTo("#qbPanel", q.cfg.pages.quiz, task); };
      } else if (marked === total) {
        hint.textContent = "ぜんぶ ○！ すごい";
        main.hidden = true;
      } else {
        hint.textContent = "答え合わせ表をタップして ○ × をつけよう（" + marked + "／" + total + "）";
        main.hidden = true;
      }
      return;
    }
    if (phase === "mark") {
      if (wrong.length) {
        hint.textContent = "× が " + wrong.length + "問";
        main.textContent = "×の解説を読む ›";
        q.action = function () { goExplain(task); };
      } else if (marked === total) {
        hint.textContent = "ぜんぶ ○！ すごい";
        main.textContent = "チェックテストへ ›";
        q.action = function () { goTest(task); };
      } else {
        // 記録表のない教材は、下の番号ボタンでつける
        var where = (q.cfg.cells && q.cfg.cells.length) ? "表" : "番号";
        hint.textContent = where + "をタップして ○ × をつけよう（" + marked + "／" + total + "）";
        main.hidden = true;
      }
    } else if (phase === "explain") {
      hint.textContent = "色のついた解説を読もう";
      main.textContent = "読み終えた → チェックテストへ ›";
      q.action = function () { goTest(task); };
    } else {
      hint.textContent = "色のついた問題を解こう";
      main.textContent = "‹ 解説にもどる";
      q.action = function () { goExplain(task); };
    }
  }

  // 北辰モード：×の問題を、もどるGトレ教材ごとにまとめて表示
  function buildReviewPanel(task, wrong) {
    var bar = document.getElementById("quizBar");
    if (!bar) return;
    var groups = [], map = {};
    wrong.forEach(function (x) {
      var k = (x.unit || "") + "|" + (x.topic || "");
      if (!map[k]) { map[k] = { unit: x.unit, topic: x.topic, qs: [] }; groups.push(map[k]); }
      map[k].qs.push(x.label || CIRC[x.n - 1] || x.n);
    });
    var panel = mkEl("qb-panel");
    panel.id = "qbPanel";
    groups.forEach(function (g) {
      var units = DATA["数学"] || [];
      var unit = findByName(units, g.unit, function (u) { return u.name; });
      var topic = null;
      if (unit) {
        var byCode = unit.topics.filter(function (t) { return norm(splitTopic(t.title).code) === norm(g.topic); });
        topic = byCode.length === 1 ? byCode[0] : findByName(unit.topics, g.topic, function (t) { return t.title; });
      }
      var b = document.createElement("button");
      b.type = "button";
      b.className = "qb-link" + (topic ? "" : " none");
      var title = topic ? topic.title : (g.unit + " " + g.topic);
      b.innerHTML = '<span class="qb-link-q">× ' + esc(g.qs.join("・")) + '</span>' +
        '<span class="qb-link-t">' + esc(title) + (topic ? " ›" : "（準備中）") + "</span>";
      if (topic) b.addEventListener("click", function () { go("数学", unit, topic); });
      panel.appendChild(b);
    });
    bar.insertBefore(panel, document.getElementById("qbMain"));
  }

  function quizScrollTo(sel, fallbackPageNum, task) {
    requestAnimationFrame(function () {
      var el = document.querySelector(sel);
      if (!el) {
        var pg = task.pages.filter(function (p) { return p.num === fallbackPageNum; })[0];
        el = pg && pg.box;
      }
      if (!el) return;
      var tools = document.querySelector(".viewer-tools");
      var off = (navBar.offsetHeight || 0) + (tools ? tools.offsetHeight : 0) + 10;
      window.scrollTo({ top: Math.max(0, el.getBoundingClientRect().top + window.scrollY - off), behavior: "smooth" });
    });
  }

  function goExplain(task) {
    var q = task.quiz;
    q.st.phase = "explain";
    saveQuizState(q);
    refreshQuiz(task);
    var first = (q.cfg.pages.explain || [])[0] || 1;
    quizScrollTo(".hl-explain", first, task);
  }
  function goTest(task) {
    var q = task.quiz;
    q.st.phase = quizWrong(q).length ? "test" : "mark";
    saveQuizState(q);
    refreshQuiz(task);
    quizScrollTo(".hl-test", q.cfg.pages.test, task);
  }

  function applyZoom(task, stack) {
    var wrap = stack.parentElement;
    var avail = wrap.clientWidth - 16;
    var w = Math.min(avail, 900) * task.zoom;
    stack.style.width = Math.round(w) + "px";
  }

  function renderPage(task, p) {
    var cssW = p.box.clientWidth;
    if (!cssW) return;
    var dpr = Math.min(window.devicePixelRatio || 1, 3);
    var targetW = Math.min(Math.round(cssW * dpr), 3000);   // メモリを使いすぎないよう上限
    if (Math.abs(targetW - p.renderedWidth) < 4 || p.rendering) return;
    var base = p.page.getViewport({ scale: 1 });
    var vp = p.page.getViewport({ scale: targetW / base.width });
    var canvas = document.createElement("canvas");
    canvas.width = Math.round(vp.width);
    canvas.height = Math.round(vp.height);
    var t = p.page.render({ canvasContext: canvas.getContext("2d", { alpha: false }), viewport: vp });
    p.rendering = t;
    t.promise.then(function () {
      p.rendering = null;
      if (task.cancelled) return;
      if (p.canvas) p.canvas.remove();
      p.box.insertBefore(canvas, p.box.firstChild);
      p.canvas = canvas;
      p.renderedWidth = targetW;
      // 大きくした後に戻した場合も、もう一度きれいに描く
      if (Math.abs(Math.round(p.box.clientWidth * dpr) - targetW) > 4) renderPage(task, p);
    }).catch(function () { p.rendering = null; });
  }

  /* ---------------- 共通：下から出る案内パネル ---------------- */
  function openGuideSheet(id, title, bodyHTML) {
    var old = document.getElementById(id);
    if (old) old.remove();
    var sheet = document.createElement("div");
    sheet.className = "qr-sheet";
    sheet.id = id;
    sheet.innerHTML =
      '<div class="qr-panel guide-panel" role="dialog" aria-modal="true" aria-labelledby="' + id + 'Title">' +
      '<button type="button" class="install-close qr-close" data-close aria-label="とじる">×</button>' +
      '<h2 class="qr-title" id="' + id + 'Title">' + title + "</h2>" + bodyHTML + "</div>";
    document.body.appendChild(sheet);
    document.body.classList.add("has-sheet");
    function close() {
      sheet.remove();
      document.body.classList.remove("has-sheet");
      document.removeEventListener("keydown", onKey);
    }
    function onKey(e) { if (e.key === "Escape") close(); }
    document.addEventListener("keydown", onKey);
    sheet.addEventListener("click", function (e) { if (e.target === sheet) close(); });
    sheet.querySelectorAll("[data-close]").forEach(function (b) { b.addEventListener("click", close); });
    sheet.querySelector("[data-close]").focus();
    return { el: sheet, close: close };
  }

  // 使っている端末（iPhone / Android / それ以外）とアプリ内ブラウザかどうか
  function deviceInfo() {
    var ua = navigator.userAgent;
    var ios = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    var android = /Android/.test(ua);
    var line = / Line\//i.test(ua);
    var inApp = line || /FBAN|FBAV|Instagram|MicroMessenger|; wv\)/.test(ua);
    var iosOther = ios && /CriOS|FxiOS|EdgiOS|OPiOS/.test(ua);
    return { ios: ios, android: android, line: line, inApp: inApp, iosOther: iosOther, kind: ios ? "ios" : android ? "android" : "pc" };
  }

  function stepsHTML(list) {
    return '<ol class="guide-steps">' + list.map(function (s) { return "<li>" + s + "</li>"; }).join("") + "</ol>";
  }

  function tabsHTML(active, panes) {
    // panes: { ios: html, android: html }
    return '<div class="guide-tabs" role="tablist">' +
      '<button type="button" role="tab" data-tab="ios" aria-selected="' + (active === "ios") + '">iPhone・iPad</button>' +
      '<button type="button" role="tab" data-tab="android" aria-selected="' + (active === "android") + '">Android</button>' +
      "</div>" +
      '<div class="guide-pane" data-pane="ios"' + (active === "ios" ? "" : " hidden") + ">" + panes.ios + "</div>" +
      '<div class="guide-pane" data-pane="android"' + (active === "android" ? "" : " hidden") + ">" + panes.android + "</div>";
  }
  function wireTabs(root) {
    root.querySelectorAll("[data-tab]").forEach(function (b) {
      b.addEventListener("click", function () {
        var t = b.getAttribute("data-tab");
        root.querySelectorAll("[data-tab]").forEach(function (x) { x.setAttribute("aria-selected", String(x === b)); });
        root.querySelectorAll("[data-pane]").forEach(function (p) { p.hidden = p.getAttribute("data-pane") !== t; });
      });
    });
  }

  /* ---------------- ホーム画面に追加（Android / iPhone） ---------------- */
  var deferredPrompt = null;
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferredPrompt = e;
    if (document.body.getAttribute("data-screen") === "home") render(false);
  });
  window.addEventListener("appinstalled", function () {
    deferredPrompt = null;
    var s = document.getElementById("installSheet");
    if (s) s.remove();
    document.body.classList.remove("has-sheet");
    if (document.body.getAttribute("data-screen") === "home") render(false);
  });

  function isStandalone() {
    return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  }

  var HOME_ICON_SVG = '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M12 8v6M9 11h6"/><path d="M10.5 18.5h3"/></svg>';

  // ホームの「ホーム画面に追加」ボタン（すでにホーム画面から開いているときは出さない）
  function installCardHTML() {
    if (isStandalone()) return "";
    return '<button type="button" class="qr-open-btn install-open-btn" id="installOpenBtn">' +
      '<span class="qr-open-icon install-icon" aria-hidden="true">' + HOME_ICON_SVG + "</span>" +
      '<span class="qr-open-text"><strong>ホーム画面に追加</strong>アプリのように1回タップで開けます</span>' +
      '<span class="chev" aria-hidden="true">›</span></button>';
  }
  function wireInstallCard() {
    var b = document.getElementById("installOpenBtn");
    if (b) b.addEventListener("click", openInstallSheet);
  }

  function openInstallSheet() {
    var d = deviceInfo();
    var head = "";

    // LINE などのアプリの中のブラウザでは、ホーム画面に追加できない
    if (d.inApp) {
      var ext = location.href + (location.search ? "&" : "?") + "openExternalBrowser=1";
      head = '<div class="guide-warn"><strong>いまはLINEなどのアプリの中で開いています。</strong>' +
        "このままではホーム画面に追加できません。" + (d.ios ? "Safari" : "Chrome") + "で開きなおしてください。" +
        '<div class="guide-btns">' +
        (d.line ? '<a class="qr-copy" href="' + esc(ext) + '">' + (d.ios ? "Safari" : "Chrome") + "で開く</a>" : "") +
        '<button type="button" class="qr-copy sub" id="installCopy">URLをコピー</button></div>' +
        '<p class="guide-small">コピーしたら' + (d.ios ? "Safari" : "Chrome") + "を開いて、上のアドレス欄に貼りつけます。</p></div>";
    } else if (d.android && deferredPrompt) {
      head = '<div class="guide-quick"><button type="button" class="qr-copy big" id="installNow">ホーム画面に追加する</button>' +
        '<p class="guide-small">出てきた画面で「インストール」をおせば完了です。</p></div>';
    } else if (d.iosOther) {
      head = '<div class="guide-warn">Safari で開くといちばん確実です。Chrome の場合は、アドレス欄の右にある共有ボタン（□に↑）から「ホーム画面に追加」をえらびます。</div>';
    }

    var ios = stepsHTML([
      "<b>Safari</b>でこの画面を開く",
      "画面の下（または上）にある<b>共有ボタン</b>" + '<span class="key">□に↑</span>' + "をおす<br><span class=\"guide-small\">見つからないときは、右下の<span class=\"key\">…</span>をおすと出てきます</span>",
      "下にスクロールして<b>「ホーム画面に追加」</b>をおす",
      "「Webアプリとして開く」が出たら<b>オン</b>のまま、右上の<b>「追加」</b>をおす",
      "ホーム画面に<b>「Gトレ教材」</b>のアイコンができたら完了"
    ]);
    var android = stepsHTML([
      "<b>Chrome</b>でこの画面を開く",
      "右上の<span class=\"key\">︙</span>（点が3つ）をおす",
      "<b>「ホーム画面に追加」</b>（または「アプリをインストール」）をおす",
      "<b>「インストール」</b>（または「追加」）をおす",
      "ホーム画面に<b>「Gトレ教材」</b>のアイコンができたら完了"
    ]);

    var s = openGuideSheet("installSheet", "ホーム画面に追加",
      '<p class="qr-lead">一度追加すると、次からはアイコンをタップするだけで開けます。</p>' + head +
      tabsHTML(d.kind === "android" ? "android" : "ios", { ios: ios, android: android }) +
      '<p class="guide-small guide-foot">一度開いた教材は、電波が弱いときも見られます。</p>');
    wireTabs(s.el);

    var now = document.getElementById("installNow");
    if (now) now.addEventListener("click", function () {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      deferredPrompt.userChoice.finally(function () { deferredPrompt = null; s.close(); render(false); });
    });
    var cp = document.getElementById("installCopy");
    if (cp) cp.addEventListener("click", function () {
      var url = appHomeURL();
      var done = function () { cp.textContent = "コピーしました ✓"; };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, function () { fallbackCopy(url); done(); });
      else { fallbackCopy(url); done(); }
    });
  }

  /* ---------------- 教室のプリンターで印刷 ---------------- */
  // 先生が print.json に「プリンター名」「Wi-Fi名」を書いておくと、生徒の画面にその名前が出ます
  var PRINT_CFG = null;
  function loadPrintCfg() {
    if (PRINT_CFG) return Promise.resolve(PRINT_CFG);
    return fetch("print.json", { cache: "no-cache" })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .catch(function () { return {}; })
      .then(function (j) {
        PRINT_CFG = {
          printer: String(j["プリンター名"] || "").trim(),
          wifi: String(j["Wi-Fi名"] || "").trim(),
          note: String(j["ひとこと"] || "").trim(),
          // 割り付け：書かない or "2in1" → 2in1（1枚に2ページ）／ "1in1" → 1枚に1ページ
          nup: /^\s*1\s*in\s*1\s*$/i.test(String(j["割り付け"] || "")) ? 1 : 2
        };
        return PRINT_CFG;
      });
  }

  var PRINT_ICON_SVG = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M6 14h12v7H6z"/></svg>';

  var printUrls = [];
  function clearPrintArea() {
    printUrls.forEach(function (u) { URL.revokeObjectURL(u); });
    printUrls = [];
    var a = document.getElementById("printArea");
    if (a) a.remove();
  }

  // えらんだページを、印刷用のきれいな画像にする
  // 1ページ分を、指定の大きさにおさまるように描いた canvas にする
  function renderPageCanvas(doc, n, boxW, boxH) {
    return doc.getPage(n).then(function (page) {
      var v1 = page.getViewport({ scale: 1 });
      var scale = Math.min(boxW / v1.width, boxH / v1.height);
      var vp = page.getViewport({ scale: scale });
      var c = document.createElement("canvas");
      c.width = Math.floor(vp.width); c.height = Math.floor(vp.height);
      var ctx = c.getContext("2d");
      ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, c.width, c.height);
      return page.render({ canvasContext: ctx, viewport: vp }).promise.then(function () { return c; });
    });
  }

  // えらんだページを、印刷用の画像（A4たて1枚＝1画像）にする
  //  nup=2 … 2in1：A4よこに2ページならべた形を、A4たての紙に向きを変えて1枚にする
  //           （スマホ・プリンターの設定に関係なく、だれが印刷しても必ず2in1になる）
  //  nup=1 … 1ページずつ
  var SHEET_W = 1654, SHEET_H = 2339;   // A4を約200dpi（スマホのメモリにもやさしい大きさ）
  function buildPrintPages(doc, nums, nup, onProgress) {
    clearPrintArea();
    var area = document.createElement("div");
    area.id = "printArea";
    area.setAttribute("aria-hidden", "true");
    document.body.appendChild(area);

    var sheets = [];
    for (var i = 0; i < nums.length; i += nup) sheets.push(nums.slice(i, i + nup));
    var done = 0;
    var chain = Promise.resolve();

    sheets.forEach(function (group) {
      chain = chain.then(function () {
        var sheet = document.createElement("canvas");
        sheet.width = SHEET_W; sheet.height = SHEET_H;
        var sx = sheet.getContext("2d");
        sx.fillStyle = "#fff"; sx.fillRect(0, 0, SHEET_W, SHEET_H);

        var inner = Promise.resolve();
        if (nup === 1) {
          inner = inner.then(function () {
            onProgress(++done, nums.length);
            return renderPageCanvas(doc, group[0], SHEET_W, SHEET_H);
          }).then(function (c) {
            sx.drawImage(c, (SHEET_W - c.width) / 2, (SHEET_H - c.height) / 2);
            c.width = c.height = 0;
          });
        } else {
          // A4よこ（2339×1654）を左右半分ずつに分けて、それぞれに1ページ
          var LW = SHEET_H, LH = SHEET_W, gap = 40, pad = 30;
          var halfW = (LW - pad * 2 - gap) / 2, halfH = LH - pad * 2;
          // よこの絵を時計まわりに90°回して、たての紙に描く（1ページ目が上、2ページ目が下）
          sx.translate(SHEET_W, 0);
          sx.rotate(Math.PI / 2);
          group.forEach(function (n, k) {
            inner = inner.then(function () {
              onProgress(++done, nums.length);
              return renderPageCanvas(doc, n, halfW, halfH);
            }).then(function (c) {
              var x0 = pad + k * (halfW + gap);
              sx.drawImage(c, x0 + (halfW - c.width) / 2, pad + (halfH - c.height) / 2);
              c.width = c.height = 0;
            });
          });
          // まん中に細い区切り線
          inner = inner.then(function () {
            sx.strokeStyle = "#d0d0d0"; sx.lineWidth = 2; sx.setLineDash([10, 10]);
            sx.beginPath(); sx.moveTo(LW / 2, pad); sx.lineTo(LW / 2, LH - pad); sx.stroke();
          });
        }

        return inner.then(function () {
          return new Promise(function (ok) { sheet.toBlob(ok, "image/jpeg", 0.92); });
        }).then(function (blob) {
          sheet.width = sheet.height = 0;
          var url = URL.createObjectURL(blob);
          printUrls.push(url);
          var box = document.createElement("div");
          box.className = "print-page";
          var img = new Image();
          img.alt = "";
          box.appendChild(img);
          area.appendChild(box);
          return new Promise(function (ok) { img.onload = img.onerror = ok; img.src = url; });
        });
      });
    });
    return chain.then(function () { return sheets.length; });
  }

  function openPrintSheet() {
    var task = currentPdfTask;
    if (!task || !task.doc) return;
    var doc = task.doc;
    var n = doc.numPages;
    var d = deviceInfo();

    loadPrintCfg().then(function (cfg) {
      if (currentPdfTask !== task) return;
      var pname = cfg.printer ? "「" + esc(cfg.printer) + "」" : "教室のプリンター";
      var chips = "";
      for (var i = 1; i <= n; i++) {
        chips += '<button type="button" class="pg-chip" data-pg="' + i + '" aria-pressed="true">' + i + "</button>";
      }

      var ios = stepsHTML([
        "下の<b>「印刷する」</b>をおす",
        "<b>「プリンタ」</b>をおして、<b class=\"pname\">" + pname + "</b>をえらぶ",
        "部数などを確かめて、右上の<b>「プリント」</b>をおす"
      ]);
      var android = stepsHTML([
        "下の<b>「印刷する」</b>をおす",
        "上の<b>「プリンタを選択」</b>（またはプリンタ名）をおし、<b>「すべてのプリンタ」</b>から<b class=\"pname\">" + pname + "</b>をえらぶ",
        "<span class=\"key\">プリンタの絵</span>のボタンをおす<br><span class=\"guide-small\">はじめての時は「印刷サービスを使いますか」と出たら「OK」</span>"
      ]);

      var s = openGuideSheet("printSheet", "教室のプリンターで印刷",
        '<div class="guide-check">' +
        "<b>印刷の前に</b>" +
        (cfg.wifi ? "教室のWi-Fi<b class=\"pname\">「" + esc(cfg.wifi) + "」</b>につながっているか確かめよう。"
                  : "教室のWi-Fiにつながっているか確かめよう。") +
        "<span class=\"guide-small\">ほかのWi-Fiやモバイル通信では、教室のプリンターは出てきません。</span></div>" +
        (cfg.note ? '<p class="guide-note">' + esc(cfg.note) + "</p>" : "") +
        (cfg.nup === 2 ? '<p class="guide-nup"><span class="nup-mark" aria-hidden="true"><i></i><i></i></span>' +
          "<span><b>2in1</b>（1枚の紙に2ページ）で印刷されます。<span class=\"guide-small\">印刷画面で何も変えなくてOK。</span></span></p>" : "") +
        '<div class="pg-pick"><div class="pg-pick-head"><b>印刷するページ</b>' +
        '<button type="button" class="pg-all" id="pgAll">すべて外す</button></div>' +
        '<div class="pg-chips" id="pgChips">' + chips + "</div>" +
        '<p class="guide-small" id="pgCount"></p></div>' +
        '<button type="button" class="qr-copy big" id="printGo">印刷する</button>' +
        '<h3 class="guide-h">印刷画面での操作</h3>' +
        tabsHTML(d.kind === "android" ? "android" : "ios", { ios: ios, android: android }) +
        '<details class="guide-more"><summary>プリンターが出てこないとき</summary>' +
        stepsHTML([
          "Wi-Fiが教室のものか、もう一度確かめる",
          "プリンターの電源が入っているか、先生に聞く",
          "Androidは「設定」→「接続済みのデバイス」（または「接続」）→「印刷」→<b>「デフォルトの印刷サービス」をオン</b>にする",
          '印刷画面が出ないときは <a href="' + esc(task.material ? task.material.open : "#") + '" target="_blank" rel="noopener">PDFを開いて</a>、共有ボタン（iPhone）か「︙」（Android）から「プリント／印刷」をえらぶ'
        ]) + "</details>");
      wireTabs(s.el);

      var chipBox = document.getElementById("pgChips");
      var allBtn = document.getElementById("pgAll");
      var count = document.getElementById("pgCount");
      var go = document.getElementById("printGo");
      function picked() {
        return Array.from(chipBox.querySelectorAll(".pg-chip")).filter(function (b) {
          return b.getAttribute("aria-pressed") === "true";
        }).map(function (b) { return Number(b.getAttribute("data-pg")); });
      }
      function refresh() {
        var p = picked();
        var paper = Math.ceil(p.length / cfg.nup);
        count.textContent = (p.length === n ? "全部で " + n + " ページ" : p.length + " ページえらんでいます（全部で " + n + " ページ）") +
          " → " + (cfg.nup === 2 ? "2in1で " : "") + "A4用紙 " + paper + " 枚";
        allBtn.textContent = p.length === n ? "すべて外す" : "すべてえらぶ";
        go.disabled = p.length === 0;
      }
      chipBox.addEventListener("click", function (e) {
        var b = e.target.closest(".pg-chip");
        if (!b) return;
        b.setAttribute("aria-pressed", String(b.getAttribute("aria-pressed") !== "true"));
        refresh();
      });
      allBtn.addEventListener("click", function () {
        var on = picked().length !== n;
        chipBox.querySelectorAll(".pg-chip").forEach(function (b) { b.setAttribute("aria-pressed", String(on)); });
        refresh();
      });
      refresh();

      go.addEventListener("click", function () {
        var nums = picked();
        if (!nums.length) return;
        go.disabled = true;
        buildPrintPages(doc, nums, cfg.nup, function (i, total) {
          go.textContent = "じゅんび中… " + i + " / " + total;
        }).then(function () {
          s.close();
          setTimeout(function () { window.print(); }, 60);
        }).catch(function () {
          go.disabled = false;
          go.textContent = "印刷する";
          clearPrintArea();
          alert("印刷のじゅんびができませんでした。「プリンターが出てこないとき」の方法をためしてください。");
        });
      });
    });
  }

  /* ---------------- その他 ---------------- */
  function updateBarHeight() {
    document.documentElement.style.setProperty("--bar-h", navBar.offsetHeight + "px");
  }
  window.addEventListener("resize", function () { updateBarHeight(); sizeDriveFrame(); });

  backBtn.addEventListener("click", goUp);
  document.getElementById("brandLink").addEventListener("click", function (e) { e.preventDefault(); go(null); });
  window.addEventListener("popstate", function () { render(true); });

  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("sw.js").catch(function () {});
    });
  }

  loadData().then(function () {
    var r = routeFromURL();
    history.replaceState({ app: true, depth: depthOf(r.subject, r.unit, r.topic) }, "", location.href);
    render(false);
  });
})();
