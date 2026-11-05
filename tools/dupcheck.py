"""페이지 안에서 '눈으로 같은 사진'(파일명만 다른 사본 포함)이 두 번 이상 나오는지 검사합니다.
python3 tools/dupcheck.py  → 문제 있으면 목록 출력, 종료코드 1
"""
import re, sys, glob
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
_cache = {}


def dhash(p, n=16):
    if p in _cache:
        return _cache[p]
    try:
        im = Image.open(p).convert('L').resize((n + 1, n))
    except Exception:
        _cache[p] = None
        return None
    px = list(im.get_flattened_data() if hasattr(im, 'get_flattened_data') else im.getdata()); v = 0
    for r in range(n):
        for c in range(n):
            v = (v << 1) | (px[r * (n + 1) + c] > px[r * (n + 1) + c + 1])
    _cache[p] = v
    return v


def page_images(html):
    srcs = re.findall(r'<img[^>]+src="(/images/[^"]+)"', html)
    srcs += [m for m in re.findall(r'style="background-image:url\((/images/[^)]+)\)', html)]
    return [s for s in srcs if 'logo' not in s]


def check(files, thr=40):
    bad = []
    for f in files:
        html = Path(f).read_text(encoding='utf-8')
        imgs = page_images(html)
        hs = []
        for s in dict.fromkeys(imgs):
            h = dhash(ROOT / s.lstrip('/'))
            if h is not None:
                hs.append((s, h))
        for i in range(len(hs)):
            for j in range(i + 1, len(hs)):
                if bin(hs[i][1] ^ hs[j][1]).count('1') <= thr:
                    bad.append((f, hs[i][0], hs[j][0]))
        for s in set(imgs):
            if imgs.count(s) > 1:
                bad.append((f, s, s))
    return bad


if __name__ == '__main__':
    files = sorted(set(glob.glob(str(ROOT / '*.html')) + glob.glob(str(ROOT / 'blog/*.html')) + glob.glob(str(ROOT / 'insight/*.html'))))
    bad = check(files)
    for b in bad:
        print(Path(b[0]).name, b[1], b[2])
    print(f'중복 의심 {len(bad)}건')
    sys.exit(1 if bad else 0)
