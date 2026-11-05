#!/usr/bin/env python3
"""전 페이지 공통 마무리 작업 (여러 번 실행해도 결과가 같습니다).

services.py / insight.py 가 페이지를 만든 뒤 자동으로 실행됩니다.
직접 실행: python3 tools/polish.py

하는 일
1. 이미지: 작은 WebP 사본(images/opt/)을 만들고 <img>에 srcset·lazy·decoding 속성을 넣어 로딩을 빠르게 합니다.
2. 검색용 구조화 데이터(JSON-LD): 회사 주소·연락처·공식 채널을 한곳 기준으로 통일하고, 홈에 WebSite 정보를 넣습니다.
3. 브라우저 주소창 색(theme-color) 지정.
4. 페이지 분류(content/taxonomy.json)에 따라 경로(BreadcrumbList)·서비스·글(Article) 구조화 데이터를 채우고,
   화면에 보이지 않는 FAQ 구조화 데이터는 제거하며, 소셜 공유 태그(twitter·og:locale)와 이미지 크기 속성을 넣습니다.
"""
import html as htmllib
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
     'name': '대표번호1', 'areaServed': 'KR', 'availableLanguage': 'ko'},
    {'@type': 'ContactPoint', 'telephone': '+82-10-8694-6775', 'contactType': 'customer service',
     'name': '대표번호2', 'areaServed': 'KR', 'availableLanguage': 'ko'},
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
        if not out.exists() or out.stat().st_size < 200:
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
        widths = [w for w in WIDTHS if (OPT / f'{src.stem}-{w}.webp').exists() and (OPT / f'{src.stem}-{w}.webp').stat().st_size >= 200] or make_variants(src)
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
    if 'application/rss+xml' not in html:
        feeds = ('<link rel="alternate" type="application/rss+xml" title="토르철거 인사이트" href="/insight-rss.xml">\n'
                 '<link rel="alternate" type="application/rss+xml" title="토르철거 철거 정보" href="/rss.xml">\n')
        html = html.replace('</head>', feeds + '</head>', 1)
    if 'name="theme-color"' not in html:
        html = html.replace('<meta name="viewport"', '<meta name="theme-color" content="#e31e24">\n<meta name="viewport"', 1)
    return html


# ---- 4. 분류(taxonomy) 기반 SEO ----------------------------------------------
SITE = 'https://thorthor.co.kr'
LOGO_URL = SITE + '/images/864c5d29e51fe.jpg'
TAX_FILE = ROOT / 'content' / 'taxonomy.json'
TAG_RE = re.compile(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>')


def load_tax():
    try:
        return json.loads(TAX_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {'pages': {}, 'articles': {}, 'site': {}}


def url_of(path):
    rel = path.relative_to(ROOT).as_posix()
    return '/' if rel == 'index.html' else '/' + rel[:-5]


def visible_text(html):
    body = html[html.find('<body'):]
    return re.sub(r'\s+', ' ', htmllib.unescape(TAG_RE.sub(' ', body)))


def get_meta(html, attr, name):
    m = re.search(r'<meta %s="%s" content="([^"]*)"' % (attr, re.escape(name)), html)
    return htmllib.unescape(m.group(1)) if m else ''


def ld_list(html):
    out = []
    for m in LD_RE.finditer(html):
        try:
            out.append(json.loads(m.group(2)))
        except Exception:
            out.append(None)
    return out


def ld_has_type(html, typ):
    return any(isinstance(d, dict) and d.get('@type') == typ for d in ld_list(html))


def prune_faq(html):
    """화면에 그 질문이 실제로 보이지 않는 FAQPage 구조화 데이터는 검색 정책에 어긋나므로 제거합니다."""
    text = visible_text(html)

    def fix(m):
        try:
            data = json.loads(m.group(2))
        except Exception:
            return m.group(0)
        if isinstance(data, dict) and data.get('@type') == 'FAQPage':
            qs = [re.sub(r'\s+', ' ', q.get('name', '')).strip() for q in data.get('mainEntity', [])]
            if not qs or any(q not in text for q in qs):
                return ''
        return m.group(0)

    new = LD_RE.sub(fix, html)
    return re.sub(r'\n{3,}', '\n\n', new)


def upsert_ld(html, data):
    block = '<script type="application/ld+json">\n' + json.dumps(data, ensure_ascii=False, indent=2) + '\n</script>'
    ids = {d.get('@id') for d in ld_list(html) if isinstance(d, dict)}
    if data['@id'] in ids:
        def fix(m):
            try:
                d = json.loads(m.group(2))
            except Exception:
                return m.group(0)
            return block if isinstance(d, dict) and d.get('@id') == data['@id'] else m.group(0)
        return LD_RE.sub(fix, html)
    return html.replace('</head>', block + '\n</head>', 1)


def breadcrumb_ld(url, items):
    return {
        '@context': 'https://schema.org', '@type': 'BreadcrumbList', '@id': SITE + url + '#breadcrumb',
        'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': n, 'item': SITE + u}
                            for i, (n, u) in enumerate(items)],
    }


