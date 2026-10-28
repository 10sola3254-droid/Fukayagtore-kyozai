#!/usr/bin/env python3
"""理科Gトレ教材（要点と対策）を「まとめ」「A問題」「B問題」の3つに分ける。

使い方:
    python3 tools/split_rika.py public/materials/rika-yoten-01-r2.pdf [...]
    python3 tools/split_rika.py --all          # public/materials/rika-yoten-*.pdf すべて

できるもの（PDFと同じフォルダ）:
    xxx-M.pdf        … 解説まとめページだけ
    xxx-A.pdf        … A問題 ＋ A問題の解答
    xxx-B.pdf        … B問題 ＋ B問題の解説
    xxx.sets.json    … アプリが「まとめ／A問題／B問題」の切りかえ・ダウンロード・印刷に使う
                        （印刷できるのは まとめ と A問題 だけ。B問題は "print": false）

ページの見分け方: 各ページ上の帯の文字
    「A 問題」「A 問題 解答」→ A ／ 「B 問題」「B 問題 解説」→ B ／ それ以外 → まとめ（補強・計算ページもふくむ）
A問題もB問題もない教材（まとめだけ）は、分けずにとばす。
"""
import glob
import json
import os
import re
import sys

from pypdf import PdfReader, PdfWriter

HEAD = re.compile(r"^(?:[AB])?([AB])問題(解答|解説)?")
# 新しい形：帯の左に単元タイトル、右に「A 問題①」「B 問題 解説②」など（例 27〜30）
HEAD2 = re.compile(r"^\d{1,2}[^0-9]{2,40}?([AB])問題(解答|解説)?")


def classify(page):
    text = re.sub(r"\s+", "", page.extract_text() or "")
    m = HEAD.match(text[:40]) or HEAD2.match(text[:60])
    if not m:
        return "m"
    return m.group(1) + ("ans" if m.group(2) else "")


def split(path):
    reader = PdfReader(path)
    kinds = [classify(p) for p in reader.pages]
    summary = [i for i, k in enumerate(kinds) if k == "m"]
    a = [i for i, k in enumerate(kinds) if k.startswith("A")]
    b = [i for i, k in enumerate(kinds) if k.startswith("B")]
    base = os.path.splitext(path)[0]
    label = "".join({"m": "ま", "A": "A", "Aans": "a", "B": "B", "Bans": "b"}[k] for k in kinds)

    if not a and not b:
        print(f"  {os.path.basename(path)}: A・B問題なし（{label}）→ とばす")
        for old in (base + "-M.pdf", base + "-A.pdf", base + "-B.pdf", base + ".sets.json"):
            if os.path.exists(old):
                os.remove(old)
        return
    # まとめページが問題のあとにまざっていたら要確認
    first_q = min(a + b)
    late = [i + 1 for i in summary if i > first_q]
    if late:
        print(f"  ⚠ {os.path.basename(path)}: 問題のあとに『まとめ』と判定したページ {late}（{label}）")

    sets = []
    for key, qs, name, desc, can_print in (
        ("M", summary, "まとめ", "解説まとめページ", True),
        ("A", a, "A問題", "A問題 ＋ 解答", True),
        ("B", b, "B問題", "B問題 ＋ 解説", False),
    ):
        if not qs:
            continue
        w = PdfWriter()
        for i in qs:
            w.add_page(reader.pages[i])
        w.compress_identical_objects()
        out = f"{base}-{key}.pdf"
        with open(out, "wb") as f:
            w.write(f)
        sets.append({
            "key": key,
            "name": name,
            "desc": desc,
            "file": os.path.basename(out),
            "pages": len(qs),
            "print": can_print,
        })

    with open(base + ".sets.json", "w", encoding="utf-8") as f:
        json.dump({"sets": sets}, f, ensure_ascii=False, indent=1)
    print(f"  {os.path.basename(path)}: {label} → " +
          " / ".join(f"{s['key']}={s['pages']}ページ" for s in sets))


def main(args):
    if not args or args == ["--all"]:
        here = os.path.dirname(os.path.abspath(__file__))
        args = sorted(p for p in glob.glob(os.path.join(here, "..", "public", "materials", "rika-yoten-*.pdf"))
                      if not re.search(r"-[AB]\.pdf$", p))
    for p in args:
        split(p)


if __name__ == "__main__":
    main(sys.argv[1:])
