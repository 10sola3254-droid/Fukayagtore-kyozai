# 英語Gトレ 定期試験編 生成スクリプト（「ね」で英文を組み立てる版）
import re, html, sys, asyncio, importlib, json
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path(__file__).parent / "out"; OUT.mkdir(exist_ok=True)

def mk(s):
    """{…} を赤字、[[…]] を太字、改行を <br> にする。それ以外のHTMLはそのまま。"""
    s = str(s)
    s = re.sub(r"\{([^{}]*)\}", r'<span class="r">\1</span>', s)
    s = re.sub(r"\[\[(.*?)\]\]", r"<b>\1</b>", s)
    return s.replace("\n", "<br>")

CSS = """
@page { size: A4; margin: 19mm 11mm 13mm 11mm; }
* { box-sizing: border-box; }
body { font-family: 'BIZ UDPGothic'; font-size: 11pt; line-height: 1.45; color: #111; margin: 0; }
.r { color: #C00000; font-weight: bold; }
.g { color: #2E7D32; font-size: 10pt; }
.kana { color: #555; font-size: 8.5pt; margin-left: .4em; }
h2 { break-after: avoid; font-size: 14pt; color: #1F4E79; border-left: 6px solid #1F4E79; padding: 1px 0 1px 8px; margin: 8px 0 6px; }
h3 { break-after: avoid; font-size: 11.5pt; background: #E8F1FA; border-left: 4px solid #2E75B6; padding: 2px 8px; margin: 8px 0 4px; }
.brk { break-before: page; }
.goal { background: #EAF2FB; border-radius: 8px; padding: 6px 10px; margin-bottom: 6px; }
.box { border: 2px solid #1F4E79; border-radius: 8px; padding: 6px 10px; margin: 6px 0; }
.box .t { color: #1F4E79; font-weight: bold; margin-bottom: 2px; }
.num { display: inline-block; width: 1.35em; height: 1.35em; line-height: 1.35em; border-radius: 50%; background: #1F4E79; color: #fff; text-align: center; font-size: 9.5pt; font-weight: bold; margin-right: 4px; }
.kata { display: flex; flex-wrap: wrap; gap: 4px; align-items: stretch; margin: 4px 0; }
.kata .k { border: 1.5px solid #1F4E79; border-radius: 5px; text-align: center; padding: 2px 8px; min-width: 60px; }
.kata .k .e { font-weight: bold; font-size: 11.5pt; }
.kata .k .j { font-size: 8.5pt; color: #1F4E79; border-top: 1px dashed #9BB; }
.kata .k.hl { background: #FDEDED; border-color: #C00000; }
.kata .plus { align-self: center; color: #1F4E79; font-weight: bold; }
table.ex { width: 100%; border-collapse: collapse; margin: 4px 0; font-size: 10.5pt; }
table.ex td { border: 1px solid #BBB; padding: 2px 6px; vertical-align: top; }
table.ex td.l { background: #1F4E79; color: #fff; font-weight: bold; width: 4.8em; text-align: center; font-size: 9.5pt; }
table.ex .e { font-weight: bold; }
.two { display: flex; gap: 8px; margin: 6px 0; }
.two > div { flex: 1; border-radius: 8px; padding: 5px 9px; font-size: 10pt; }
.two ul { margin: 0; padding-left: 1.2em; }
.miss { background: #FDEDED; border: 1.5px solid #C00000; }
.miss .t { color: #C00000; font-weight: bold; }
.nyu { background: #FFF4E0; border: 1.5px solid #C07000; }
.nyu .t { color: #C07000; font-weight: bold; }
.small { background: #fff; border: 1px solid #AAA; }
.small .t { color: #1F4E79; font-weight: bold; }
/* 「ね」の7段解説 */
.ne { border: 1.5px solid #1F4E79; border-radius: 8px; margin: 5px 0 8px; break-inside: avoid; font-size: 10.5pt; }
.ne .row { display: flex; border-top: 1px solid #D5DEE8; }
.ne .row:first-child { border-top: none; }
.ne .lab { flex: 0 0 8.4em; white-space: nowrap; background: #EAF2FB; color: #1F4E79; font-weight: bold; font-size: 9pt; padding: 3px 5px; border-right: 1px solid #D5DEE8; }
.ne .row:first-child .lab { border-top-left-radius: 7px; }
.ne .row:last-child .lab { border-bottom-left-radius: 7px; }
.ne .val { flex: 1; padding: 3px 8px; }
.ne .nechunks span.c { display: inline-block; }
.ne .nechunks .sl { color: #888; margin: 0 3px; }
.ne .nechunks .nn { color: #C00000; font-weight: bold; }
.flow { display: flex; flex-wrap: wrap; gap: 3px; align-items: stretch; }
.flow .f { border: 1px solid #1F4E79; border-radius: 4px; padding: 1px 5px; text-align: center; font-size: 9.5pt; background: #fff; }
.flow .f .rl { display: block; font-size: 7.5pt; color: #fff; background: #1F4E79; border-radius: 3px; padding: 0 3px; margin: 1px 0; }
.flow .f .en { display: block; color: #C00000; font-weight: bold; font-size: 10.5pt; }
.flow .ar { align-self: center; color: #1F4E79; font-weight: bold; }
.ans { color: #C00000; font-weight: bold; font-size: 11.5pt; }
.ne .lastmiss { background: #FFF4E0; }
/* 問題 */
.inst { margin: 2px 0 4px; break-after: avoid; }
.q { margin: 3px 0 6px; break-inside: avoid; }
.q .qt { display: flex; gap: 6px; }
.q .qn { flex: 0 0 auto; font-weight: bold; }
.hint { background: #EEF7EE; border: 1.5px dashed #2E7D32; border-radius: 6px; padding: 1px 8px; margin: 3px 0 2px 1.6em; font-size: 9.5pt; }
.hint b { color: #2E7D32; }
.al { text-align: right; margin-top: 2px; }
.al span { display: inline-block; border-bottom: 1px solid #333; width: 42%; height: 1.3em; }
.al.long span { width: 92%; }
.al.long2 { margin-top: 12px; }
.words { color: #333; }
/* 解答 */
.re { background: #F5F5F5; border-radius: 6px; padding: 2px 8px; font-size: 9.5pt; color: #333; margin: 4px 0 2px; }
.re.inst2 { background: none; padding: 0 2px; }
.a1 { margin: 1px 0 1px 4px; }
.chip { display: inline-block; background: #C00000; color: #fff; font-size: 8.5pt; border-radius: 4px; padding: 0 5px; margin-right: 5px; vertical-align: 1px; }
.exp { margin: 0 0 4px 4px; font-size: 10.5pt; }
.exp .pt { color: #C00000; font-weight: bold; }
.aq { break-inside: avoid; border-bottom: 1px solid #E3E3E3; padding-bottom: 3px; }
"""

