#!/usr/bin/env python3
"""
数学Gトレ教材PDFの「解答・解説」ページの各問題の上に、その問題文（確認問題・チェックテストの問題枠）を
小さく載せた版を作る。ページ数は変えない（入りきらないぶんは内容を縮小する）。

  python3 tools/add_problem_text.py public/materials/xxxx.pdf [出力.pdf]

・確認問題／チェックテストのページ番号は同名の .json（make_quiz_json.py の出力）から読む。
・解答ページの問題のはじまりは「番号 答え…」の行で見つける。
・問題文は元ページから切り出して（文字・図はそのまま）、グレーの枠に入れて置く。
"""
import json, os, re, subprocess, sys
from xml.etree import ElementTree as ET
import pymupdf

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"
UNIT = r"(?:\d+章-[0-9０-９①-⑳]+(?:[・＋+](?:\d+章-)?[0-9０-９①-⑳]+)*|§[0-9０-９]+)"
PROB_SCALE = 0.78   # 問題文の縮小率（さらにページ全体の縮小がかかる）
MIN_SCALE = 0.60    # ページ全体の縮小の下限（これを下回ったら警告）
GAP = 4


def num_of(t):
    if re.fullmatch(r"\d{1,2}", t) and 1 <= int(t) <= 12:
        return int(t)
    if len(t) == 1 and t in CIRCLED:
        return CIRCLED.index(t) + 1
    return None


def words_of(pdf):
    xml = subprocess.run(["pdftotext", "-bbox", pdf, "-"], check=True, capture_output=True).stdout.decode()
    xml = re.sub(r"<!DOCTYPE[^>]*>", "", xml).replace('xmlns="http://www.w3.org/1999/xhtml"', "")
    pages = []
    for pg in ET.fromstring(xml).iter("page"):
        ws = [dict(t=w.text or "", x0=float(w.get("xMin")), y0=float(w.get("yMin")),
                   x1=float(w.get("xMax")), y1=float(w.get("yMax"))) for w in pg.iter("word")]
        pages.append(ws)
    return pages


def anchors_answer(ws, W):
    """解答ページ：『番号 答え』の行。(n, x0, y0, y1) を返す"""
    out = []
    for w in ws:
        n = num_of(w["t"])
        if n is None or w["y0"] < 25:
            continue
        if not (w["x0"] < 52 or W / 2 - 6 < w["x0"] < W / 2 + 24):
            continue
        colx = 0 if w["x0"] < W / 2 else W / 2 - 6
        if any(abs(v["y0"] - w["y0"]) < 6 and colx <= v["x0"] < w["x0"] - 1 for v in ws if v is not w):
            continue  # 行の先頭ではない
        nxt = [v for v in ws if v["t"].startswith("答") and abs(v["y0"] - w["y0"]) < 9 and 0 <= v["x0"] - w["x1"] < 320]
        # 番号と「答え」の間にあるのは単元タグか短い分類語（加減・累乗 など）だけ
        if nxt:
            mid = [v for v in ws if abs(v["y0"] - w["y0"]) < 9 and w["x1"] <= v["x0"] < nxt[0]["x0"] and v is not w]
            if any(not re.fullmatch(UNIT, v["t"]) and len(v["t"]) > 4 for v in mid) or len(mid) > 2:
                nxt = []
        if nxt:
            out.append(dict(n=n, x0=w["x0"], y0=min(w["y0"], nxt[0]["y0"]), y1=max(w["y1"], nxt[0]["y1"])))
    return dedupe(out)


def anchors_problem(ws, W, H, expected=None):
    """問題ページ：行の先頭（列の左はし）にある番号（1,2,… または ①②…）"""
    tbl = [w for w in ws if ("番号" in w["t"] or "記録表" in w["t"]) and w["x0"] < 110 and w["y0"] > H * 0.45]
    ymax = (min(w["y0"] for w in tbl) - 8) if tbl else H - 40
    out = []
    for w in ws:
        n = num_of(w["t"])
        if n is None or w["y0"] < 50 or w["y0"] > ymax:
            continue
        if any(abs(v["y0"] - w["y0"]) < 6 and v["x1"] <= w["x0"] + 1 and w["x0"] - v["x0"] < 30 for v in ws if v is not w):
            continue  # すぐ左に小さな記号がある（□①… のような箇条書き）
        right = [v for v in ws if abs(v["y0"] - w["y0"]) < 7 and 0 <= v["x0"] - w["x1"] < 45 and v is not w]
        if not right or num_of(min(right, key=lambda v: v["x0"])["t"]) is not None:
            continue  # 番号のあとに言葉が続かない（表の中の番号など）
        out.append(dict(n=n, x0=w["x0"], y0=w["y0"], y1=w["y1"]))
    return dedupe(out, expected)


