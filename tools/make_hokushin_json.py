#!/usr/bin/env python3
"""
北辰チェックテストPDFから「北辰モード」用の位置データ（.json）を作る。

  python3 tools/make_hokushin_json.py public/materials/hokushin-xxx.pdf map.json

map.json（作問時に用意）:
  {"rows": [["1(1)", "A"], ["1(2)", "A"], ...],
   "leg":  {"A": ["中2 式の計算", "1章-3〜8 多項式の計算（…）"], ...}}

PDF側の前提: 「答え合わせ表」の見出しがあるページに、
  1行目「問題」＋各問題のラベル、2行目「○×」（空のマス）、3行目「教材」＋記号 の表がある。
できるもの: PDFと同じ名前の .json
  {"mode":"hokushin","pages":{"quiz":2},"questions":[{"n":1,"label":"1(1)","unit":…,"topic":…}],"cells":[…]}
"""
import json, re, subprocess, sys, os, tempfile
from xml.etree import ElementTree as ET


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True).stdout


def pages_words(pdf):
    xml = run(["pdftotext", "-bbox", pdf, "-"]).decode("utf-8")
    xml = re.sub(r"<!DOCTYPE[^>]*>", "", xml).replace('xmlns="http://www.w3.org/1999/xhtml"', "")
    root = ET.fromstring(xml)
    out = []
    for pg in root.iter("page"):
        W, H = float(pg.get("width")), float(pg.get("height"))
        words = [(w.text or "", float(w.get("xMin")), float(w.get("yMin")), float(w.get("xMax")), float(w.get("yMax")))
                 for w in pg.iter("word")]
        out.append({"W": W, "H": H, "words": words})
    return out


def group(idx):
    out, cur = [], []
    for i in idx:
        if cur and i - cur[-1] > 2:
            out.append(sum(cur) / len(cur)); cur = []
        cur.append(i)
    if cur:
        out.append(sum(cur) / len(cur))
    return out


def render_gray(pdf, pageno, dpi=200):
    from PIL import Image
    import numpy as np
    with tempfile.TemporaryDirectory() as td:
        run(["pdftoppm", "-r", str(dpi), "-f", str(pageno), "-l", str(pageno), "-gray", "-png", pdf, td + "/g"])
        f = [x for x in os.listdir(td) if x.endswith(".png")][0]
        return np.array(Image.open(os.path.join(td, f)).convert("L"))


def main_vertical(pdf, mapfile, P, pageno, p):
    """中1北辰テストの形式: 縦長の表(問題｜内容｜○×｜まちがえたら復習する教材)。
    map.json: {"rows": [["1 (1)〜(3)", "A"], ...], "leg": {"A": [単元, 細かい単元], ...}}
    rows のラベルは表の「問題」列の文字(空白なし)と一致させる。"""
    mp = json.load(open(mapfile, encoding="utf-8"))
    ws = p["words"]
    ox = [w for w in ws if w[0] == "○×"][0]
    mon = [w for w in ws if w[0] == "問題" and abs(w[2] - ox[2]) < 3][0]
    naiyo = [w for w in ws if w[0] == "内容" and abs(w[2] - ox[2]) < 3][0]
    a = render_gray(pdf, pageno)
    s = 200 / 72.0
    W, H = p["W"], p["H"]
    # 表の範囲: 見出し行から、問題列の最後の文字の下まで
    col_words = [w for w in ws if w[2] > ox[4] and w[1] < naiyo[1] - 5 and w[1] > 20]
    bottom_pt = max(w[4] for w in col_words) + 14
    y0, y1 = int((ox[2] - 6) * s), int(bottom_pt * s)
    # 縦線(うすい灰色も拾う): 表の高さの6割以上
    reg = a[y0:y1, :] < 225
    vx = group([i for i, v in enumerate(reg.mean(axis=0)) if v > 0.6])
    cx = (ox[1] + ox[3]) / 2 * s
    left = max(v for v in vx if v < cx); right = min(v for v in vx if v > cx)
    # 横線: ○×列の中で、幅の8割以上が暗い行
    dark = (a[y0:y1, int(left) + 3:int(right) - 3] < 225).mean(axis=1)
    hl = [y0 + i for i in group([i for i, v in enumerate(dark) if v > 0.8])]
    # 行: 問題列の文字を y で束ねる
    rows_y = []
    for w in sorted(col_words, key=lambda w: w[2]):
        if rows_y and w[2] - rows_y[-1][1] < 14:
            rows_y[-1][1] = max(rows_y[-1][1], w[4]); rows_y[-1][2].append(w)
        else:
            rows_y.append([w[2], w[4], [w]])
    # 行の境界(横線)でさらに区切る: 2行に折り返したラベルは同じ行
    cells, labels = [], []
    for k in range(len(hl) - 1):
        top, bot = hl[k], hl[k + 1]
        inside = [w for w in col_words if top / s < (w[2] + w[4]) / 2 < bot / s]
        if not inside:
            continue
        label = "".join(w[0] for w in sorted(inside, key=lambda w: (round(w[2]), w[1])))
        labels.append(label)
        cells.append({"x": round(left / s / W, 4), "y": round(top / s / H, 4), "w": round((right - left) / s / W, 4), "h": round((bot - top) / s / H, 4)})
    rows = mp["rows"]
    nz = lambda t: re.sub(r"\s", "", t)
    if [nz(l) for l in labels] != [nz(r[0]) for r in rows]:
        print("⚠ 行ラベルが合いません\n  PDF:", labels, "\n  map:", [r[0] for r in rows])
    questions = []
    for n, (lab, row) in enumerate(zip(labels, rows), 1):
        unit, topic = mp["leg"][row[1]]
        questions.append({"n": n, "label": lab, "unit": unit, "topic": topic})
        cells[n - 1]["n"] = n
    out = {"mode": "hokushin", "pages": {"quiz": pageno}, "questions": questions, "cells": cells[:len(questions)]}
    dst = re.sub(r"\.pdf$", ".json", pdf, flags=re.I)
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    print("OK:", dst, len(questions), "行")