def kata_html(k):
    parts = []
    for i, b in enumerate(k):
        if i: parts.append('<span class="plus">＋</span>')
        e, j = b[0], b[1]
        hl = ' hl' if len(b) > 2 and b[2] else ''
        parts.append(f'<div class="k{hl}"><div class="e">{mk(e)}</div><div class="j">{mk(j)}</div></div>')
    return '<div class="kata">' + "".join(parts) + '</div>'

def ne_html(it, kana=False, show_jp=True):
    ch = it["chunks"]
    rows = []
    def row(l, v, cls=""):
        rows.append(f'<div class="row {cls}"><div class="lab">{l}</div><div class="val">{v}</div></div>')
    if show_jp:
        row("① 日本語の文", mk(it["jp"]))
    nes = []
    for c in ch:
        if len(c) > 3 and c[3]: continue   # 日本語にない語（Does など）は②に出さない
        t = html.escape(c[0]) if "<" not in c[0] else c[0]
        t = t[:-1] + '<span class="nn">ね</span>' if t.endswith("ね") else t
        # 末尾の「ね」だけ赤（単語の中の「ね」はそのまま）
        nes.append(f'<span class="c">{t}</span>')
    nes = '<span class="sl">／</span>'.join(nes)
    row("② 「ね」で区切る", f'<span class="nechunks">{nes}</span>')
    row("③ 考え方", mk(it["think"]))
    fl = []
    for n, i in enumerate(it["order"]):
        c = ch[i]
        jp = c[0][:-1] if c[0].endswith("ね") else c[0]
        if len(c) > 3 and c[3]: jp = '<span style="color:#888;font-size:8pt">日本語にない語</span>'
        if n: fl.append('<span class="ar">→</span>')
        fl.append(f'<div class="f"><span class="rl">{mk(c[2])}</span>{mk(jp)}<span class="en">{mk(c[1])}</span></div>')
    row("④ 英語の順に<br>並べかえ", f'<div class="flow">{"".join(fl)}</div>')
    k = f'<span class="kana">{it["kana"]}</span>' if kana and it.get("kana") else ""
    row("⑤ 完成した英文", f'<span class="ans">{mk(it["ans"])}</span>{k}')
    row("⑥ 文のしくみ", mk(it["why"]))
    row("⑦ 間違えやすい", mk(it["miss"]), "lastmiss")
    return '<div class="ne">' + "".join(rows) + '</div>'