def dedupe(out, expected=None):
    """同じ番号は上のものだけ。ほかの番号と左はしがそろわない孤立した番号は捨てる"""
    cnt = {id(a): len({b["n"] for b in out if abs(b["x0"] - a["x0"]) < 3}) for a in out}
    if len(out) >= 3:
        # 左はし x ごとにまとめ、小さいまとまり（文中の数字など）は捨てる
        mx = max(cnt.values())
        def keep(a):
            if cnt[id(a)] >= max(2, 0.6 * mx):
                return True
            # 1つだけの列でも、解答ページにある番号で、ほかに同じ番号がなければ残す
            return bool(expected) and a["n"] in expected and not any(b["n"] == a["n"] and cnt[id(b)] > cnt[id(a)] for b in out)
        out = [a for a in out if keep(a)]
    best = {}
    for a in out:
        b = best.get(a["n"])
        if b is None or (cnt[id(a)], -a["y0"]) > (cnt[id(b)], -b["y0"]):
            best[a["n"]] = a
    return sorted(best.values(), key=lambda a: (a["y0"], a["x0"]))


def columns(anchors, W):
    """番号の左はし x をまとめて列の区切りを返す： [(x0, x1), ...]"""
    xs = sorted(a["x0"] for a in anchors)
    centers = []
    for x in xs:
        if centers and x - centers[-1][-1] < 40:
            centers[-1].append(x)
        else:
            centers.append([x])
    cs = [sum(c) / len(c) for c in centers]
    margin = 28
    if len(cs) == 1:
        return [(margin, W - margin)]
    # 各列は「その列の番号の左はし」から「次の列の番号の少し手前」まで
    cols = []
    for i, c in enumerate(cs):
        x0 = margin if (i == 0 and c < 60) else c - 8
        x1 = (cs[i + 1] - 10) if i + 1 < len(cs) else W - margin
        cols.append((x0, x1))
    return cols


def col_range(a, cols, W=None, margin=28):
    for x0, x1 in cols:
        if x0 - 8 <= a["x0"] <= x1:
            return x0, x1
    return min(cols, key=lambda c: abs(c[0] - a["x0"]))


