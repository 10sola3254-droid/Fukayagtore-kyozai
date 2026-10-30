#!/usr/bin/env python3
"""数学教材PDFの構造を調べる（問題番号マーカーの検出テスト）"""
import json, re, sys, pymupdf

def spans(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                if t:
                    out.append(dict(x0=s["bbox"][0], y0=s["bbox"][1], x1=s["bbox"][2], y1=s["bbox"][3],
                                    size=s["size"], color=s["color"], bold="Bold" in s["font"], text=t))
    return out

def kind(sp, H):
    head = [s for s in sp if s["y0"] < 55 and s["color"] == 16777215]
    txt = "".join(s["text"] for s in sorted(head, key=lambda s: s["x0"]))
    title = "".join(s["text"] for s in sp if 55 < s["y0"] < 95 and s["size"] > 15)
    if txt.startswith("チェックテスト"): return "test", title
    if txt.startswith("確認問題"): return "quiz", title
    if txt.startswith("解答・解説"):
        return ("ans_test" if "チェック" in title else "ans_quiz"), title
    if txt.startswith("解説"): return "explain", title
    return "other", title

def markers(sp, H):
    m = [s for s in sp if s["color"] == 16777215 and s["bold"] and re.fullmatch(r"\d{1,2}", s["text"])
         and 9.5 <= s["size"] <= 13 and 55 < s["y0"] < H - 40]
    return sorted(m, key=lambda s: (round(s["y0"] / 20), s["x0"]))

def survey(pdf):
    d = pymupdf.open(pdf)
    res = []
    for p in d:
        sp = spans(p)
        k, t = kind(sp, p.rect.height)
        ms = [int(s["text"]) for s in markers(sp, p.rect.height)]
        res.append((k, ms))
    return res

if __name__ == "__main__":
    mats = json.load(open("public/materials.json"))
    files = [m["URL"].split("/")[-1] for m in mats if m["教科"] == "数学" and m["URL"].startswith("materials/")]
    for f in files:
        try:
            r = survey("public/materials/" + f)
        except Exception as e:
            print(f, "ERR", e); continue
        print(f, " ".join(f"{k}:{''.join(str(x) for x in ms) or '-'}" for k, ms in r))
