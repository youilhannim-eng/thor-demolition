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
        html = html.replace('<meta name="viewport"', '<meta name="theme-color" content="#F01C24">\n<meta name="viewport"', 1)
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


BG_RE = re.compile(r'(<[a-z]+ class="([^"]*)" style=")background-image:url\((/images/([^/)]+)\.(?:jpg|jpeg|png))\)(")')


def polish_bg(html):
    """CSS 배경 이미지(히어로·카드)에 WebP image-set 추가. 원본 jpg는 대체용으로 유지."""
    def fix(m):
        cls, url, stem = m.group(2), m.group(3), m.group(4)
        src = ROOT / url.lstrip('/')
        if not src.exists():
            return m.group(0)
        want = 640 if 'bcard' in cls else 1200
        widths = [w for w in WIDTHS if (OPT / f'{stem}-{w}.webp').exists() and (OPT / f'{stem}-{w}.webp').stat().st_size >= 200] or make_variants(src)
        if not widths:
            return m.group(0)
        w = want if want in widths else max(widths)
        webp = f'/images/opt/{stem}-{w}.webp'
        return (f'{m.group(1)}background-image:url({url});'
                f'background-image:image-set(url({webp}) type(&quot;image/webp&quot;),url({url}) type(&quot;image/jpeg&quot;)){m.group(5)}')
    return BG_RE.sub(fix, html)


def polish_assets(html):
    """/assets/site.css·site.js 에 내용 해시 버전(?v=)을 붙여, 수정 즉시 방문자 브라우저에 반영되게 합니다."""
    import hashlib
    for name in ('site.css', 'site.js'):
        f = ROOT / 'assets' / name
        if not f.exists():
            continue
        v = hashlib.md5(f.read_bytes()).hexdigest()[:8]
        html = re.sub(r'/assets/' + re.escape(name) + r'(\?v=[0-9a-f]+)?(?=")', f'/assets/{name}?v={v}', html)
    return html


# 페이지별로 연결할 인사이트 카테고리(앞쪽이 우선)
RELATED = {
    'service': ['철거 실무', '비용·견적', '폐업지원금·정책'],
    'seoul-demolition': ['철거 실무', '비용·견적'], 'gyeonggi-demolition': ['철거 실무', '비용·견적'],
    'gangnam': ['철거 실무', '비용·견적'], 'incheon': ['철거 실무', '비용·견적'],
    'interior-demolition': ['철거 실무', '인테리어', '비용·견적'], 'restoration': ['철거 실무', '폐업지원금·정책', '비용·견적'],
    'support': ['폐업지원금·정책', '비용·견적'],
    'interior-construction': ['인테리어', '비용·견적'],
    'building-construction': ['건축·리모델링', '철거 실무'], 'remodeling': ['건축·리모델링', '철거 실무'],
    'waste-transport': ['철거 실무', '비용·견적'],
    'fire-restoration': ['화재복구', '철거 실무'], 'memorial-cleanup': ['유품정리'],
}


def _posts():
    import json
    out = []
    for f in sorted((ROOT / 'content' / 'insight').glob('*.json')):
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
            out.append(d)
        except Exception:
            pass
    out.sort(key=lambda d: d.get('date', ''), reverse=True)
    return out


def polish_related(html, url):
    slug = url.strip('/').rsplit('/', 1)[-1]
    cats = RELATED.get(slug)
    if not cats:
        return html
    posts = _posts()
    pick = [d for c in cats for d in posts if d.get('category') == c]
    seen, uniq = set(), []
    pool = pick if len({d['slug'] for d in pick}) >= 2 else pick + posts
    for d in pool:
        if d['slug'] not in seen:
            seen.add(d['slug']); uniq.append(d)
        if len(uniq) == 3:
            break
    if not uniq:
        return html
    import html as _h
    items = ''.join(f'<li><a href="/insight/{d["slug"]}"><em>{_h.escape(d.get("category", ""))}</em>'
                    f'<b>{_h.escape(d["title"])}</b></a></li>' for d in uniq)
    block = f'<div class="rel"><h2>함께 보면 좋은 글</h2><ul>{items}</ul><a class="rel-more" href="/insight">인사이트 전체 보기</a></div>'
    if '<!--related:start-->' in html:
        return re.sub(r'<!--related:start-->.*?<!--related:end-->', lambda m: f'<!--related:start-->{block}<!--related:end-->', html, count=1, flags=re.S)
    # 직접 만든 페이지: FAQ 섹션 바로 앞에 별도 섹션으로 넣기
    m = re.search(r'<h2[^>]*>자주 묻는 질문</h2>', html)
    if not m:
        return html
    sec = html.rfind('<section', 0, m.start())
    if sec < 0 or m.start() - sec > 400:
        return html
    return html[:sec] + f'<!--related:start--><section class="relsec"><div class="relw">{block}</div></section><!--related:end-->' + html[sec:]


