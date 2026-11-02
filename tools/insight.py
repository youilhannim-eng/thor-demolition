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

CATEGORIES = ['철거 실무', '비용·견적', '폐업지원금·정책', '인테리어·건축', '화재복구·유품정리']

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

# 글에 쓸 수 있는 HTML 태그
ALLOWED_TAGS = {'p', 'h2', 'h3', 'ul', 'ol', 'li', 'strong', 'em', 'a', 'br', 'table', 'thead', 'tbody', 'tr', 'th', 'td'}
# 사이트 안 링크로 허용하는 주소
INTERNAL_OK = re.compile(r'^/(service|support|portfolio|about|contact|blog|gangnam|incheon|interior-demolition|restoration|insight|interior-construction|waste-transport|memorial-cleanup|fire-restoration|building-construction)(/[a-z0-9-]+)?$')

# 이 표현이 들어가면 빌드를 막는다 (토르철거 마케팅 원칙: 과장·가격 후려치기·보장 표현 금지)
BANNED = ['최저가', '업계 1위', '업계1위', '무조건', '100% 보장', '100%보장', '타사 견적', '타 업체 견적', '가장 저렴',
          '국내 최고', '만족도 9', '고객 후기', '후기에 따르면']
# 회사에 대해 확인되지 않은 사실을 지어내지 못하게 막는 표현
BANNED_COMPANY_CLAIMS = ['토르철거는 면허', '토르철거는 보험', '토르철거 보유 면허', '배상책임보험에 가입', '인증을 받', '수상', '누적 시공', '시공 건수']
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
        if chars < 1800:
            errors.append(f'{w}: 본문이 너무 짧습니다 ({chars}자, 최소 1800자)')
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
        for s in p.get('sources', []):
            if not (s.get('title') and re.match(r'^https://', s.get('url', ''))):
                errors.append(f'{w}: sources 항목은 title, https url 이 필요합니다')
        for f in p.get('faq', []):
            if not (f.get('q') and f.get('a')):
                errors.append(f'{w}: faq 항목은 q, a 가 필요합니다')
        if len(p.get('faq', [])) not in (0, 3, 4, 5, 6):
            errors.append(f'{w}: faq 는 0개 또는 3~6개')
    return errors


def tags_html():
    return ''.join(f'<li>{esc(c)}</li>' for c in CATEGORIES)


def article_html(p, nxt, prv):
    cta = ('<p>지원금 지급 여부는 심사 결과에 따라 달라지며 보장할 수 없습니다. 신청에 필요한 견적서와 시공 전후 사진 등 서류 준비는 시공과 함께 도와드립니다. 현장 사진이나 계약서를 '
           '보내 주시면 상황에 맞춰 안내해 드립니다. 무료 방문 견적은 <a href="/contact">견적 문의</a> 페이지 또는 '
           '<a href="tel:010-2225-6775">010-2225-6775</a>, <a href="tel:010-8694-6775">010-8694-6775</a>로 연락 주세요. '
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


def build_list(posts):
    t = (TPL / 'list.html').read_text(encoding='utf-8')
    cards = ''.join(
        f'<a class="bcard" href="/insight/{p["slug"]}"><div class="bcard-th" style="background-image:url({p["image"]})"></div>'
        f'<div class="bcard-t"><em>{esc(p["category"])}</em>{esc(p["title"])}</div>'
        f'<div class="bcard-x">{esc(p["description"])}</div><small class="bcard-d">{p["date"]}</small></a>' for p in posts)
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


def build_sitemap(posts):
    f = ROOT / 'sitemap.xml'
    t = f.read_text(encoding='utf-8')
    t = re.sub(r'\s*<url><loc>' + re.escape(SITE) + r'/insight[^<]*</loc>.*?</url>', '', t)
    today = posts[0]['date'] if posts else datetime.now(KST).strftime('%Y-%m-%d')
    new = f'\n  <url><loc>{SITE}/insight</loc><lastmod>{today}</lastmod></url>'
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
    keep = {f'{p["slug"]}.html' for p in posts}
    for f in (ROOT / 'insight').glob('*.html'):
        if f.name not in keep:
            f.unlink()
    build_list(posts)
    build_rss(posts)
    build_sitemap(posts)
    build_llms(posts)
    print('메뉴 링크 추가한 페이지:', ensure_nav())
    print('빌드 완료')


if __name__ == '__main__':
    main()
