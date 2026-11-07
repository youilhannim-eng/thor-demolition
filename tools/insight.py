#!/usr/bin/env python3
"""토르철거 인사이트 빌더.

content/insight/*.json (글 1개 = 파일 1개)을 읽어서 아래를 만든다.
  - insight.html                 목록 페이지  (https://thorthor.co.kr/insight)
  - insight/<slug>.html          글 페이지    (https://thorthor.co.kr/insight/<slug>)
  - insight-rss.xml              인사이트 RSS
  - sitemap.xml                  /insight, /insight/<slug> 항목을 갱신 (기존 항목은 그대로)
  - llms.txt                     인사이트 목록 구간 갱신 (마커 안쪽만)
  - 모든 기존 페이지의 상단 메뉴·푸터에 '인사이트' 링크 추가 (이미 있으면 그대로)

사용법:  python3 tools/insight.py          # 검증 + 빌드
         python3 tools/insight.py --check  # 검증만
"""
import html
import json
import pathlib
import re
import sys
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / 'content' / 'insight'
TPL = ROOT / 'tools' / 'templates'
SITE = 'https://thorthor.co.kr'
KST = timezone(timedelta(hours=9))

# 장르(카테고리) → (주소 이름, 연결할 서비스 페이지, 서비스 이름, 모음 페이지 소개문, 사진 장르)
# 장르마다 /insight/topic-<주소 이름> 모음 페이지가 생긴다. 글이 3편 이상 쌓이면 검색에 노출(그 전에는 noindex).
HUBS = {
    '철거 실무': ('demolition', '/service', '철거 서비스',
                 '상가·사무실·주택 철거 현장에서 실제로 부딪히는 준비 사항과 작업 순서, 소음·분진·폐기물 문제를 정리합니다.', '철거'),
    '비용·견적': ('estimate', '/service', '철거 서비스',
                 '견적서를 읽는 법, 비용이 달라지는 이유, 추가 비용이 생기는 경우와 견적 비교 기준을 정리합니다.', '철거'),
    '폐업지원금·정책': ('support', '/support', '폐업지원금 철거 안내',
                    '폐업 소상공인을 위한 지원 제도와 철거비 관련 안내를 공식 자료 기준으로 정리합니다.', '철거'),
    '인테리어': ('interior', '/interior-construction', '인테리어 시공',
               '철거 이후 인테리어 공정 순서와 마감 선택, 공사 범위를 정하는 기준을 정리합니다.', '인테리어'),
    '건축·리모델링': ('building', '/building-construction', '건축·구조 공사',
                  '대수선·리모델링과 구조 공사에서 확인할 사항, 오래된 건물을 다룰 때의 주의점을 정리합니다.', '건축'),
    '화재복구': ('fire', '/fire-restoration', '화재복구',
               '화재 이후 철거와 폐기물 분류, 복구 순서, 보험 청구에 필요한 기록 방법을 정리합니다.', '화재복구'),
    '유품정리': ('cleanup', '/memorial-cleanup', '유품정리',
               '유품정리·고인의 주거 공간 정리 절차와 폐기물 분류, 유가족이 미리 알아 둘 점을 정리합니다.', '유품정리'),
}
CATEGORIES = list(HUBS)
HUB_MIN_POSTS = 3