GAL_ITEM_RE = re.compile(r'<div(?: data-c="[^"]*")?><img [^>]*src="(/images/[^"]+)"[^>]*></div>|<figure><img [^>]*src="(/images/[^"]+)"[^>]*>(?:<figcaption>.*?</figcaption>)?</figure>', re.S)


def polish_dedupe(html):
    """한 페이지에서 같은 사진(파일명만 다른 사본 포함)이 갤러리에 두 번 나오면 뒤에 나온 것을 뺍니다."""
    try:
        import dupcheck
    except Exception:
        return html
    seen = []
    # 갤러리 밖(히어로·전후비교 등)에서 먼저 쓴 사진도 기준에 넣기
    for m in re.finditer(r'(?:src="|style="background-image:url\()(/images/[^")]+)', html):
        pass
    out, pos = [], 0
    first_gal = GAL_ITEM_RE.search(html)
    head = html[:first_gal.start()] if first_gal else html
    bgs = re.findall(r'style="background-image:url\((/images/[^)]+)\)', html)
    for s in re.findall(r'(?:src="|style="background-image:url\()(/images/[^")]+)', head) + bgs:
        if 'logo' in s:
            continue
        h = dupcheck.dhash(ROOT / s.lstrip('/'))
        if h is not None:
            seen.append(h)

    def fix(m):
        s = m.group(1) or m.group(2)
        h = dupcheck.dhash(ROOT / s.lstrip('/'))
        if h is None:
            return m.group(0)
        if any(bin(h ^ x).count('1') <= 40 for x in seen):
            return ''
        seen.append(h)
        return m.group(0)
    return GAL_ITEM_RE.sub(fix, html)


# 직접 만든 키워드 랜딩(철거·인테리어철거·원상복구·폐업지원금·강남·인천)도 단독 홈페이지처럼
MINI = {'service': '토르철거', 'interior-demolition': '토르철거', 'restoration': '토르철거',
        'support': '토르철거', 'gangnam': '토르철거', 'incheon': '토르철거'}
MINI_RULES = [('svc', '서비스', None), ('area', '출동 지역', ('출동 범위',)), ('photos', '현장 사진', ('현장 사진',)),
              ('process', '진행 순서', ('진행 절차', '진행 순서', '신청부터')), ('cost', '비용 안내', ('비용',)),
              ('faq', '자주 묻는 질문', ('자주 묻는 질문',)), ('quote', '견적 문의', None)]


