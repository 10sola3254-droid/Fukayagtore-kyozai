#!/usr/bin/env python3
"""
Gトレ教材PDFから「チェック機能」用の位置データ（.json）を作る。

  python3 tools/make_quiz_json.py public/materials/xxxx.pdf

できるもの: public/materials/xxxx.json
  ・確認問題ページの「確認問題 ○×」の行（マスごとの位置）
  ・解説ページの単元ごとの位置（まちがえた単元に色をつける場所）
  ・チェックテストの問題ごとの位置（まちがえた番号に色をつける場所）
位置はすべて「ページの幅・高さに対する割合（0〜1）」。
"""
import json, re, subprocess, sys, os, tempfile
from xml.etree import ElementTree as ET

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True).stdout


def pages_words(pdf):
    xml = run(["pdftotext", "-bbox", pdf, "-"]).decode("utf-8")
    xml = re.sub(r"<!DOCTYPE[^>]*>", "", xml)
    xml = xml.replace('xmlns="http://www.w3.org/1999/xhtml"', "")
    root = ET.fromstring(xml)
    out = []
    for pg in root.iter("page"):
        W, H = float(pg.get("width")), float(pg.get("height"))
        words = [(w.text or "", float(w.get("xMin")), float(w.get("yMin")), float(w.get("xMax")), float(w.get("yMax")))
                 for w in pg.iter("word")]
        out.append({"W": W, "H": H, "words": words})
    return out


def page_kind(p):
    """ページ上端の帯の文字で種類を判定"""
    head = [w for w in p["words"] if w[2] < 60]
    txt = "".join(w[0] for w in sorted(head, key=lambda w: (round(w[2]), w[1])))
    for key, kind in (("チェックテスト", "test"), ("確認問題", "quiz"), ("解答・解説", "answer"), ("解説", "explain")):
        if txt.startswith(key):
            return kind
    return "other"


def frac(p, x0, y0, x1, y1):
    W, H = p["W"], p["H"]
    r = lambda v: round(v, 4)
    return {"x": r(x0 / W), "y": r(y0 / H), "w": r((x1 - x0) / W), "h": r((y1 - y0) / H)}


def grid_lines(pdf, pageno, p, y_from, y_to):
    """表の縦線・横線を画像から探す（PDF座標 pt で返す）"""
    from PIL import Image
    import numpy as np
    dpi = 200
    with tempfile.TemporaryDirectory() as td:
        run(["pdftoppm", "-r", str(dpi), "-f", str(pageno), "-l", str(pageno), "-gray", "-png", pdf, td + "/g"])
        f = [x for x in os.listdir(td) if x.endswith(".png")][0]
        a = np.array(Image.open(os.path.join(td, f)).convert('L'))
    s = dpi / 72.0
    y0, y1 = int(y_from * s), int(y_to * s)
    reg = a[y0:y1, :] < 150
    cols = reg.mean(axis=0)
    # 表の中の縦線：高さの8割以上が暗い列
    vx = [i for i, v in enumerate(cols) if v > 0.8]
    rows = (a[:, :] < 150)[:, :].mean(axis=1)
    return vx, s, y0, a


def group(idx):
    out, cur = [], []
    for i in idx:
        if cur and i - cur[-1] > 2:
            out.append(sum(cur) / len(cur)); cur = []
        cur.append(i)
    if cur:
        out.append(sum(cur) / len(cur))
    return out


def table_cells(pdf, pageno, p):
    ws = p["words"]
    num = [w for w in ws if w[0] in tuple(CIRCLED)]
    # 「番号」の行（表の見出し）の丸数字
    num_y = min(w[2] for w in num if w[2] > p["H"] * 0.6)
    row_nums = sorted([w for w in num if abs(w[2] - num_y) < 3], key=lambda w: w[1])
    label = [w for w in ws if w[0] == "確認問題" and w[1] < 60 and w[2] > num_y]
    ox_y = label[0][2]
    top = num_y - 10
    bottom = p["H"] - 40
    vx, s, y0, a = grid_lines(pdf, pageno, p, top, bottom)
    vlines = group(vx)  # px
    # 横線：表の幅の8割以上が暗い行
    import numpy as np
    x0, x1 = int(vlines[0]), int(vlines[-1])
    dark = (a[:, x0:x1] < 150).mean(axis=1)
    hl = group([i for i, v in enumerate(dark) if v > 0.8 and y0 <= i <= int(bottom * s)])
    # 「確認問題 ○×」の行を囲む上下の横線
    mid = (ox_y + 5) * s
    above = max([h for h in hl if h < mid])
    below = min([h for h in hl if h > mid])
    cells = []
    for w in row_nums:
        cx = (w[1] + w[3]) / 2 * s
        left = max([v for v in vlines if v < cx]); right = min([v for v in vlines if v > cx])
        cells.append(frac(p, left / s, above / s, right / s, below / s))
    return [CIRCLED.index(w[0]) + 1 for w in row_nums], cells