# 사이트에 이미 있는 실제 현장 사진만 쓴다. (경로 → 대체텍스트)
IMAGES = {
    '/images/03b023449983b.jpg': '상가 원상복구 완료 후 콘크리트 골조가 드러난 내부',
    '/images/0af4730ede62a.jpg': '철거 전 파티션과 카펫이 남아 있는 사무실 내부',
    '/images/0d3e6bfb4928c.jpg': '내부 철거 후 콘크리트가 드러난 아파트 거실',
    '/images/2a96bcedd8fcc.jpg': '인테리어 철거 작업자가 주방 가구를 해체하는 모습',
    '/images/2bd7589e770cd.jpg': '목재 마감과 카운터가 남아 있는 원상복구 전 상가 내부',
    '/images/4e32e76cc44b8.jpg': '보양 작업을 마친 주방에서 철거 자재를 정리하는 작업자 두 명',
    '/images/52b164e6196f8.jpg': '건물 내부 구조물 해체가 진행 중인 층 전경',
    '/images/57c52588a0b08.jpg': '철거 전 벽지와 마루가 남아 있는 아파트 거실',
    '/images/669a52117056f.jpg': '상가 외부에서 굴착기로 철거 작업을 진행하는 현장',
    '/images/7d84c87416680.jpg': '보호구를 착용한 작업자 두 명이 석고보드 벽체를 해체하는 철거 현장',
    '/images/8a649338e8303.jpg': '폐업 정리 중인 주방 철거 현장과 마대에 담긴 철거 폐기물',
    '/images/b1013ad073907.jpg': '철거 후 폐기물이 정리된 현장',
    '/images/c7a41366da88d.jpg': '원상복구 후 콘크리트 골조만 남은 사무실 내부',
    '/images/e7897a67ffc8f.jpg': '철거 전 목재 인테리어와 카운터가 있는 상가 내부',
    '/images/ecb1caf3ef233.jpg': '상가 내부 철거 작업 현장과 미니굴착기',
    '/images/fca750281234d.jpg': '건물 한 개 층 내부 철거 현장과 안전망으로 구획한 폐기물 적재 구역',
}

try:                                           # tools/photos.py 로 올린 사진 중 장르·설명이 채워진 것도 쓸 수 있다
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import photos as _photos
    IMAGES.update(_photos.photo_alts())
except Exception:
    pass

# 글에 쓸 수 있는 HTML 태그
ALLOWED_TAGS = {'p', 'h2', 'h3', 'ul', 'ol', 'li', 'strong', 'em', 'a', 'br', 'table', 'thead', 'tbody', 'tr', 'th', 'td'}
# 사이트 안 링크로 허용하는 주소
INTERNAL_OK = re.compile(r'^/(service|support|portfolio|about|contact|blog|gangnam|incheon|interior-demolition|restoration|insight|interior-construction|waste-transport|memorial-cleanup|fire-restoration|building-construction|remodeling|seoul-demolition|gyeonggi-demolition)(/[a-z0-9-]+)?$')

# 이 표현이 들어가면 빌드를 막는다 (토르철거 마케팅 원칙: 과장·가격 후려치기·보장 표현 금지)
BANNED = ['최저가 보장', '최저가를 보장', '토르철거는 최저가', '토르철거가 최저가', '최저가 업체', '업계 1위', '업계1위', '무조건', '100% 보장', '100%보장', '타사 견적', '타 업체 견적', '가장 저렴',
          '국내 최고', '만족도 9', '고객 후기', '후기에 따르면']
# 회사에 대해 확인되지 않은 사실을 지어내지 못하게 막는 표현
BANNED_COMPANY_CLAIMS = ['토르철거는 면허', '토르철거는 보험', '토르철거 보유 면허', '배상책임보험에 가입', '인증을 받', '수상', '누적 시공', '시공 건수']
# 2026-11-07 검토 반영: 글끼리 같은 문구가 반복되면 '대량 생산 콘텐츠'로 보일 수 있어 빌드에서 막는다
# 표현: 한 글에 허용하는 최대 횟수
PHRASE_LIMITS = {'결론부터 말씀드리면': 0, '결론부터 말하면': 0, '사진, 주소, 평수, 층수': 0, '사진·주소·평수·층수': 0,
                 '확인하시기 바랍니다': 1, '알아보겠습니다': 0, '살펴보겠습니다': 0, '결론적으로': 0, '종합하면': 0,
                 '이 글에서는': 1, '도움이 되셨길': 0}
