"""教材PDFを軽くする（ページの大きさ・文字の位置は変えない）

使い方:
  python3 tools/compress_pdfs.py public/materials/*.pdf
  python3 tools/compress_pdfs.py --dry public/materials/xxx.pdf   # 書きかえずに結果だけ見る

やっていること
  1. 大きすぎる画像（200dpi超）を150dpiに小さくする
     （写真＝JPEG品質75、図・グラフ＝くっきりのまま可逆圧縮。透明部分もそのまま）
  2. 同じ中身のフォント・画像が何回も入っているのを1つにまとめる
  3. 文字・線のデータを圧縮して保存する
  → 文字の位置は変わらないので、数学の○×用 .json や理科の .sets.json は作り直さなくてよい
  元より3%以上小さくならなかったファイルは、そのまま残す。
"""
import io
import os
import sys
import zlib

import pikepdf
import pymupdf
from PIL import Image

DPI_MAX, DPI_TARGET, JPEG_Q = 200, 150, 75
DRY = "--dry" in sys.argv
files = [a for a in sys.argv[1:] if not a.startswith("--")]


def looks(doc):
    """見た目チェック用の小さなグレー画像"""
    return [p.get_pixmap(dpi=50, colorspace=pymupdf.csGRAY).samples for p in doc]


def diff(a, b):
    """ページごとの見た目のちがい（0〜255の平均）の最大"""
    worst = 0
    for x, y in zip(a, b):
        if len(x) != len(y):
            return 255
        worst = max(worst, sum(abs(i - j) for i, j in zip(x, y)) / max(1, len(x)))
    return worst


def words(doc):
    return [[tuple(round(v, 1) for v in w[:4]) + (w[4],) for w in p.get_text("words")] for p in doc]


def shown_size(path):
    """画像ごとに、ページ上でいちばん大きく表示されている幅・高さ（pt）"""
    out = {}
    d = pymupdf.open(path)
    for p in d:
        for info in p.get_image_info(xrefs=True):
            x = info.get("xref")
            if not x:
                continue
            b = pymupdf.Rect(info["bbox"])
            w, h = abs(b.width), abs(b.height)
            ow, oh = out.get(x, (0, 0))
            out[x] = (max(ow, w), max(oh, h))
    d.close()
    return out


def shrink_images(path, tmp):
    shown = shown_size(path)
    pdf = pikepdf.open(path)
    n = 0
    done_masks = set()
    for obj in pdf.objects:
        if not isinstance(obj, pikepdf.Stream) or obj.get("/Subtype") != "/Image":
            continue
        if obj.get("/ImageMask") or obj.get("/BitsPerComponent") != 8 or "/Decode" in obj:
            continue
        cs = obj.get("/ColorSpace")
        if cs not in ("/DeviceRGB", "/DeviceGray"):
            continue
        xref = obj.objgen[0]
        if xref not in shown:
            continue
        sw, sh = shown[xref]
        W, H = int(obj.Width), int(obj.Height)
        if sw <= 1 or sh <= 1:
            continue
        dpi = min(W / (sw / 72), H / (sh / 72))
        if dpi <= DPI_MAX:
            continue
        k = DPI_TARGET / dpi
        nw, nh = max(1, round(W * k)), max(1, round(H * k))
        sm = obj.get("/SMask")                           # 透明部分（影など）
        if sm is not None and not (int(sm.Width) == W and int(sm.Height) == H
                                   and sm.get("/BitsPerComponent") == 8
                                   and sm.get("/Filter") in ("/FlateDecode", None)
                                   and "/Matte" not in sm and sm.objgen not in done_masks):
            continue                                     # あつかいにくい透明はさわらない
        mode = "RGB" if cs == "/DeviceRGB" else "L"
        try:
            if obj.get("/Filter") == "/DCTDecode":
                im = Image.open(io.BytesIO(obj.read_raw_bytes())).convert(mode)
            elif obj.get("/Filter") in ("/FlateDecode", None):
                im = Image.frombytes(mode, (W, H), obj.read_bytes())
            else:
                continue
            m = Image.frombytes("L", (W, H), sm.read_bytes()) if sm is not None else None
        except Exception:
            continue
        im = im.resize((nw, nh), Image.LANCZOS)
        if obj.get("/Filter") == "/DCTDecode":          # 写真 → JPEG
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=JPEG_Q, optimize=True)
            obj.write(buf.getvalue(), filter=pikepdf.Name.DCTDecode)
        else:                                           # 図・グラフ → くっきり
            obj.write(zlib.compress(im.tobytes(), 9), filter=pikepdf.Name.FlateDecode)
        if "/DecodeParms" in obj:
            del obj["/DecodeParms"]
        obj.Width, obj.Height = nw, nh
        if m is not None:                                # 透明部分も同じ大きさに（/Decode はそのまま）
            m = m.resize((nw, nh), Image.LANCZOS)
            sm.write(zlib.compress(m.tobytes(), 9), filter=pikepdf.Name.FlateDecode)
            if "/DecodeParms" in sm:
                del sm["/DecodeParms"]
            sm.Width, sm.Height = nw, nh
            done_masks.add(sm.objgen)
        n += 1
    pdf.save(tmp)
    pdf.close()
    return n


before_total = after_total = 0
for path in files:
    if not path.lower().endswith(".pdf"):
        continue
    size0 = os.path.getsize(path)
    src = pymupdf.open(path)
    sizes0 = [tuple(round(v, 2) for v in p.rect) for p in src]
    words0 = words(src)
    look0 = looks(src)
    src.close()

    mid, tmp = path + ".mid", path + ".tmp"
    nimg = shrink_images(path, mid)
    doc = pymupdf.open(mid)
    doc.save(tmp, garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, use_objstms=1)
    doc.close()
    os.remove(mid)

    chk = pymupdf.open(tmp)
    dv = diff(look0, looks(chk))
    ok = ([tuple(round(v, 2) for v in p.rect) for p in chk] == sizes0 and words(chk) == words0
          and dv < 2.0)
    chk.close()
    size1 = os.path.getsize(tmp)

    before_total += size0
    if ok and size1 < size0 * 0.97 and not DRY:
        os.replace(tmp, path)
        after_total += size1
        mark = "OK"
    else:
        os.remove(tmp)
        after_total += size1 if (DRY and ok and size1 < size0) else size0
        mark = "そのまま" if ok else "⚠変化大"
    print(f"{mark:6} {os.path.basename(path)}  {size0 // 1024}KB → {size1 // 1024}KB  (画像{nimg}, 見た目差{dv:.2f})")

print(f"\n合計 {before_total / 1048576:.1f}MB → {after_total / 1048576:.1f}MB")