def short_title(html):
    t = get_meta(html, 'property', 'og:title') or ''
    return re.sub(r'\s*\|\s*토르철거\s*$', '', t).strip()


def polish_taxonomy(html, url, tax):
    page = tax['pages'].get(url)
    article = tax['articles'].get(url)
    if not page and not article:
        return html
    desc = get_meta(html, 'name', 'description')
    has_other_bc = any(isinstance(d, dict) and d.get('@type') == 'BreadcrumbList' and not str(d.get('@id', '')).endswith('#breadcrumb')
                       for d in ld_list(html))
    if article:
        title = short_title(html)
        crumbs = [('토르철거', '/'), ('철거정보', '/blog'), (title, url)]
        image = get_meta(html, 'property', 'og:image')
        art = {
            '@context': 'https://schema.org', '@type': 'Article', '@id': SITE + url + '#article',
            'headline': title, 'description': desc, 'image': image,
            'datePublished': article['published'], 'dateModified': tax['site'].get('modified', article['published']),
            'inLanguage': 'ko', 'mainEntityOfPage': SITE + url, 'articleSection': article['section'],
            'author': {'@type': 'Organization', 'name': '토르철거', 'url': SITE},
            'publisher': {'@type': 'Organization', 'name': '토르철거', 'url': SITE,
                          'logo': {'@type': 'ImageObject', 'url': LOGO_URL}},
        }
        if not has_other_bc:
            html = upsert_ld(html, breadcrumb_ld(url, crumbs))
        if not ld_has_type(html, 'Article') or SITE + url + '#article' in {d.get('@id') for d in ld_list(html) if isinstance(d, dict)}:
            html = upsert_ld(html, art)
        return html
    if page['type'] == 'home':
        return html
    crumbs = [('토르철거', '/')] + [(n, u) for n, u in page.get('crumbs', [])] + [(page['name'], url)]
    if not has_other_bc:
        html = upsert_ld(html, breadcrumb_ld(url, crumbs))
    typ = page['type']
    own = SITE + url + '#page'
    ids = {d.get('@id') for d in ld_list(html) if isinstance(d, dict)}
    kind = {'service': 'Service', 'about': 'AboutPage', 'contact': 'ContactPage', 'collection': 'CollectionPage', 'webpage': 'WebPage'}[typ]
    if own in ids or not ld_has_type(html, kind):
        data = {'@context': 'https://schema.org', '@type': kind, '@id': own, 'name': page['name'], 'url': SITE + url,
                'description': desc, 'inLanguage': 'ko'}
        if typ == 'service':
            data['serviceType'] = page.get('serviceType', page['name'])
            data['areaServed'] = page.get('area', ['서울', '경기', '인천'])
            data['provider'] = {'@id': SITE + '/#business'}
        else:
            data['isPartOf'] = {'@id': SITE + '/#website'}
        data['breadcrumb'] = {'@id': SITE + url + '#breadcrumb'}
        html = upsert_ld(html, data)
    return html