BAD_H2 = re.compile(r'^(\d+[.)]\s|개요$|결론$|정리$|마치며$|마무리$|요약$)')
STRICT_FROM = '2026-11-08'   # 이 날짜 이후 글은 글 사이 반복 검사를 오류로 처리(그 전 글은 경고)
SLUG_RE = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')


def esc(s):
    return html.escape(str(s), quote=True)


def load_posts():
    posts = []
    for f in sorted(CONTENT.glob('*.json')):
        p = json.loads(f.read_text(encoding='utf-8'))
        p['_file'] = f.name
        posts.append(p)
    posts.sort(key=lambda p: (p['date'], p['slug']), reverse=True)
    return posts


def strip_tags(s):
    return re.sub(r'<[^>]+>', '', s)


def validate(posts):
    errors = []
    slugs, titles = set(), set()
    today = datetime.now(KST).date().isoformat()
    for p in posts:
        w = p['_file']
        for k in ('slug', 'title', 'description', 'date', 'category', 'image', 'summary', 'body'):
            if not p.get(k):
                errors.append(f'{w}: "{k}" 가 비어 있습니다')
        if errors and any(e.startswith(w) for e in errors):
            continue
        if p['slug'].startswith('topic-'):
            errors.append(f'{w}: slug 는 topic- 으로 시작할 수 없음(장르 모음 페이지 주소)')
        if not SLUG_RE.match(p['slug']):
            errors.append(f'{w}: slug 는 영문 소문자·숫자·하이픈만 가능합니다')
        if not w.endswith(p['slug'] + '.json') or not re.match(r'^\d{4}-\d{2}-\d{2}-', w):
            errors.append(f'{w}: 파일 이름은 YYYY-MM-DD-<slug>.json 이어야 합니다')
        if p['slug'] in slugs:
            errors.append(f'{w}: slug 중복')
        slugs.add(p['slug'])
        if p['title'] in titles:
            errors.append(f'{w}: 제목 중복')
        titles.add(p['title'])
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', p['date']):
            errors.append(f'{w}: date 형식 오류')
        elif p['date'] > today:
            errors.append(f'{w}: date 가 미래입니다')
        if not 15 <= len(p['title']) <= 60:
            errors.append(f'{w}: 제목은 15~60자 ({len(p["title"])}자)')
        if not 70 <= len(p['description']) <= 160:
            errors.append(f'{w}: description 은 70~160자 ({len(p["description"])}자)')
        if p['category'] not in CATEGORIES:
            errors.append(f'{w}: category 는 {CATEGORIES} 중 하나')
        if p['image'] not in IMAGES:
            errors.append(f'{w}: image 는 IMAGES 목록에 있는 사진만 가능합니다')
        if not (isinstance(p['summary'], list) and len(p['summary']) == 3 and all(isinstance(x, str) and x for x in p['summary'])):
            errors.append(f'{w}: summary 는 3줄(문자열 3개) 이어야 합니다')
        body = p['body']
        text_all = strip_tags(body) + ' ' + p['title'] + ' ' + p['description'] + ' ' + ' '.join(p.get('summary', []))
        for f in p.get('faq', []):
            text_all += ' ' + f.get('q', '') + ' ' + f.get('a', '')
        chars = len(re.sub(r'\s+', '', strip_tags(body)))
        min_chars = 2000     # 2026-11-07부터 옛 글 포함 전부 2000자 이상
        if chars < min_chars:
            errors.append(f'{w}: 본문이 너무 짧습니다 ({chars}자, 최소 {min_chars}자)')
        for tag in re.findall(r'</?([a-zA-Z0-9]+)', body):
            if tag.lower() not in ALLOWED_TAGS:
                errors.append(f'{w}: 허용되지 않은 태그 <{tag}>')
                break
        if re.search(r'<[^>]+\s(style|on[a-z]+)\s*=', body, re.I) or re.search(r'<script|<iframe|<img', body, re.I):
            errors.append(f'{w}: style/이벤트/script/iframe/img 는 쓸 수 없습니다')
        for href in re.findall(r'href="([^"]*)"', body):
            if not (INTERNAL_OK.match(href) or href.startswith('tel:010')):
                errors.append(f'{w}: 본문 링크는 사이트 내부 주소만 가능합니다: {href}')
        for b in BANNED + BANNED_COMPANY_CLAIMS:
            if b in text_all:
                errors.append(f'{w}: 금지 표현 "{b}"')
        if re.search(r'(평당|㎡당|제곱미터당|평\s*단가)[^.]{0,20}\d', text_all):
            errors.append(f'{w}: 평당·㎡당 단가 수치는 쓰지 않습니다')
        if p['category'] == '폐업지원금·정책':
            if not p.get('sources'):
                errors.append(f'{w}: 정책 글은 sources(공식 출처) 가 필요합니다')
            if '기준' not in body:
                errors.append(f'{w}: 정책 글 본문에 "○○년 ○월 기준" 표기가 필요합니다')
        for ph, mx in PHRASE_LIMITS.items():
            if text_all.count(ph) > mx:
                errors.append(f'{w}: 반복 문구 "{ph}" {text_all.count(ph)}회 (최대 {mx}회)')
        for h in re.findall(r'<h2>(.*?)</h2>', body):
            if BAD_H2.match(strip_tags(h).strip()):
                errors.append(f'{w}: 소제목은 질문·상황형으로 (번호형·"정리" 금지): {strip_tags(h)}')
        for s in p.get('sources', []):
            if not (s.get('title') and re.match(r'^https://', s.get('url', ''))):
                errors.append(f'{w}: sources 항목은 title, https url 이 필요합니다')
        for f in p.get('faq', []):
            if not (f.get('q') and f.get('a')):
                errors.append(f'{w}: faq 항목은 q, a 가 필요합니다')
        if len(p.get('faq', [])) not in (0, 3, 4, 5, 6):
            errors.append(f'{w}: faq 는 0개 또는 3~6개')
    errors += cross_post_check(posts)
    return errors