def main(pdf, mapfile):
    mp = json.load(open(mapfile, encoding="utf-8"))
    P = pages_words(pdf)
    pageno = None
    for i, p in enumerate(P):
        if any(w[0].startswith("答え合わせ表") for w in p["words"]):
            pageno = i + 1; p_ = p
    if pageno is None:
        sys.exit("⚠ 「答え合わせ表」が見つかりません")
    p = p_
    ws = p["words"]
    if any(w[0] == "まちがえたら復習する教材" for w in ws):
        return main_vertical(pdf, mapfile, P, pageno, p)
    title_y = [w for w in ws if w[0].startswith("答え合わせ表")][0][2]
    ox = [w for w in ws if w[0] == "○×" and w[2] > title_y][0]
    mon = [w for w in ws if w[0] == "問題" and w[2] > title_y and w[2] < ox[2]][-1]
    labels = sorted([w for w in ws if abs(w[2] - mon[2]) < 4 and w[1] > mon[3]], key=lambda w: w[1])
    rows = mp["rows"]
    if len(labels) != len(rows):
        print("⚠ ラベル数が合いません: PDF", [w[0] for w in labels], "map", [r[0] for r in rows])
    # 画像から表の縦線・横線を探す
    from PIL import Image
    import numpy as np
    dpi = 200
    with tempfile.TemporaryDirectory() as td:
        run(["pdftoppm", "-r", str(dpi), "-f", str(pageno), "-l", str(pageno), "-gray", "-png", pdf, td + "/g"])
        f = [x for x in os.listdir(td) if x.endswith(".png")][0]
        a = np.array(Image.open(os.path.join(td, f)).convert("L"))
    s = dpi / 72.0
    y0, y1 = int((mon[2] - 4) * s), int((ox[4] + 12) * s)
    reg = a[y0:y1, :] < 150
    vx = group([i for i, v in enumerate(reg.mean(axis=0)) if v > 0.45])
    x0, x1 = int(vx[0]), int(vx[-1])
    dark = (a[y0:y1, x0:x1] < 150).mean(axis=1)
    hl = [y0 + i for i in group([i for i, v in enumerate(dark) if v > 0.8])]
    mid = (ox[2] + ox[4]) / 2 * s
    above = max(h for h in hl if h < mid); below = min(h for h in hl if h > mid)
    W, H = p["W"], p["H"]
    r = lambda v: round(v, 4)
    cells, questions = [], []
    for n, (w, row) in enumerate(zip(labels, rows), 1):
        cx = (w[1] + w[3]) / 2 * s
        left = max(v for v in vx if v < cx); right = min(v for v in vx if v > cx)
        cells.append({"x": r(left / s / W), "y": r(above / s / H), "w": r((right - left) / s / W), "h": r((below - above) / s / H), "n": n})
        unit, topic = mp["leg"][row[1]]
        questions.append({"n": n, "label": row[0], "unit": unit, "topic": topic})
    out = {"mode": "hokushin", "pages": {"quiz": pageno}, "questions": questions, "cells": cells}
    dst = re.sub(r"\.pdf$", ".json", pdf, flags=re.I)
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    print("OK:", dst, len(cells), "マス")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