def polish_mini(html, url):
    slug = url.strip('/')
    brand = MINI.get(slug)
    if not brand or '<header' not in html:
        return html
    head_end = html.find('</header>')
    foot = html.find('<footer')
    if head_end < 0 or foot < 0:
        return html
    body = html[head_end:foot]
    h2s = list(re.finditer(r'<h2([^>]*)>(.*?)</h2>', body, re.S))
    h2s = [m for m in h2s if '함께 보면 좋은 글' not in m.group(2)]
    if not h2s:
        return html
    assign = {}
    for sid, label, keys in MINI_RULES:
        if keys is None:
            continue
        for m in h2s:
            txt = re.sub('<[^>]+>', '', m.group(2))
            if any(k in txt for k in keys) and m.start() not in assign.values():
                assign[sid] = m.start(); break
    if h2s[0].start() not in assign.values():
        assign.setdefault('svc', h2s[0].start())
    assign['quote'] = h2s[-1].start()
    # id 붙이기(뒤에서부터)
    for sid, pos in sorted(assign.items(), key=lambda x: -x[1]):
        m = re.match(r'<h2([^>]*)>', body[pos:])
        attrs = re.sub(r'\sid="[^"]*"', '', m.group(1))
        body = body[:pos] + f'<h2 id="{sid}"{attrs}>' + body[pos + m.end():]
    html = html[:head_end] + body + html[foot:]
    order = [r for r in MINI_RULES if r[0] in assign]
    order.sort(key=lambda r: assign[r[0]])
    links = ''.join(f'<a href="#{sid}">{label}</a>' for sid, label, _ in order)
    # 헤더
    html = re.sub(r'<header class="thd[^"]*" id="thd">', '<header class="thd thd-hassub" id="thd">', html, count=1)
    html = re.sub(r'<a class="thd-logo" href="[^"]*"><img ([^>]*?)alt="[^"]*"([^>]*)><span>[^<]*</span>',
                  lambda x: f'<a class="thd-logo" href="/{slug}"><img {x.group(1)}alt="{brand}"{x.group(2)}><span>{brand}</span>', html, count=1)
    html = re.sub(r'<nav class="thd-nav[^"]*"[^>]*>.*?</nav>', f'<nav class="thd-nav thd-spy" aria-label="{brand} 메뉴">{links}</nav>', html, count=1, flags=re.S)
    html = re.sub(r'<div class="thd-sub[^"]*"[^>]*>.*?</div>', '', html, count=1, flags=re.S)
    html = html.replace('<div class="thd-drawer"', f'<div class="thd-sub thd-spy" role="navigation" aria-label="{brand} 바로가기">{links}</div><div class="thd-drawer"', 1)
    html = re.sub(r'<nav class="thd-panel"[^>]*>.*?</nav>',
                  f'<nav class="thd-panel" aria-label="모바일 메뉴">{links}<a href="tel:01022256775">대표번호1 010-2225-6775</a><a href="tel:01086946775">대표번호2 010-8694-6775</a></nav>', html, count=1, flags=re.S)
    # 하단
    html = re.sub(r'<h4>[^<]*</h4>(\s*)<ul class="fnav">.*?</ul>',
                  lambda x: f'<h4>{brand}</h4>{x.group(1)}<ul class="fnav">' + ''.join(f'<li><a href="#{sid}">{label}</a></li>' for sid, label, _ in order) + '</ul>', html, count=1, flags=re.S)
    if 'class="fall"' not in html:
        html = re.sub(r'(<div class="fbot">\s*<em>[^<]*</em>)', r'\1<em><a href="/" class="fall">토르 전체 서비스 보기 →</a></em>', html, count=1)
    return html


# 키워드 랜딩에서도 다른 서비스로 갈 수 있게: 상단 '전체 서비스' 버튼 + 메뉴 안 목록 + 하단 서비스 바로가기
ALL_SVC = [('/service', '철거', '상가·사무실·주거 철거'), ('/restoration', '상가 원상복구', '임대 종료·폐업 원상복구'),
           ('/interior-construction', '인테리어', '상가·사무실 인테리어 시공'), ('/building-construction', '건축·구조', '구조 변경·보수 공사'),
           ('/remodeling', '대수선·리모델링', '건물 내부 개조'), ('/waste-transport', '폐기물', '철거·사업장 폐기물 처리'),
           ('/fire-restoration', '화재복구', '화재 잔해 철거·복구'), ('/memorial-cleanup', '유품정리', '분류·정리·폐기물 처리'),
           ('/support', '폐업지원금', '철거비 지원 제도 안내'), ('/portfolio', '시공사례', '현장 사진 모음')]


def polish_svcnav(html, url):
    if 'thd-spy' not in html:
        return html
    cur = '/' + url.strip('/')
    # 1) 상단 바 맨 앞 '전체 서비스' 버튼
    if 'data-allsvc' not in html:
        html = re.sub(r'(<div class="thd-sub thd-spy"[^>]*>)', r'\1<button type="button" class="thd-all" data-allsvc aria-haspopup="true">전체 서비스 ▾</button>', html, count=1)
    # 2) 메뉴(햄버거) 안 서비스 목록
    items = ''.join(f'<a href="{u}"{" class=on aria-current=page" if u == cur else ""}>{n}</a>' for u, n, _ in ALL_SVC)
    block = f'<!--svcnav:start--><b class="thd-ph">이 페이지</b><!--svcnav:end-->'
    html = re.sub(r'<!--svcnav:start-->.*?<!--svcnav:end-->', '', html, flags=re.S)
    html = re.sub(r'<!--svclist:start-->.*?<!--svclist:end-->', '', html, flags=re.S)
    html = re.sub(r'(<nav class="thd-panel"[^>]*>)', r'\1' + block, html, count=1)
    html = re.sub(r'(<nav class="thd-panel"[^>]*>.*?)(</nav>)',
                  lambda m: m.group(1) + f'<!--svclist:start--><b class="thd-ph">토르 전체 서비스</b>{items}<a href="/">토르 홈</a><!--svclist:end-->' + m.group(2),
                  html, count=1, flags=re.S)
    # 3) 하단 서비스 바로가기
    cards = ''.join(f'<a class="allsvc-c{" on" if u == cur else ""}" href="{u}"><b>{n}</b><span>{d}</span></a>' for u, n, d in ALL_SVC)
    sec = f'<!--allsvc:start--><section class="allsvc"><div class="allsvc-w"><h2>토르 다른 서비스</h2><div class="allsvc-g">{cards}</div></div></section><!--allsvc:end-->'
    html = re.sub(r'<!--allsvc:start-->.*?<!--allsvc:end-->', '', html, flags=re.S)
    i = html.find('<footer')
    if i > 0:
        html = html[:i] + sec + html[i:]
    return html