def _sentences(p):
    t = strip_tags(p['body'])
    return {re.sub(r'\s+', ' ', x).strip() for x in re.split(r'(?<=[.?!])\s+', t) if len(re.sub(r'\s+', '', x)) >= 25}


def _ngrams(p, n=6):
    words = re.sub(r'[^\w가-힣·]+', ' ', strip_tags(p['body'])).split()
    return {' '.join(words[i:i + n]) for i in range(len(words) - n + 1)}


def cross_post_check(posts):
    """글 사이에 같은 문장, 여러 글에 반복되는 6어절 문구를 찾는다.
    STRICT_FROM 이후 글은 오류로 막고, 그 전 글은 경고만 출력한다."""
    errors = []
    sents = {p['_file']: _sentences(p) for p in posts}
    grams = {p['_file']: _ngrams(p) for p in posts}
    count = {}
    for g in grams.values():
        for x in g:
            count[x] = count.get(x, 0) + 1
    for p in posts:
        w = p['_file']
        strict = p['date'] >= STRICT_FROM
        same = set()
        for o in posts:
            if o['_file'] != w:
                same |= sents[w] & sents[o['_file']]
        rep = sorted(x for x in grams[w] if count[x] >= 3)
        msgs = [f'다른 글과 같은 문장: "{x[:40]}"' for x in sorted(same)[:3]]
        msgs += [f'3편 이상에 반복되는 문구: "{x}"' for x in rep[:3]]
        for m in msgs:
            if strict:
                errors.append(f'{w}: {m}')
            else:
                print(f'경고 {w}: {m}')
    return errors


def hub_url(cat):
    return f'/insight/topic-{HUBS[cat][0]}'


def tags_html():
    return ''.join(f'<li><a href="{hub_url(c)}" style="color:inherit;text-decoration:none">{esc(c)}</a></li>' for c in CATEGORIES)


