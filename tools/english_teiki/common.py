def N(jp, ch, order, think, ans, why, miss, **kw):
    """「ね」の7段解説つきの1問（例題・並べかえ・英作文）"""
    d = dict(jp=jp, chunks=ch, order=order, think=think, ans=ans, why=why, miss=miss)
    d.update(kw)
    d.setdefault("q", jp)
    return d

def S(q, a, exp, hint=None):
    """ふつうの1問（選択・補充・書きかえ）"""
    d = dict(q=q, a=a, exp=exp)
    if hint: d["hint"] = hint
    return d

H = True  # 日本語にない語のしるし
