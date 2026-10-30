#!/usr/bin/env python3
"""
英語Gトレ教材PDFの「解答・解説」ページの各「問N」見出しの下に、その大問の問題文
（確認問題／チェックテストのページから切り出し、ヒント囲み・答え欄は消す）を
小さくグレー枠で載せた版を作る。ページ数は変えない（入りきらないぶんは解説側を縮小）。

  python3 tools/add_problem_text_english.py public/materials/english-xxx.pdf [出力.pdf]
"""
import re, subprocess, sys
from xml.etree import ElementTree as ET
import pymupdf

PROB_SCALE = 0.72
MIN_SCALE = 0.62
GAP = 5
GRAY = (0.955, 0.955, 0.955)


def words_of(pdf):
    xml = subprocess.run(["pdftotext", "-bbox", pdf, "-"], check=True, capture_output=True).stdout.decode()
    xml = re.sub(r"<!DOCTYPE[^>]*>", "", xml).replace('xmlns="http://www.w3.org/1999/xhtml"', "")
    pages = []
    for pg in ET.fromstring(xml).iter("page"):
        pages.append([dict(t=w.text or "", x0=float(w.get("xMin")), y0=float(w.get("yMin")),
                           x1=float(w.get("xMax")), y1=float(w.get("yMax"))) for w in pg.iter("word")])
    return pages


def head_text(ws):
    return "".join(w["t"] for w in ws if w["y0"] < 95)


def section_heads(WP):
    """セクション見出し（『確認問題』『確認問題 解答・解説』『チェックテスト』…）の位置を
    [(page, y, (quiz|test, problem|answer))] で返す。ページの途中から始まるセクションにも対応"""
    heads = []
    for pi, ws in enumerate(WP):
        for w in ws:
            if w["t"] not in ("確認問題", "チェックテスト") or w["x0"] > 60 or w["y0"] < 40 or (w["y1"] - w["y0"]) < 11:
                continue
            line = "".join(v["t"] for v in ws if abs(v["y0"] - w["y0"]) < 6 and v["x0"] >= w["x0"])
            kind = "quiz" if w["t"] == "確認問題" else "test"
            part = "answer" if ("解答" in line or "解説" in line) else "problem"
            heads.append((pi, w["y0"], (kind, part)))
    return sorted(heads)


def role_at(heads, pi, y):
    cur = None
    for hp, hy, r in heads:
        if (hp, hy) <= (pi, y):
            cur = r
    return cur