def article_html(p, nxt, prv):
    cta = ('<p>지원금 지급 여부는 심사 결과에 따라 달라지며 보장할 수 없습니다. 신청에 필요한 견적서와 시공 전후 사진 등 서류 준비는 시공과 함께 도와드립니다. 현장 사진이나 계약서를 '
           '보내 주시면 상황에 맞춰 안내해 드립니다. 무료 방문 견적은 <a href="/contact">견적 문의</a> 페이지 또는 '
           '<a href="tel:01022256775">010-2225-6775</a>, <a href="tel:01086946775">010-8694-6775</a>로 연락 주세요. '
           '비슷한 사례는 <a href="/portfolio">시공사례</a>에서 비포·애프터 사진으로 확인하실 수 있습니다.</p>')
    summ = ''.join(f'<li>{esc(x)}</li>' for x in p['summary'])
    faq = ''
    if p.get('faq'):
        items = ''.join(f'<div class="ins-q"><h3>{esc(f["q"])}</h3><p>{esc(f["a"])}</p></div>' for f in p['faq'])
        faq = f'<h2>자주 묻는 질문</h2>{items}'
    src = ''
    if p.get('sources'):
        li = ''.join(f'<li><a href="{esc(s["url"])}" target="_blank" rel="noopener nofollow">{esc(s["title"])}</a></li>' for s in p['sources'])
        src = f'<h2>참고한 자료</h2><ul class="ins-src">{li}</ul>'
    if p.get('updated_note'):
        src += f'<p class="ins-note">{esc(p["updated_note"])}</p>'
    nav = ''
    for label, q, cls in (('다음 글', nxt, 'up'), ('이전 글', prv, 'dn')):
        if q:
            nav += f'<a class="bpost-nav-i" href="/insight/{q["slug"]}"><span class="{cls}" aria-hidden="true"></span>{esc(q["title"])}</a>'
    nav_html = f'<nav class="bpost-nav" aria-label="다른 글">{nav}</nav>' if nav else ''
    alt = esc(IMAGES[p['image']])
    return (f'<article class="bpost"><header class="bpost-h"><h1 class="bpost-tit"><span class="bpost-cat">{esc(p["category"])}</span>{esc(p["title"])}</h1>'
            f'<p class="bpost-sum"><span>인사이트</span><time datetime="{p["date"]}">{p["date"]}</time></p></header>'
            f'<div class="bpost-body ins-body fr-view"><p><img alt="{alt}" class="fr-dii" src="{p["image"]}"/></p>'
            f'<div class="ins-box"><b>3줄 요약</b><ul>{summ}</ul></div>'
            f'{p["body"]}{faq}{cta}{src}</div>{nav_html}'
            f'<p class="bpost-btns"><a class="bpost-list" href="/insight">목록</a></p></article>')


def jsonld_html(p):
    url = f'{SITE}/insight/{p["slug"]}'
    img = SITE + p['image']
    graph = [
        {
            '@context': 'https://schema.org', '@type': 'Article', 'headline': p['title'], 'description': p['description'],
            'image': img, 'datePublished': p['date'], 'dateModified': p.get('modified', p['date']), 'inLanguage': 'ko',
            'mainEntityOfPage': url,
            'author': {'@type': 'Organization', 'name': '토르철거', 'url': SITE},
            'publisher': {'@type': 'Organization', 'name': '토르철거', 'url': SITE, 'logo': {'@type': 'ImageObject', 'url': SITE + '/images/864c5d29e51fe.jpg'}},
        },
        {
            '@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
                {'@type': 'ListItem', 'position': 1, 'name': '토르철거', 'item': SITE + '/'},
                {'@type': 'ListItem', 'position': 2, 'name': '인사이트', 'item': SITE + '/insight'},
                {'@type': 'ListItem', 'position': 3, 'name': p['title'], 'item': url},
            ]},
    ]
    if p.get('faq'):
        graph.append({'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
            {'@type': 'Question', 'name': f['q'], 'acceptedAnswer': {'@type': 'Answer', 'text': f['a']}} for f in p['faq']]})
    return '\n'.join('<script type="application/ld+json">\n' + json.dumps(g, ensure_ascii=False, indent=1).replace('</', '<\\/') + '\n</script>' for g in graph)