def problem_rects(page, ws, anchors, W, H):
    """問題ページの各問題の枠（単位 pt）"""
    cols = columns(anchors, W)
    # 下限：表の「番号」行 or フッター
    tbl = [w for w in ws if ("番号" in w["t"] or "記録表" in w["t"]) and w["x0"] < 110 and w["y0"] > H * 0.45]
    page_bottom = (min(w["y0"] for w in tbl) - 8) if tbl else H - 44
    draws = [d["rect"] for d in page.get_drawings()] + [page.get_image_bbox(i) for i in page.get_images(full=True)]
    rects = {}
    for a in anchors:
        cx0, cx1 = col_range(a, cols)
        later = [b for b in anchors if b["y0"] > a["y0"] + 4 and cx0 - 2 <= b["x0"] <= cx1]
        bottom = min([b["y0"] - 6 for b in later] + [page_bottom])
        top = a["y0"] - 6
        inw = [w for w in ws if top < w["y0"] < bottom and cx0 - 2 <= w["x0"] <= cx1 + 2]
        hintw = [w for w in inw if "ヒント" in w["t"]]
        hint_y = min(w["y0"] for w in hintw) if hintw else bottom
        # ヒントの囲み（ヒントの言葉を含むいちばん小さい塗り）
        hint_box = None
        if hintw:
            hw = hintw[0]
            cands = [r for r in draws if r.x0 <= hw["x0"] + 1 and r.x1 >= hw["x1"] - 1 and r.y0 <= hw["y0"] + 1 and r.y1 >= hw["y1"] - 1
                     and r.width < (cx1 - cx0) + 12 and r.height < 200 and r.width >= (hw["x1"] - hw["x0"]) * 3]
            if cands:
                hint_box = min(cands, key=lambda r: r.width * r.height)
            else:
                hint_box = pymupdf.Rect(cx0, hint_y - 2, cx1, bottom)
        def in_hint(x0, y0, x1, y1):
            return hint_box is not None and x0 >= hint_box.x0 - 2 and x1 <= hint_box.x1 + 2 and y0 >= hint_box.y0 - 2 and y1 <= hint_box.y1 + 2
        ans = [w for w in inw if w["t"] == "答え" and w["y0"] > a["y1"] and not in_hint(w["x0"], w["y0"], w["x1"], w["y1"])]
        ans_y = min([w["y0"] for w in ans] + [bottom])
        # 問題文の言葉（答えの行・ヒント枠の中は除く）の下端
        content = [w for w in inw if not in_hint(w["x0"], w["y0"], w["x1"], w["y1"])
                   and not any(abs(w["y0"] - v["y0"]) < 4 and w["x0"] >= v["x0"] - 2 for v in ans)]
        cb = max([w["y1"] for w in content] + [a["y1"]])
        cr = max([w["x1"] for w in content] + [a["x0"] + 60])
        # 答えを書く空の四角（言葉の下にあり、中に文字がない）は除く
        def is_answer_box(r):
            if not (12 <= r.height <= 34 and 36 <= r.width <= 150 and r.y0 >= cb - 3):
                return False
            return not any(r.x0 - 1 <= w["x0"] and w["x1"] <= r.x1 + 1 and r.y0 - 1 <= w["y0"] and w["y1"] <= r.y1 + 1 for w in inw)
        draws_here = [r for r in draws if not is_answer_box(r)]
        # 図（線・画像）も含める（ヒント枠・「答え」の下線・問題全体の枠は除く）
        for r in draws_here:
            if r.x0 >= cx0 - 6 and r.x1 <= cx1 + 6 and r.y0 >= top - 1 and r.y0 < ans_y - 3 \
                    and r.y1 <= bottom + 1 and r.y1 <= ans_y + 3 and r.height < 200 \
                    and not (r.width < 3 and r.height > 100) and not (r.height < 2.5 and r.width > (cx1 - cx0) * 0.6) \
                    and not in_hint(r.x0, r.y0, r.x1, r.y1) and not (hint_box is not None and r.intersects(hint_box) and r.y1 > hint_box.y0 + 6) \
                    and not (r.width > (cx1 - cx0) * 0.8 and r.height > 30):
                cb = max(cb, r.y1)
                cr = max(cr, r.x1)
        cut = min(bottom, ans_y, cb + 4)
        cut = max(cut, cb + 2)
        cut = min(cut, bottom)
        clip = pymupdf.Rect(cx0, top, min(cx1, cr + 6), cut)
        rects[a["n"]] = (clip, hint_box if (hint_box is not None and hint_box.intersects(clip)) else None)
    return rects


def answer_segments(page, ws, anchors, W, H):
    """解答ページを 見出し／列ごとの問題区間／フッター に分ける"""
    draws = [d["rect"] for d in page.get_drawings()]
    cols_ = columns(anchors, W)
    ncol = len(cols_)
    foot_y = H - 44
    fw = [w for w in ws if w["y0"] > H - 46]
    if fw:
        foot_y = min(w["y0"] for w in fw) - 4
    for r in draws:  # フッターの罫線
        if r.y0 > H - 60 and r.width > W * 0.8 and r.height < 3:
            foot_y = min(foot_y, r.y0 - 3)
    head_end = min(a["y0"] for a in anchors) - 7
    # 2列のとき、いちばん下にある全幅の囲み（「解き直しが終わったら」など）は列の外に出す
    trailer = None
    if ncol >= 2:
        amax = max(a["y0"] for a in anchors)
        cand = [r for r in draws if r.width > W * 0.6 and r.y0 > amax + 10 and r.y1 <= foot_y and r.height > 12]
        if cand:
            ty = min(r.y0 for r in cand) - 2
            ys = [w["y1"] for w in ws if ty < w["y0"] < foot_y] + [r.y1 for r in draws if ty <= r.y0 and r.y1 < foot_y]
            trailer = pymupdf.Rect(0, ty, W, min(foot_y, max(ys) + 4))
    cols = {}
    for a in anchors:
        cx0, cx1 = col_range(a, cols_)
        key = (round(cx0), round(cx1))
        cols.setdefault(key, []).append(a)
    segs = {}
    for key, al in cols.items():
        al.sort(key=lambda a: a["y0"])
        lst = []
        for i, a in enumerate(al):
            top = a["y0"] - 7
            bottom = al[i + 1]["y0"] - 7 if i + 1 < len(al) else (trailer.y0 - 1 if trailer else foot_y)
            if i + 1 == len(al):
                # 最後の区間はページ下の余白を切る
                ys = [w["y1"] for w in ws if top < w["y0"] < bottom and key[0] - 2 <= w["x0"] <= key[1] + 2]
                ys += [r.y1 for r in draws if top < r.y0 < bottom and r.y1 < foot_y - 1 and r.x0 >= key[0] - 6 and r.x1 <= key[1] + 6]
                if ys:
                    bottom = min(bottom, max(ys) + 8)
            lst.append(dict(n=a["n"], rect=pymupdf.Rect(key[0], top, key[1], bottom)))
        segs[key] = lst
    return head_end, foot_y, segs, trailer