def main(pdf):
    P = pages_words(pdf)
    kinds = [page_kind(p) for p in P]
    quiz_i = kinds.index("quiz")
    test_i = kinds.index("test")
    explain_is = [i for i, k in enumerate(kinds) if k == "explain"]

    # 問題番号→単元（確認問題ページの表の「単元」行）
    qp = P[quiz_i]
    nums, cells = table_cells(pdf, quiz_i + 1, qp)
    ws = qp["words"]
    num_words = {CIRCLED.index(w[0]) + 1: w for w in ws if w[0] in tuple(CIRCLED) and w[2] > qp["H"] * 0.6}
    unit_row_y = [w for w in ws if w[0] == "単元" and w[1] < 60 and w[2] > qp["H"] * 0.6][0][2]
    units = {}
    for w in ws:
        if re.fullmatch(r"3章-\d+", w[0]) and abs(w[2] - unit_row_y) < 3:
            cx = (w[1] + w[3]) / 2
            n = min(num_words, key=lambda k: abs((num_words[k][1] + num_words[k][3]) / 2 - cx))
            units[n] = w[0]
    questions = [{"n": n, "mark": CIRCLED[n - 1], "unit": units.get(n, "")} for n in nums]

    # 解説ページ：単元の見出し（ページ上部の大きな「3章-○○」）
    explain = []
    for i in explain_is:
        p = P[i]
        heads = sorted([w for w in p["words"] if re.fullmatch(r"3章-\d+", w[0]) and w[2] < 130 and (w[4] - w[2]) > 14], key=lambda w: w[2])
        footer = p["H"] - 52
        for k, h in enumerate(heads):
            end = heads[k + 1][2] - 8 if k + 1 < len(heads) else footer
            explain.append({
                "unit": h[0], "page": i + 1,
                "heading": frac(p, 28, h[2] - 14, p["W"] - 28, h[4] + 8),
                "area": frac(p, 28, h[2] - 14, p["W"] - 28, end),
            })

    # チェックテスト：「確認問題①と同じ型」の位置から各問題の枠を決める
    tp = P[test_i]
    marks = []
    for w in tp["words"]:
        m = re.fullmatch(r"確認問題([①-⑫])と同じ型", w[0])
        if m:
            marks.append((CIRCLED.index(m.group(1)) + 1, w[1], w[2]))
    # 「確認問題①と同じ型」が1語に分かれている場合の保険
    if not marks:
        raise SystemExit("チェックテストの問題位置が見つかりません")
    ys = sorted(set(round(m[2]) for m in marks))
    xs = sorted(set(round(m[1] / 300) for m in marks))
    footer = tp["H"] - 52
    test = []
    for n, x, y in sorted(marks):
        row = [r for r in ys if abs(r - round(y)) < 4][0]
        nxt = [r for r in ys if r > row + 4]
        bottom = (nxt[0] - 24) if nxt else footer - 6
        left_col = x < tp["W"] / 2
        x0 = 30 if left_col else tp["W"] / 2 + 8
        x1 = tp["W"] / 2 - 4 if left_col else tp["W"] - 30
        test.append({"n": n, "page": test_i + 1, "rect": frac(tp, x0, y - 8, x1, bottom)})

    out = {
        "pages": {"quiz": quiz_i + 1, "test": test_i + 1, "explain": [i + 1 for i in explain_is]},
        "questions": questions,
        "cells": [dict(c, n=n) for n, c in zip(nums, cells)],
        "explain": explain,
        "test": test,
    }
    dst = os.path.splitext(pdf)[0] + ".json"
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("書きました:", dst)
    print(" 問題:", [(q["mark"], q["unit"]) for q in questions])
    print(" 解説の単元:", [(e["unit"], "p." + str(e["page"])) for e in explain])
    print(" チェックテスト:", [t["n"] for t in test])


if __name__ == "__main__":
    main(sys.argv[1])