def build_post(p, nxt, prv):
    t = (TPL / 'post.html').read_text(encoding='utf-8')
    url = f'{SITE}/insight/{p["slug"]}'
    title_tag = f'{p["title"]} | 토르철거 인사이트'
    rep = {
        '{{TITLE_TAG}}': esc(title_tag), '{{DESC}}': esc(p['description']), '{{URL}}': url, '{{OG_IMAGE}}': SITE + p['image'],
        '{{DATE}}': p['date'], '{{TAGS}}': tags_html(), '{{JSONLD}}': jsonld_html(p), '{{ARTICLE}}': article_html(p, nxt, prv),
    }
    for k, v in rep.items():
        t = t.replace(k, v)
    assert '{{' not in t, 'unreplaced placeholder'
    (ROOT / 'insight').mkdir(exist_ok=True)
    (ROOT / 'insight' / f'{p["slug"]}.html').write_text(t, encoding='utf-8')


def cards_html(posts):
    return ''.join(
        f'<a class="bcard" href="/insight/{p["slug"]}"><div class="bcard-th" style="background-image:url({p["image"]})"></div>'
        f'<div class="bcard-t"><em>{esc(p["category"])}</em>{esc(p["title"])}</div>'
        f'<div class="bcard-x">{esc(p["description"])}</div><small class="bcard-d">{p["date"]}</small></a>' for p in posts)


def build_hubs(posts):
    """장르별 모음 페이지 /insight/topic-<이름>. 글이 HUB_MIN_POSTS 편 미만이면 noindex(얇은 페이지 방지)."""
    src = (TPL / 'list.html').read_text(encoding='utf-8')
    indexable = []
    for cat, (slug, svc, svc_name, intro, _g) in HUBS.items():
        mine = [p for p in posts if p['category'] == cat]
        url = f'{SITE}/insight/topic-{slug}'
        title = f'{cat} 인사이트 | 토르철거'
        desc = f'{intro} 토르철거 현장 경험을 바탕으로 한 {cat} 글 모음입니다.'
        t = src
        t = t.replace('<title>인사이트 | 철거 실무·견적·폐업지원금 정보 | 토르철거</title>', f'<title>{esc(title)}</title>')
        t = t.replace('<meta property="og:title" content="인사이트 | 철거 실무·견적·폐업지원금 정보 | 토르철거">', f'<meta property="og:title" content="{esc(title)}">')
        t = t.replace('content="철거·원상복구 실무, 견적이 정해지는 기준, 폐업지원금과 제도 변화까지. 토르철거가 매일 하나씩 정리하는 인사이트입니다."', f'content="{esc(desc)}"')
        t = t.replace('<link rel="canonical" href="https://thorthor.co.kr/insight">', f'<link rel="canonical" href="{url}">')
        t = t.replace('<meta property="og:url" content="https://thorthor.co.kr/insight">', f'<meta property="og:url" content="{url}">')
        if len(mine) < HUB_MIN_POSTS:
            t = re.sub(r'<meta name="robots" content="[^"]*">\s*', '', t)
            t = t.replace('<link rel="canonical"', '<meta name="robots" content="noindex,follow">\n<link rel="canonical"', 1)
        else:
            indexable.append(slug)
        t = t.replace('<h1 class="thorBI-h1">토르철거 <em>인사이트</em></h1>', f'<h1 class="thorBI-h1">{esc(cat)} <em>인사이트</em></h1>')
        t = re.sub(r'<p class="thorBI-lead">.*?</p>',
                   f'<p class="thorBI-lead">{esc(intro)} 관련 서비스: <a href="{svc}" style="color:#F01C24;font-weight:600">{esc(svc_name)}</a> · <a href="/insight" style="color:#555">전체 글 보기</a></p>', t, count=1, flags=re.S)
        t = t.replace('<h2>인사이트 <em>{{COUNT}}</em></h2>', f'<h2>{esc(cat)} <em>{{{{COUNT}}}}</em></h2>')
        ld = {'@context': 'https://schema.org', '@type': 'CollectionPage', 'name': title, 'url': url, 'inLanguage': 'ko',
              'hasPart': [{'@type': 'Article', 'headline': p['title'], 'url': f'{SITE}/insight/{p["slug"]}', 'datePublished': p['date']} for p in mine]}
        ld_html = '<script type="application/ld+json">\n' + json.dumps(ld, ensure_ascii=False, indent=1).replace('</', '<\\/') + '\n</script>'
        body = cards_html(mine) if mine else '<p style="grid-column:1/-1;color:#757575">이 분야의 첫 글을 준비하고 있습니다.</p>'
        for k, v in {'{{TAGS}}': tags_html(), '{{COUNT}}': str(len(mine)), '{{CARDS}}': body, '{{LIST_JSONLD}}': ld_html}.items():
            t = t.replace(k, v)
        assert '{{' not in t
        (ROOT / 'insight' / f'topic-{slug}.html').write_text(t, encoding='utf-8')
    return indexable