def q_text(it):
    t = mk(it["q"])
    if it.get("words"):
        t += f'<br><span class="words">（ {html.escape(it["words"])} ）</span>'
    return t

def render(U):
    h = []
    h.append(f'<h2>本日の学習 ― {mk(U["topic"])}</h2><div class="goal">{mk(U["goal"])}</div>')
    for blk in U["explain"]:
        typ = blk[0]
        if typ == "kata":
            h.append(f'<div class="box"><div class="t">{mk(blk[1])}</div>{kata_html(blk[2])}' + (f'<div class="g">{mk(blk[3])}</div>' if len(blk) > 3 else "") + '</div>')
        elif typ == "table":
            rows = "".join(f'<tr><td class="l">{mk(r[0])}</td><td><span class="e">{mk(r[1])}</span><span class="kana">{r[2]}</span><br>{mk(r[3])}</td></tr>' for r in blk[2])
            h.append(f'<h3>{mk(blk[1])}</h3><table class="ex">{rows}</table>')
        elif typ == "two":
            cells = "".join(f'<div class="small"><div class="t">{mk(c[0])}</div>{mk(c[1])}</div>' for c in blk[1])
            h.append(f'<div class="two">{cells}</div>')
        elif typ == "text":
            h.append(f'<div>{mk(blk[1])}</div>')
        elif typ == "h3":
            h.append(f'<h3>{mk(blk[1])}</h3>')
    # ね の手順（共通）
    h.append('<div class="box"><div class="t">「ね」で英文を組み立てる 5ステップ</div>'
             '<div><span class="num">1</span>日本語の文を読む。（ふつうの文？　否定文？　疑問文？）</div>'
             '<div><span class="num">2</span>意味のまとまりごとに「ね」を入れて区切る。（例：私は<span class="r">ね</span>／昨日<span class="r">ね</span>／図書館で<span class="r">ね</span>／英語を<span class="r">ね</span>／勉強しました）</div>'
             '<div><span class="num">3</span>英語では何を先に言うかを考える。まず「誰が」「どうする」を見つける。</div>'
             '<div><span class="num">4</span>まとまりを英語の順に並べかえる。</div>'
             '<div><span class="num">5</span>主語・動詞・何を・どこで・いつ を確かめて、英文を完成させる。</div>'
             f'<div class="g">この単元のコツ：{mk(U["kotsu"])}<br>「ね」を入れる場所は1つの正解ではありません。英語の順番を考えやすくするための目印です。</div></div>')
    h.append('<div class="two">'
             f'<div class="miss"><div class="t">間違えやすいポイント</div><ul>{"".join("<li>"+mk(x)+"</li>" for x in U["miss"])}</ul></div>'
             f'<div class="nyu"><div class="t">テストのポイント</div><ul>{"".join("<li>"+mk(x)+"</li>" for x in U["test"])}</ul></div></div>')
    for i, ex in enumerate(U["examples"], 1):
        h.append(f'<div style="break-inside: avoid"><h3>例題{i}　{mk(ex["label"])}</h3>{ne_html(ex, kana=True)}</div>')
    # 確認問題
    h.append('<h2 class="brk">確認問題</h2>')
    for sec in U["q"]:
        head = f'<h3>{mk(sec["h"])}</h3><div class="inst">{mk(sec["inst"])}</div>'
        for n, it in enumerate(sec["items"], 1):
            hint = f'<div class="hint"><b>💡ヒント</b> {mk(it["hint"])}</div>' if it.get("hint") else ""
            long_ = sec.get("long")
            al = f'<div class="al long{" long2" if long_ else ""}"><span></span></div>' if long_ else '<div class="al">答え <span></span></div>'
            h.append((f'<div style="break-inside: avoid">{head}' if n == 1 else '') + f'<div class="q"><div class="qt"><span class="qn">({n})</span><span>{q_text(it)}</span></div>{hint}{al}</div>' + ('</div>' if n == 1 else ''))
    # 解答・解説
    h.append('<h2 class="brk">確認問題 解答・解説</h2>')
    for sec in U["q"]:
        head = f'<h3>{mk(sec["h"])}</h3><div class="re inst2">{mk(sec["inst"])}</div>'
        for n, it in enumerate(sec["items"], 1):
            body = f'<div class="re">({n}) {q_text(it)}</div>'
            if "chunks" in it:
                body += ne_html(it, show_jp=False)
            else:
                body += f'<div class="a1"><span class="chip">答え</span><span class="ans">{mk(it["a"])}</span></div><div class="exp">{mk(it["exp"])}</div>'
            if n == 1:
                h.append(f'<div style="break-inside: avoid">{head}<div class="aq">{body}</div></div>')
            else:
                h.append(f'<div class="aq">{body}</div>')
    return h