def mon_anchors(ws, H):
    """『問N』見出し（行頭）を (n, y0, y1) で返す"""
    out = []
    for w in ws:
        m = re.fullmatch(r"問([0-9０-９]+)", w["t"])
        if not m or w["x0"] > 80 or w["y0"] < 40 or w["y0"] > H - 40:
            continue
        if any(abs(v["y0"] - w["y0"]) < 5 and v["x1"] <= w["x0"] + 1 for v in ws if v is not w):
            continue
        n = int(m.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789")))
        out.append(dict(n=n, y0=w["y0"], y1=w["y1"]))
    best = {}
    for a in out:
        if a["n"] not in best or a["y0"] < best[a["n"]]["y0"]:
            best[a["n"]] = a
    return sorted(best.values(), key=lambda a: a["y0"])


def band_rect(page, a, W):
    """問N見出しの水色の帯の矩形"""
    for d in page.get_drawings():
        r = d["rect"]
        if r.y0 <= a["y0"] + 1 and r.y1 >= a["y1"] - 1 and r.width > W * 0.5 and r.height < 30:
            return r
    return None


def band_or_line(page, a, W):
    """帯があればその矩形、なければ『問N』の行頭だけ（高さ0の帯）を返す"""
    r = band_rect(page, a, W)
    return r if r is not None else pymupdf.Rect(28, a["y0"] - 4, W - 28, a["y0"] - 4)


def footer_y(ws, page, W, H):
    fy = H - 44
    fw = [w for w in ws if w["y0"] > H - 46]
    if fw:
        fy = min(w["y0"] for w in fw) - 4
    for d in page.get_drawings():
        r = d["rect"]
        if r.y0 > H - 60 and r.width > W * 0.8 and r.height < 3:
            fy = min(fy, r.y0 - 3)
    return fy


def problem_blocks(src, WP, heads, role):
    """role(quiz/test) の問題ページから 問N → (page index, [strip rects], total height) を集める。
    strip は文字の行・表だけ（ヒント囲み・「答え」欄・空白は含めない）"""
    out = {}
    for pi, ws in enumerate(WP):
        page = src[pi]
        W, H = page.rect.width, page.rect.height
        an_all = mon_anchors(ws, H)
        an = [a for a in an_all if role_at(heads, pi, a["y0"]) == (role, "problem")]
        if not an:
            continue
        fy = footer_y(ws, page, W, H)
        draws = [d["rect"] for d in page.get_drawings()]
        for i, a in enumerate(an):
            band = band_or_line(page, a, W)
            top = band.y1 + 1
            nxt = [x for x in an_all if x["y0"] > a["y0"]]
            # 次の問N か、次のセクション見出しの手前まで
            nh = [hy for hp, hy, _ in heads if hp == pi and hy > a["y0"]]
            bottom = band_or_line(page, nxt[0], W).y0 - 3 if nxt else fy
            if nh:
                bottom = min(bottom, min(nh) - 6)
            inw = [w for w in ws if top <= w["y0"] < bottom]
            # ヒント囲みの矩形
            hints = []
            for hw in [w for w in inw if "ヒント" in w["t"]]:
                c = [d for d in draws if d.x0 <= hw["x0"] + 1 and d.x1 >= hw["x1"] - 1 and d.y0 <= hw["y0"] + 1
                     and d.y1 >= hw["y1"] - 1 and d.height < 120 and d.width > W * 0.4]
                hints.append(min(c, key=lambda d: d.width * d.height) if c else pymupdf.Rect(28, hw["y0"] - 3, W - 28, hw["y1"] + 3))
            def in_hint(y0, y1):
                c = (y0 + y1) / 2
                return any(h.y0 - 2 <= c <= h.y1 + 2 for h in hints)
            spans = []
            for w in inw:
                if (w["t"].startswith("答え") and w["x0"] < 60) or in_hint(w["y0"], w["y1"]) or "ヒント" in w["t"]:
                    continue
                # 答え欄のラベル（「日本語」「スラッシュ入り」など、左はしの小さい字でその行にほかの語がない）
                if w["x0"] < 60 and (w["y1"] - w["y0"]) < 8.6 and not any(abs(v["y0"] - w["y0"]) < 5 and v["x0"] > w["x1"] for v in inw):
                    continue
                spans.append([w["y0"] - 1.5, w["y1"] + 1.5])
            # 表（選択肢・語群の表）
            for d in draws:
                if d.y0 >= top - 1 and d.y1 <= bottom and 8 < d.height < 400 and d.width > 40 \
                        and not any(d.intersects(h) for h in hints) and not in_hint(d.y0, d.y1):
                    spans.append([d.y0 - 0.5, d.y1 + 0.5])
            if not spans:
                continue
            spans.sort()
            strips = []
            for y0, y1 in spans:
                if strips and y0 <= strips[-1][1] + 3:
                    strips[-1][1] = max(strips[-1][1], y1)
                else:
                    strips.append([y0, y1])
            rects = [pymupdf.Rect(28, y0, W - 28, y1) for y0, y1 in strips]
            if a["n"] in out:
                print(f"  ⚠ {role} 問{a['n']} が2回出てくる（p.{out[a['n']][0]+1}, p.{pi+1}）")
            out[a["n"]] = (pi, rects, sum(r_.height for r_ in rects) + 2 * (len(rects) - 1))
    return out


def build(pdf, out):
    src = pymupdf.open(pdf)
    WP = words_of(pdf)
    heads = section_heads(WP)
    W, H = src[0].rect.width, src[0].rect.height
    blocks = {"quiz": problem_blocks(src, WP, heads, "quiz"), "test": problem_blocks(src, WP, heads, "test")}
    if not blocks["quiz"] and not blocks["test"]:
        print("  × 問題ページ（問N 見出し）が見つからない"); return False
    dst = pymupdf.open()
    font = pymupdf.Font("japan")
    placed = 0
    ok = True
    for pi in range(len(src)):
        page = dst.new_page(width=W, height=H)
        ws = WP[pi]
        an = [a for a in mon_anchors(ws, H) if (role_at(heads, pi, a["y0"]) or ("", ""))[1] == "answer"]
        if not an:
            page.show_pdf_page(page.rect, src, pi)
            continue
        role = role_at(heads, pi, an[0]["y0"])[0]
        if any(role_at(heads, pi, a["y0"])[0] != role for a in an):
            print(f"  ⚠ p.{pi+1} に確認問題とチェックテストの解答が混ざっている"); ok = False
        sp = src[pi]
        fy = footer_y(ws, sp, W, H)
        # 見出し帯（最初の問N帯の上まで）
        first_band = band_or_line(sp, an[0], W)
        head_end = first_band.y0 - 1
        page.show_pdf_page(pymupdf.Rect(0, 0, W, head_end), src, pi, clip=pymupdf.Rect(0, 0, W, head_end))
        page.show_pdf_page(pymupdf.Rect(0, fy, W, H), src, pi, clip=pymupdf.Rect(0, fy, W, H))
        # 区間：問N帯 ～ 次の帯の手前（最後は本文の下端まで）
        segs = []
        for i, a in enumerate(an):
            band = band_or_line(sp, a, W)
            top = band.y0 - 1
            if i + 1 < len(an):
                bottom = band_or_line(sp, an[i + 1], W).y0 - 1
            else:
                ys = [w["y1"] for w in ws if top < w["y0"] < fy] + [d["rect"].y1 for d in sp.get_drawings() if top < d["rect"].y0 and d["rect"].y1 < fy - 1]
                bottom = min(fy, max(ys) + 6) if ys else fy
            segs.append(dict(n=a["n"], band=band, body=pymupdf.Rect(0, band.y1, W, bottom)))
        avail = fy - head_end - 2
        need = 0
        for s in segs:
            need += s["band"].height + 1 + s["body"].height
            b = blocks[role].get(s["n"])
            if b:
                need += b[2] * PROB_SCALE + 6 + GAP * 2
        scale = min(1.0, avail / need)
        if scale < MIN_SCALE:
            print(f"  ⚠ p.{pi+1} 縮小率 {scale:.2f}（{MIN_SCALE} 未満）"); ok = False
        elif scale < 0.8:
            print(f"  p.{pi+1} 縮小率 {scale:.2f}")
        y = head_end + 1
        for s in segs:
            band = s["band"]
            if band.height > 1:
                page.show_pdf_page(pymupdf.Rect(0, y, W * scale, y + band.height * scale), src, pi, clip=pymupdf.Rect(0, band.y0, W, band.y1))
                y += band.height * scale + GAP * scale
            else:
                y += 2 * scale
            b = blocks[role].get(s["n"])
            if b is None:
                print(f"  ⚠ p.{pi+1} 問{s['n']} の問題文が {role} の問題ページに見つからない"); ok = False
            else:
                spi, rects, th = b
                k = PROB_SCALE * scale
                pw, ph = (W - 56) * k, th * k
                x0 = 28
                box = pymupdf.Rect(x0, y, x0 + pw + 6, y + ph + 6)
                sh = page.new_shape(); sh.draw_rect(box); sh.finish(color=(0.72, 0.72, 0.72), fill=GRAY, width=0.5); sh.commit()
                yy = y + 3
                for rc in rects:
                    tg = pymupdf.Rect(x0 + 3, yy, x0 + 3 + pw, yy + rc.height * k)
                    page.show_pdf_page(tg, src, spi, clip=rc)
                    yy = tg.y1 + 2 * k
                fs = 6.5 * max(scale, 0.8)
                tw = font.text_length("問題", fontsize=fs)
                page.insert_text((box.x1 - tw - 3, y + 3 + fs), "問題", fontsize=fs, fontname="japan", color=(0.45, 0.45, 0.45))
                y = box.y1 + GAP * scale
                placed += 1
            body = s["body"]
            tg = pymupdf.Rect(0, y, W, y + body.height * scale)
            # 横は W 幅のまま置くと縦だけ縮んで文字がつぶれるので、縮小時は左寄せで等倍縮小
            tg = pymupdf.Rect(0, y, W * scale, y + body.height * scale) if scale < 1 else tg
            if body.height > 1:
                page.show_pdf_page(tg, src, pi, clip=body)
            y = tg.y1
    if not placed:
        print("  × 問題枠を1つも置けなかった"); return False
    if not ok:
        print("  × 形が合わないので出力しません（元のまま）"); return False
    dst.save(out, garbage=4, deflate=True)
    print(f"書きました: {out}  問題枠 {placed}")
    return True


if __name__ == "__main__":
    pdf = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else re.sub(r"(-r\d+)?\.pdf$", "", pdf) + "-q.pdf"
    sys.exit(0 if build(pdf, out) else 1)