def polish_fbar(html):
    """모바일 하단 고정 바: 대표번호1·대표번호2·문자·견적 4칸으로 통일(두 번호 모두 바로 전화)."""
    quote = '#quote' if 'id="quote"' in html and 'id="tform"' in html else '/contact'
    ul = ('<ul class="fbar4">'
          '<li><a href="tel:01022256775"><small>대표번호1</small>전화</a></li>'
          '<li><a href="tel:01086946775"><small>대표번호2</small>전화</a></li>'
          '<li><a href="sms:01022256775"><small>사진 보내기</small>문자</a></li>'
          f'<li class="fq"><a href="{quote}"><small>무료</small>견적</a></li></ul>')
    return re.sub(r'(<div class="fbar">\s*)<ul[^>]*>.*?</ul>', lambda m: m.group(1) + ul, html, count=1, flags=re.S)


def polish_dlinks(html, url):
    """손으로 만든 강남·인천 페이지에 같은 권역 지역 페이지 링크를 붙인다(재실행 안전)."""
    cfg = {'/gangnam': ('thorGN-area', [('서울', '서울 다른 구 철거 안내')]),
           '/incheon': ('thorIC-area', [('인천', '인천 구별 철거 안내'), ('경기', '인근 경기 지역 철거 안내')])}
    if url not in cfg:
        return html
    cls, groups = cfg[url]
    html = re.sub(r'<!--dl:start-->.*?<!--dl:end-->', '', html, flags=re.S)
    qs = [json.loads(f.read_text(encoding='utf-8')) for f in sorted((ROOT / 'content' / 'services').glob('*.json'))]
    block = ''
    for prov, title in groups:
        out = sorted((q.get('order', 99), q['slug'], q['name']) for q in qs if q.get('district') and q.get('province', '서울') == prov)
        if out:
            links = ''.join(f'<a href="/{sl}">{nm}</a>' for _, sl, nm in out)
            block += f'<h3 style="margin:26px 0 10px;font-size:17px">{title}</h3><div class="dlinks">{links}</div>'
    if not block:
        return html
    block = f'<!--dl:start-->{block}<!--dl:end-->'
    m = re.search(r'<div class="' + cls + r'">.*?</div>\s*</div>', html, re.S)
    if not m:
        return html
    return html[:m.end()] + block + html[m.end():]


def polish_pagephotos(html, url):
    """직접 만든 키워드 랜딩(강남·인천·인테리어철거·원상복구·폐업지원금)에 실제 현장 사진 갤러리 삽입(content/page_photos.json)."""
    import json, html as _h
    f = ROOT / 'content' / 'page_photos.json'
    if not f.exists():
        return html
    conf = json.loads(f.read_text(encoding='utf-8')).get(url.strip('/'))
    if not conf:
        return html
    figs = ''.join(f'<figure><img src="{x["src"]}" alt="{_h.escape(x["alt"])}" loading="lazy" decoding="async" width="480" height="640"><figcaption>{_h.escape(x["alt"])}</figcaption></figure>' for x in conf['items'])
    block = (f'<!--pphotos:start--><section class="pphotos"><div class="relw"><h2>{_h.escape(conf["h2"])}</h2>'
             f'<p class="pphotos-note">{_h.escape(conf["note"])}</p><div class="sgal">{figs}</div></div></section><!--pphotos:end-->')
    if '<!--pphotos:start-->' in html:
        return re.sub(r'<!--pphotos:start-->.*?<!--pphotos:end-->', lambda m: block, html, count=1, flags=re.S)
    i = html.find('<!--related:start-->')
    if i < 0:
        m = re.search(r'<h2[^>]*>자주 묻는 질문</h2>', html)
        if not m:
            return html
        i = html.rfind('<section', 0, m.start())
    return html[:i] + block + html[i:]


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
        new = polish_bg(new)
        new = polish_related(new, url_of(p))
        new = polish_pagephotos(new, url_of(p))
        new = polish_dlinks(new, url_of(p))
        new = polish_dedupe(new)
        new = polish_mini(new, url_of(p))
        new = polish_svcnav(new, url_of(p))
        new = polish_fbar(new)
        new = polish_assets(new)
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