def header(U):
    return f'''<div style="width:100%;margin:0 11mm;font-family:'BIZ UDPGothic';-webkit-print-color-adjust:exact;">
<div style="display:flex;align-items:center;gap:8px;border-bottom:2px solid #1F4E79;padding-bottom:3px;">
<span style="background:#1F4E79;color:#fff;border-radius:5px;padding:1px 7px;font-size:9pt;font-weight:bold;">{U["chip"]}</span>
<span style="color:#1F4E79;font-size:14pt;font-weight:bold;">{html.escape(U["title"])}</span></div></div>'''

def footer(U):
    return f'''<div style="width:100%;margin:0 11mm;font-family:'BIZ UDPGothic';font-size:8pt;color:#777;display:flex;justify-content:space-between;border-top:1px solid #BBB;padding-top:2px;">
<span>{html.escape(U["title"])}</span><span style="color:#111;font-weight:bold;font-size:9pt;">p. <span class="pageNumber"></span></span></div>'''

def check(U):
    """並べかえの語数チェック・必須項目チェック"""
    errs = []
    def norm(w): return re.sub(r"[.?!,]", "", w).lower()
    for sec in U["q"]:
        for it in sec["items"]:
            if it.get("words"):
                a = sorted(norm(w) for w in it["ans"].split() if norm(w))
                b = sorted(norm(w) for w in re.split(r"\s*/\s*", it["words"]) for w in w.split() if norm(w))
                if a != b: errs.append(f'語群不一致: {it["ans"]} | {a} vs {b}')
            if "ね、" in it.get("q","") or "ね／" in it.get("q",""): errs.append("問題文に「ね」: " + it["q"])
            if "chunks" in it:
                if sorted(it["order"]) != list(range(len(it["chunks"]))): errs.append("order不正: " + it["ans"])
    for ex in U["examples"]:
        if sorted(ex["order"]) != list(range(len(ex["chunks"]))): errs.append("order不正: " + ex["ans"])
    return errs

async def build(mods):
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for U in mods:
            e = check(U)
            if e: print("⚠", U["file"], *e, sep="\n  ")
            doc = f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(render(U))}</body></html>'
            (OUT / (U["file"] + ".html")).write_text(doc, encoding="utf-8")
            pg = await b.new_page()
            await pg.set_content(doc, wait_until="networkidle")
            await pg.pdf(path=str(OUT / (U["file"] + ".pdf")), format="A4", print_background=True,
                         display_header_footer=True, header_template=header(U), footer_template=footer(U),
                         margin={"top": "19mm", "bottom": "13mm", "left": "11mm", "right": "11mm"})
            await pg.close()
            import subprocess
            n = subprocess.run(["pdfinfo", str(OUT / (U["file"] + ".pdf"))], capture_output=True, text=True).stdout
            print(U["file"], re.search(r"Pages:\s+(\d+)", n).group(1), "pages")
        await b.close()

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    units = []
    for m in sys.argv[1:]:
        mod = importlib.import_module(m)
        units += mod.UNITS
    asyncio.run(build(units))