def build_list(posts):
    t = (TPL / 'list.html').read_text(encoding='utf-8')
    cards = cards_html(posts)
    ld = {'@context': 'https://schema.org', '@type': 'CollectionPage', 'name': '토르철거 인사이트', 'url': SITE + '/insight', 'inLanguage': 'ko',
          'hasPart': [{'@type': 'Article', 'headline': p['title'], 'url': f'{SITE}/insight/{p["slug"]}', 'datePublished': p['date']} for p in posts]}
    ld_html = '<script type="application/ld+json">\n' + json.dumps(ld, ensure_ascii=False, indent=1).replace('</', '<\\/') + '\n</script>'
    rep = {'{{TAGS}}': tags_html(), '{{COUNT}}': str(len(posts)), '{{CARDS}}': cards, '{{LIST_JSONLD}}': ld_html}
    for k, v in rep.items():
        t = t.replace(k, v)
    assert '{{' not in t
    (ROOT / 'insight.html').write_text(t, encoding='utf-8')


def rfc822(date):
    d = datetime.strptime(date, '%Y-%m-%d').replace(hour=9, tzinfo=KST)
    return d.strftime('%a, %d %b %Y %H:%M:%S +0900')


def build_rss(posts):
    items = ''.join(
        f'  <item>\n    <title>{esc(p["title"])}</title>\n    <link>{SITE}/insight/{p["slug"]}</link>\n'
        f'    <guid isPermaLink="true">{SITE}/insight/{p["slug"]}</guid>\n    <category>{esc(p["category"])}</category>\n'
        f'    <description>{esc(p["description"])}</description>\n    <pubDate>{rfc822(p["date"])}</pubDate>\n  </item>\n' for p in posts[:30])
    last = rfc822(posts[0]['date']) if posts else rfc822(datetime.now(KST).strftime('%Y-%m-%d'))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n<channel>\n'
           '  <title>인사이트 | 토르철거</title>\n  <link>' + SITE + '/insight</link>\n'
           '  <atom:link href="' + SITE + '/insight-rss.xml" rel="self" type="application/rss+xml"/>\n'
           '  <description>철거·원상복구 실무, 견적 기준, 폐업지원금과 제도 변화까지 토르철거가 매일 정리하는 인사이트</description>\n'
           '  <language>ko</language>\n  <lastBuildDate>' + last + '</lastBuildDate>\n' + items + '</channel>\n</rss>\n')
    (ROOT / 'insight-rss.xml').write_text(xml, encoding='utf-8')