def detect_pages(WP):
    """.json がないとき：ページ上部の文字から 確認問題／チェックテスト のページを探す"""
    quiz = test = None
    for i, ws in enumerate(WP):
        head = "".join(w["t"] for w in ws if w["y0"] < 70)
        if quiz is None and "確認問題" in head and "解答" not in head and "解説" not in head:
            quiz = i
        if test is None and "チェックテスト" in head and "解答" not in head and "解説" not in head and quiz is not None and i > quiz:
            test = i
    return quiz, test


def build(pdf, out):
    """作れたら True、形が合わず途中であきらめたら False（出力しない）"""
    base = os.path.splitext(pdf)[0]
    src = pymupdf.open(pdf)
    WP = words_of(pdf)
    W, H = src[0].rect.width, src[0].rect.height
    quiz_i = test_i = None
    if os.path.exists(base + ".json"):
        meta = json.load(open(base + ".json"))
        quiz_i = meta["pages"].get("quiz", 0) - 1 if "quiz" in meta["pages"] else None
        test_i = meta["pages"]["test"] - 1 if "test" in meta["pages"] else None
    if quiz_i is None:
        quiz_i, test_i = detect_pages(WP)
    if quiz_i is None:
        print("  ⚠ 確認問題のページが見つからない"); return False
    if test_i is None:
        test_i = len(src)  # チェックテストなし（確認問題＋解答だけの教材）
    ok = True
    # 解答ページにある問題番号（問題ページの番号探しの手がかり）
    expected = {"quiz": set(), "test": set()}
    for pi in range(len(src)):
        role = "quiz" if quiz_i < pi < test_i else ("test" if pi > test_i else None)
        if role:
            expected[role] |= {a["n"] for a in anchors_answer(WP[pi], W)}
    # 問題文の枠
    prob = {}
    for role, pi in (("quiz", quiz_i), ("test", test_i)):
        if pi >= len(src):
            continue
        an = anchors_problem(WP[pi], W, H, expected[role] or None)
        if not an:
            print(f"  ⚠ {role} ページ(p.{pi+1}) に問題番号が見つからない"); ok = False
        rects = problem_rects(src[pi], WP[pi], an, W, H)
        for n, (r, _) in rects.items():
            inside = [w for w in WP[pi] if r.contains(pymupdf.Point(w["x0"] + 1, w["y0"] + 1))]
            if r.height > 230 or r.height < 12 or r.width < 40 or len(inside) < 2:
                print(f"  ⚠ {role} ページ 問題{n} の枠が不自然 ({r.width:.0f}×{r.height:.0f}pt, 語{len(inside)})"); ok = False
        prob[role] = (pi, rects)
    dst = pymupdf.open()
    font = pymupdf.Font("japan")
    summary = []
    for pi in range(len(src)):
        page = dst.new_page(width=W, height=H)
        role = "quiz" if quiz_i < pi < test_i else ("test" if pi > test_i else None)
        if role and role not in prob:
            role = None
        an = anchors_answer(WP[pi], W) if role else []
        if not an:
            page.show_pdf_page(page.rect, src, pi)
            if role:
                print(f"  ⚠ p.{pi+1} は解答ページのはずだが問題の見出しが見つからない"); ok = False
            continue
        summary.append(0)
        spi, prects = prob[role]
        head_end, foot_y, segs, trailer = answer_segments(src[pi], WP[pi], an, W, H)
        # 列をまたぐ言葉があれば、この形には合わない（列ごとに切ると文が切れる）
        if len(segs) >= 2:
            bs = sorted(k[0] for k in segs)[1:]
            top_a = min(a["y0"] for a in an) - 7
            cross = [w for w in WP[pi] if head_end < w["y0"] < (trailer.y0 if trailer else foot_y) and any(w["x0"] < b - 3 and w["x1"] > b + 3 for b in bs)]
            if cross:
                print(f"  ⚠ p.{pi+1} 列をまたぐ文がある（例: {cross[0]['t'][:12]}）"); ok = False
        # 見出し・フッターはそのまま
        page.show_pdf_page(pymupdf.Rect(0, 0, W, head_end), src, pi, clip=pymupdf.Rect(0, 0, W, head_end))
        page.show_pdf_page(pymupdf.Rect(0, foot_y, W, H), src, pi, clip=pymupdf.Rect(0, foot_y, W, H))
        avail = foot_y - head_end - 2
        if trailer:
            avail -= trailer.height + GAP
        # 必要な高さ（列ごと）
        def need(lst, colw):
            tot = 0
            for s in lst:
                pr = prects.get(s["n"], (None, None))[0]
                if pr:
                    k = min(PROB_SCALE, colw / pr.width)
                    tot += pr.height * k + 6 + GAP
                tot += s["rect"].height
            return tot
        scale = 1.0
        for key, lst in segs.items():
            colw = key[1] - key[0]
            scale = min(scale, avail / need(lst, colw))
        if scale < MIN_SCALE:
            print(f"  ⚠ p.{pi+1} 縮小率 {scale:.2f}（{MIN_SCALE} 未満）"); ok = False
        elif scale < 0.75:
            print(f"  p.{pi+1} 縮小率 {scale:.2f}")
        y_end = head_end + 1
        for key, lst in segs.items():
            cx0, cx1 = key
            colw = cx1 - cx0
            y = head_end + 1
            for s in lst:
                pr, hb = prects.get(s["n"], (None, None))
                if pr is None:
                    print(f"  ⚠ p.{pi+1} 問題{s['n']} の問題文が {role} ページに見つからない"); ok = False
                else:
                    k = min(PROB_SCALE, colw / pr.width) * scale
                    pw, ph = pr.width * k, pr.height * k
                    box = pymupdf.Rect(cx0, y, cx0 + max(pw + 6, 80), y + ph + 6)
                    sh = page.new_shape()
                    sh.draw_rect(box)
                    sh.finish(color=(0.75, 0.75, 0.75), fill=(0.955, 0.955, 0.955), width=0.5)
                    sh.commit()
                    tgt = pymupdf.Rect(cx0 + 3, y + 3, cx0 + 3 + pw, y + 3 + ph)
                    page.show_pdf_page(tgt, src, spi, clip=pr)
                    summary[-1] += 1
                    if hb is not None:
                        # ヒントの囲みは枠の色でぬりつぶして消す
                        hbc = hb & pr
                        if not hbc.is_empty:
                            hr = pymupdf.Rect(tgt.x0 + (hbc.x0 - pr.x0) * k, tgt.y0 + (hbc.y0 - pr.y0) * k,
                                              tgt.x0 + (hbc.x1 - pr.x0) * k, tgt.y0 + (hbc.y1 - pr.y0) * k)
                            sh = page.new_shape(); sh.draw_rect(hr); sh.finish(color=None, fill=(0.955, 0.955, 0.955)); sh.commit()
                    # 小さな「問題」ラベル（枠の右上）
                    fs = 6.5 * max(scale, 0.8)
                    tw = font.text_length("問題", fontsize=fs)
                    lx = box.x1 - tw - 3
                    page.insert_text((lx, y + 3 + fs), "問題", fontsize=fs, fontname="japan", color=(0.45, 0.45, 0.45))
                    y = box.y1 + GAP
                r = s["rect"]
                tgt = pymupdf.Rect(cx0, y, cx0 + r.width * scale, y + r.height * scale)
                page.show_pdf_page(tgt, src, pi, clip=r)
                y = tgt.y1
            y_end = max(y_end, y)
        if trailer:
            tgt = pymupdf.Rect(0, y_end + GAP, W * scale, y_end + GAP + trailer.height * scale)
            page.show_pdf_page(tgt, src, pi, clip=trailer)
    if not summary:
        print("  ⚠ 問題枠を1つも置けなかった"); ok = False
    if not ok:
        print("  × 形が合わないので出力しません（元のまま）")
        return False
    dst.save(out, garbage=4, deflate=True)
    print(f"書きました: {out}  解答ページ {len(summary)}  問題枠 {sum(summary)}")
    return True


if __name__ == "__main__":
    pdf = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else re.sub(r"(-r\d+)?\.pdf$", "", pdf) + "-q.pdf"
    sys.exit(0 if build(pdf, out) else 1)
