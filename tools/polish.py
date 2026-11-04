#!/usr/bin/env python3
"""전 페이지 공통 마무리 작업 (여러 번 실행해도 결과가 같습니다).

services.py / insight.py 가 페이지를 만든 뒤 자동으로 실행됩니다.
직접 실행: python3 tools/polish.py

하는 일
1. 이미지: 작은 WebP 사본(images/opt/)을 만들고 <img>에 srcset·lazy·decoding 속성을 넣어 로딩을 빠르게 합니다.
2. 검색용 구조화 데이터(JSON-LD): 회사 주소·연락처·공식 채널을 한곳 기준으로 통일하고, 홈에 WebSite 정보를 넣습니다.
3. 브라우저 주소창 색(theme-color) 지정.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OPT = ROOT / 'images' / 'opt'
WIDTHS = (640, 1200)

# ---- 회사 정보(검색엔진에 알려 주는 기준값) --------------------------------
ADDRESS = {
    '@type': 'PostalAddress',
    'streetAddress': '언주로93길 32, Thor Prime Tower 2F',
    'addressLocality': '강남구',
    'addressRegion': '서울특별시',
    'postalCode': '06139',
    'addressCountry': 'KR',
}
SAME_AS = [
    'https://naver.me/FZoJ0jPb',
    'https://www.instagram.com/thorinterior',
    'https://blog.naver.com/yooilhannim',
    'https://youtube.com/channel/UC9PTLl61EU0pEFHhMIcXxyA',
]
CONTACTS = [
    {'@type': 'ContactPoint', 'telephone': '+82-10-2225-6775', 'contactType': 'customer service',
     'name': '대표전화', 'areaServed': 'KR', 'availableLanguage': 'ko'},
    {'@type': 'ContactPoint', 'telephone': '+82-10-8694-6775', 'contactType': 'customer service',
     'name': '추가문의', 'areaServed': 'KR', 'availableLanguage': 'ko'},
]
WEBSITE = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    '@id': 'https://thorthor.co.kr/#website',
    'url': 'https://thorthor.co.kr/',
    'name': '토르철거',
    'alternateName': 'THOR INTERIOR',
    'inLanguage': 'ko-KR',
    'publisher': {'@id': 'https://thorthor.co.kr/#business'},
}

LD_RE = re.compile(r'(<script type="application/ld\+json">)([\s\S]*?)(</script>)')
IMG_RE = re.compile(r'<img\b[^>]*>')


def html_files():
    for p in sorted(ROOT.rglob('*.html')):
        rel = p.relative_to(ROOT).parts
        if rel[0] in ('tools', 'node_modules', '.git'):
            continue
        yield p


# ---- 1. 이미지 ------------------------------------------------------------
def make_variants(stem_path):
    """images/xxx.jpg → images/opt/xxx-640.webp, xxx-1200.webp. 만든 폭 목록을 돌려줍니다."""
    try:
        from PIL import Image
    except Exception:
        return []
    made = []
    try:
        im = Image.open(stem_path)
        im.load()
    except Exception:
        return []
    OPT.mkdir(parents=True, exist_ok=True)
    for w in WIDTHS:
        if im.width <= w:
            continue
        out = OPT / f'{stem_path.stem}-{w}.webp'
        if not out.exists():
            h = round(im.height * w / im.width)
            im.convert('RGB').resize((w, h), Image.LANCZOS).save(out, 'WEBP', quality=78, method=4)
        made.append(w)
    return made


_variant_cache = {}


def variants_for(name):
    if name in _variant_cache:
        return _variant_cache[name]
    src = ROOT / 'images' / name
    widths = []
    if src.suffix.lower() in ('.jpg', '.jpeg', '.png') and src.exists() and src.stat().st_size > 30_000:
        widths = [w for w in WIDTHS if (OPT / f'{src.stem}-{w}.webp').exists()] or make_variants(src)
    _variant_cache[name] = widths
    return widths


def polish_img(tag, before, state):
    m = re.search(r'\bsrc="/images/([^"/]+)"', tag)
    if not m:
        return tag
    name = m.group(1)
    if name.startswith('logo') or 'srcset=' in tag:
        return tag
    attrs = ''
    widths = variants_for(name)
    stem = pathlib.Path(name).stem
    is_hero = (not state['first_done']) and re.search(r'class="[^"]*hero[^"]*"', before[-1500:])
    state['first_done'] = True
    if widths:
        srcset = ', '.join(f'/images/opt/{stem}-{w}.webp {w}w' for w in widths)
        full = None
        try:
            from PIL import Image
            full = Image.open(ROOT / 'images' / name).width
        except Exception:
            pass
        if full:
            srcset += f', /images/{name} {full}w'
        sizes = '100vw' if is_hero else '(max-width:600px) 100vw, 560px'
        attrs += f' srcset="{srcset}" sizes="{sizes}"'
    if is_hero:
        if 'fetchpriority=' not in tag:
            attrs += ' fetchpriority="high"'
        tag = re.sub(r'\sloading="lazy"', '', tag)
    elif 'loading=' not in tag:
        attrs += ' loading="lazy"'
    if 'decoding=' not in tag:
        attrs += ' decoding="async"'
    if tag.endswith('/>'):
        return tag[:-2].rstrip() + attrs + ' />'
    return tag[:-1].rstrip() + attrs + '>'


def polish_images(html):
    state = {'first_done': False}
    body_start = html.find('<body')
    out, last = [], 0
    for m in IMG_RE.finditer(html):
        if m.start() < body_start:
            continue
        out.append(html[last:m.start()])
        out.append(polish_img(m.group(0), html[:m.start()], state))
        last = m.end()
    out.append(html[last:])
    return ''.join(out)


# ---- 2. 구조화 데이터 -------------------------------------------------------
def polish_ld(html, is_home):
    def fix(m):
        try:
            data = json.loads(m.group(2))
        except Exception:
            return m.group(0)
        if isinstance(data, dict) and data.get('@type') == 'GeneralContractor':
            data['address'] = ADDRESS
            data['sameAs'] = SAME_AS
            data['contactPoint'] = CONTACTS
            return m.group(1) + '\n' + json.dumps(data, ensure_ascii=False, indent=2) + '\n' + m.group(3)
        return m.group(0)

    html = LD_RE.sub(fix, html)
    if is_home and '"@type": "WebSite"' not in html:
        block = '<script type="application/ld+json">\n' + json.dumps(WEBSITE, ensure_ascii=False, indent=2) + '\n</script>\n'
        html = html.replace('</head>', block + '</head>', 1)
    return html


# ---- 3. 기타 메타 -----------------------------------------------------------
def polish_meta(html):
    if 'name="theme-color"' not in html:
        html = html.replace('<meta name="viewport"', '<meta name="theme-color" content="#e31e24">\n<meta name="viewport"', 1)
    return html


def run():
    changed = []
    for p in html_files():
        src = p.read_text(encoding='utf-8')
        new = polish_images(src)
        new = polish_ld(new, p == ROOT / 'index.html')
        new = polish_meta(new)
        if new != src:
            p.write_text(new, encoding='utf-8')
            changed.append(str(p.relative_to(ROOT)))
    print(f'마무리 작업: {len(changed)}개 페이지 갱신')
    return changed


if __name__ == '__main__':
    run()
    sys.exit(0)