def build_sitemap(posts, hubs=()):
    f = ROOT / 'sitemap.xml'
    t = f.read_text(encoding='utf-8')
    t = re.sub(r'\s*<url><loc>' + re.escape(SITE) + r'/insight[^<]*</loc>.*?</url>', '', t)
    today = posts[0]['date'] if posts else datetime.now(KST).strftime('%Y-%m-%d')
    new = f'\n  <url><loc>{SITE}/insight</loc><lastmod>{today}</lastmod></url>'
    for s in hubs:
        new += f'\n  <url><loc>{SITE}/insight/topic-{s}</loc><lastmod>{today}</lastmod></url>'
    for p in posts:
        new += f'\n  <url><loc>{SITE}/insight/{p["slug"]}</loc><lastmod>{p.get("modified", p["date"])}</lastmod></url>'
    t = t.replace('</urlset>', new + '\n</urlset>')
    f.write_text(t, encoding='utf-8')


def build_llms(posts):
    f = ROOT / 'llms.txt'
    t = f.read_text(encoding='utf-8')
    t = re.sub(r'\n*<!-- insight:start -->.*?<!-- insight:end -->\n*', '\n', t, flags=re.S).rstrip() + '\n'
    lines = ['', '<!-- insight:start -->', '# 토르철거 인사이트', '',
             '> 서울·인천·경기 철거·원상복구 전문업체 토르철거가 정리한 철거 실무, 견적 기준, 폐업지원금 정보입니다.', '']
    lines += [f'- [{p["title"]}]({SITE}/insight/{p["slug"]}): {p["description"]}' for p in posts]
    lines += ['<!-- insight:end -->', '']
    f.write_text(t + '\n'.join(lines), encoding='utf-8')


def ensure_nav():
    """기존 모든 페이지 메뉴·푸터에 '인사이트' 링크를 한 번만 넣는다."""
    changed = 0
    files = list(ROOT.glob('*.html')) + list((ROOT / 'blog').glob('*.html'))
    for f in files:
        if f.name == 'insight.html':
            continue
        t = f.read_text(encoding='utf-8')
        if 'href="/insight"' in t:
            continue
        n = t
        n = n.replace('<a href="/blog" class=on>철거정보</a>', '<a href="/blog" class=on>철거정보</a><a href="/insight">인사이트</a>')
        n = n.replace('<a href="/blog">철거정보</a>', '<a href="/blog">철거정보</a><a href="/insight">인사이트</a>')
        n = n.replace('<li><a href="/blog">철거 정보</a></li>', '<li><a href="/blog">철거 정보</a></li>\n<li><a href="/insight">인사이트</a></li>')
        if n != t:
            f.write_text(n, encoding='utf-8')
            changed += 1
    return changed


def main():
    posts = load_posts()
    errors = validate(posts)
    if errors:
        print('검증 실패:')
        for e in errors:
            print(' -', e)
        sys.exit(1)
    print(f'검증 통과: 글 {len(posts)}개')
    if '--check' in sys.argv:
        return
    for i, p in enumerate(posts):
        nxt = posts[i - 1] if i > 0 else None          # 더 최근 글
        prv = posts[i + 1] if i + 1 < len(posts) else None
        build_post(p, nxt, prv)
    # 지워진 글의 페이지 정리
    keep = {f'{p["slug"]}.html' for p in posts} | {f'topic-{h[0]}.html' for h in HUBS.values()}
    for f in (ROOT / 'insight').glob('*.html'):
        if f.name not in keep:
            f.unlink()
    hubs = build_hubs(posts)
    build_list(posts)
    build_rss(posts)
    build_sitemap(posts, hubs)
    build_llms(posts)
    print('메뉴 링크 추가한 페이지:', ensure_nav())
    import polish
    polish.run()
    print('빌드 완료')


if __name__ == '__main__':
    main()