def polish_social(html):
    title = get_meta(html, 'property', 'og:title')
    if not title:
        return html
    desc = get_meta(html, 'property', 'og:description')
    img = get_meta(html, 'property', 'og:image')
    add = []
    if 'property="og:locale"' not in html:
        add.append('<meta property="og:locale" content="ko_KR">')
    if img and 'property="og:image:alt"' not in html:
        add.append('<meta property="og:image:alt" content="%s">' % htmllib.escape(title, quote=True))
    if 'name="twitter:card"' not in html:
        add.append('<meta name="twitter:card" content="summary_large_image">')
        add.append('<meta name="twitter:title" content="%s">' % htmllib.escape(title, quote=True))
        if desc:
            add.append('<meta name="twitter:description" content="%s">' % htmllib.escape(desc, quote=True))
        if img:
            add.append('<meta name="twitter:image" content="%s">' % htmllib.escape(img, quote=True))
    if not add:
        return html
    ms = list(re.finditer(r'<meta property="og:[^>]*>', html))
    pos = ms[-1].end() if ms else html.find('</head>')
    return html[:pos] + '\n' + '\n'.join(add) + html[pos:]


_dim_cache = {}


def image_size(name):
    if name in _dim_cache:
        return _dim_cache[name]
    size = None
    try:
        from PIL import Image
        with Image.open(ROOT / 'images' / name) as im:
            size = im.size
    except Exception:
        pass
    _dim_cache[name] = size
    return size


def polish_dims(html):
    """이미지에 width/height 속성을 넣어 화면이 밀리는 현상(CLS)을 줄입니다.
    sizes 끝이 고정 폭(예: "..., 560px")이면 그 폭 기준으로 넣어 원래 표시 크기를 유지합니다."""
    body_start = html.find('<body')

    def fixed_width(tag):
        m = re.search(r'\bsizes="[^"]*,\s*(\d+)px"', tag)
        return int(m.group(1)) if m else None

    def fix(m):
        if m.start() < body_start:
            return m.group(0)
        tag = m.group(0)
        sm = re.search(r'\bsrc="/images/([^"/]+)"', tag)
        if not sm:
            return tag
        size = image_size(sm.group(1))
        if not size:
            return tag
        w, h = size
        fw = fixed_width(tag)
        if fw and fw < w:
            w, h = fw, round(h * fw / w)
        wm, hm = re.search(r'\bwidth="(\d+)"', tag), re.search(r'\bheight="(\d+)"', tag)
        if wm and hm:
            # 원래 작성자가 넣은 값은 그대로 두고, 이 도구가 넣은 원본 크기만 sizes 기준으로 바로잡습니다.
            if (int(wm.group(1)), int(hm.group(1))) == tuple(size) and (w, h) != tuple(size):
                tag = re.sub(r'\s(width|height)="[^"]*"', '', tag)
            else:
                return tag
        elif wm or hm:
            tag = re.sub(r'\s(width|height)="[^"]*"', '', tag)
        add = ' width="%d" height="%d"' % (w, h)
        return (tag[:-2].rstrip() + add + ' />') if tag.endswith('/>') else (tag[:-1].rstrip() + add + '>')

    return IMG_RE.sub(fix, html)


def run():
    changed = []
    tax = load_tax()
    for p in html_files():
        src = p.read_text(encoding='utf-8')
        new = polish_images(src)
        new = polish_dims(new)
        new = polish_ld(new, p == ROOT / 'index.html')
        new = prune_faq(new)
        new = polish_taxonomy(new, url_of(p), tax)
        new = polish_social(new)
        new = polish_meta(new)
        if new != src:
            p.write_text(new, encoding='utf-8')
            changed.append(str(p.relative_to(ROOT)))
    print(f'마무리 작업: {len(changed)}개 페이지 갱신')
    try:
        import lastmod
        lastmod.main()
    except Exception as e:  # sitemap 날짜 갱신 실패는 빌드를 막지 않음
        print('lastmod 건너뜀:', e)
    return changed


if __name__ == '__main__':
    run()
    sys.exit(0)
