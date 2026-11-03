#!/usr/bin/env python3
"""토르철거 서비스 페이지 빌더.  content/services/*.json -> /<slug>.html
사용법: python3 tools/services.py
- 페이지 생성, sitemap.xml / llms.txt 갱신, 푸터에 서비스 링크 추가(템플릿 포함, 여러 번 실행해도 안전)
"""
import html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = 'https://thorthor.co.kr'
CONTENT = ROOT / 'content' / 'services'
TPL = ROOT / 'tools' / 'templates'

IMAGES = {
    '/images/7d84c87416680.jpg': '보호구를 착용한 작업자 두 명이 석고보드 벽체를 해체하는 철거 현장',
    '/images/b1013ad073907.jpg': '철거 후 폐기물이 정리된 현장',
    '/images/fca750281234d.jpg': '건물 한 개 층 내부 철거 현장과 안전망으로 구획한 폐기물 적재 구역',
    '/images/c7a41366da88d.jpg': '원상복구 후 콘크리트 골조만 남은 사무실 내부',
    '/images/0d3e6bfb4928c.jpg': '내부 철거 후 콘크리트가 드러난 아파트 거실',
    '/images/4e32e76cc44b8.jpg': '보양 작업을 마친 주방에서 철거 자재를 정리하는 작업자 두 명',
    '/images/8a649338e8303.jpg': '폐업 정리 중인 주방 철거 현장과 마대에 담긴 철거 폐기물',
    '/images/52b164e6196f8.jpg': '건물 내부 구조물 해체가 진행 중인 층 전경',
}
BANNED = ['최저가', '업계 1위', '업계1위', '무조건', '100% 보장', '100%보장', '타사 견적', '가장 저렴', '국내 최고', '고객 후기']
ALLOWED = {'p', 'h2', 'h3', 'ul', 'ol', 'li', 'strong', 'em', 'a', 'br', 'table', 'thead', 'tbody', 'tr', 'th', 'td'}
INTERNAL = re.compile(r'^/(service|support|portfolio|about|contact|blog|gangnam|incheon|interior-demolition|restoration|insight|interior-construction|waste-transport|memorial-cleanup|fire-restoration|building-construction)$')
LI_MARK = '<!-- svc-links -->'


def esc(s):
    return html.escape(str(s), quote=True)


def load():
    out = []
    for f in sorted(CONTENT.glob('*.json')):
        p = json.loads(f.read_text(encoding='utf-8'))
        p['_f'] = f.name
        out.append(p)
    out.sort(key=lambda p: p.get('order', 99))
    return out


def validate(pages):
    errs = []
    for p in pages:
        w = p['_f']
        for k in ('slug', 'name', 'title', 'description', 'lead', 'image', 'summary', 'sections', 'faq', 'strengths'):
            if not p.get(k):
                errs.append(f'{w}: {k} 비어 있음')
        if errs and errs[-1].startswith(w):
            continue
        if p['image'] not in IMAGES:
            errs.append(f'{w}: image 목록에 없음')
        if len(p['summary']) != 3:
            errs.append(f'{w}: summary 3줄')
        if not 70 <= len(p['description']) <= 160:
            errs.append(f'{w}: description 길이 {len(p["description"])}')
        txt = ' '.join(s['html'] for s in p['sections'])
        for t in re.findall(r'</?([a-zA-Z0-9]+)', txt):
            if t.lower() not in ALLOWED:
                errs.append(f'{w}: 태그 {t}')
                break
        for h in re.findall(r'href="([^"]*)"', txt):
            if not (INTERNAL.match(h) or h.startswith('tel:010') or h.startswith('sms:010')):
                errs.append(f'{w}: 링크 {h}')
        full = txt + ' ' + p['title'] + ' ' + p['description'] + ' ' + ' '.join(f['a'] for f in p['faq'])
        for b in BANNED:
            if b in full:
                errs.append(f'{w}: 금지 표현 {b}')
        if re.search(r'\d+\s*만\s*원|\d+\s*원|평당|㎡당', full):
            errs.append(f'{w}: 금액·단가 수치 금지')
    return errs


CTA = ('<div class="ins-box svc-cta"><b>견적 안내</b><ul>'
       '<li>현장 사진, 주소, 평수, 층수를 문자로 보내 주시면 바로 견적을 안내해 드립니다.</li>'
       '<li>현장 방문 견적도 가능합니다.</li>'
       '<li>문의: <a href="tel:010-2225-6775">010-2225-6775</a> · <a href="tel:010-8694-6775">010-8694-6775</a> · <a href="/contact">견적 문의 페이지</a></li>'
       '</ul></div>')


def related(p, pages):
    items = ''.join(f'<li><a href="/{q["slug"]}">{esc(q["name"])}</a></li>' for q in pages if q['slug'] != p['slug'])
    return f'<h2>다른 서비스</h2><ul>{items}<li><a href="/service">철거 서비스</a></li><li><a href="/restoration">상가 원상복구</a></li><li><a href="/insight">인사이트 글 모아보기</a></li></ul>'


def jsonld(p):
    url = f'{SITE}/{p["slug"]}'
    g = [
        {'@context': 'https://schema.org', '@type': 'Service', 'name': p['name'], 'serviceType': p['name'], 'description': p['description'],
         'url': url, 'inLanguage': 'ko', 'areaServed': ['서울', '경기', '인천'],
         'provider': {'@type': 'Organization', 'name': '토르철거', 'url': SITE, 'telephone': '010-2225-6775'}},
        {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': '토르철거', 'item': SITE + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': p['name'], 'item': url}]},
        {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
            {'@type': 'Question', 'name': f['q'], 'acceptedAnswer': {'@type': 'Answer', 'text': f['a']}} for f in p['faq']]},
    ]
    return '\n'.join('<script type="application/ld+json">\n' + json.dumps(x, ensure_ascii=False, indent=1).replace('</', '<\\/') + '\n</script>' for x in g)


def header_block(p):
    return ('<div class="thorBI">\n  <span class="thorBI-eye">THOR SERVICE</span>\n'
            f'  <h1 class="thorBI-h1">{esc(p["name"])}</h1>\n'
            f'  <p class="thorBI-lead">{esc(p["lead"])}</p>\n</div>\n')



AREAS = {
    '서울': ['종로구', '중구', '용산구', '성동구', '광진구', '동대문구', '중랑구', '성북구', '강북구', '도봉구', '노원구', '은평구', '서대문구', '마포구', '양천구', '강서구', '구로구', '금천구', '영등포구', '동작구', '관악구', '서초구', '강남구', '송파구', '강동구'],
    '경기': ['수원시(장안구·권선구·팔달구·영통구)', '성남시(수정구·중원구·분당구)', '의정부시', '안양시(만안구·동안구)', '부천시(원미구·소사구·오정구)', '광명시', '평택시', '동두천시', '안산시(상록구·단원구)', '고양시(덕양구·일산동구·일산서구)', '과천시', '구리시', '남양주시', '오산시', '시흥시', '군포시', '의왕시', '하남시', '용인시(처인구·기흥구·수지구)', '파주시', '이천시', '안성시', '김포시', '화성시', '광주시', '양주시', '포천시', '여주시', '연천군', '가평군', '양평군'],
    '인천': ['중구', '동구', '미추홀구', '연수구', '남동구', '부평구', '계양구', '서구', '강화군', '옹진군'],
}


def areas_block():
    rows = ''.join(f'<p><b>{k}</b> {esc(", ".join(v))}</p>' for k, v in AREAS.items())
    return (f'<h2>서비스 지역</h2><div class="svc-area">{rows}'
            '<p class="small">인천은 2026년 7월 신설된 제물포구·영종구·검단구 지역을 포함합니다. 위에 없는 동네도 문의 주시면 가능 여부를 안내해 드립니다.</p></div>')


def article(p, pages):
    summ = ''.join(f'<li>{esc(x)}</li>' for x in p['summary'])
    secs = ''.join(f'<h2>{esc(s["h2"])}</h2>{s["html"]}' for s in p['sections'])
    faq = ''.join(f'<div class="ins-q"><h3>{esc(f["q"])}</h3><p>{esc(f["a"])}</p></div>' for f in p['faq'])
    alt = esc(IMAGES[p['image']])
    cards = ''.join(f'<div class="svc-card"><b>{esc(s["t"])}</b><p>{esc(s["d"])}</p></div>' for s in p.get('strengths', []))
    strengths = f'<h2>토르철거가 선택받는 이유</h2><div class="svc-grid">{cards}</div>' if cards else ''
    lic = ''
    if p.get('licenses'):
        li = ''.join(f'<li>{esc(x)}</li>' for x in p['licenses'])
        lic = f'<h2>면허·등록·보험</h2><ul class="svc-lic">{li}</ul>'
    return (f'<article class="bpost"><div class="bpost-body ins-body fr-view">'
            f'<p><img alt="{alt}" class="fr-dii" src="{p["image"]}"/></p>'
            f'<div class="ins-box"><b>3줄 요약</b><ul>{summ}</ul></div>'
            f'{strengths}{secs}{lic}{areas_block()}<h2>자주 묻는 질문</h2>{faq}{CTA}</div></article>')


def focus(t, p):
    """키워드 랜딩 페이지: 다른 서비스·메뉴가 보이지 않게 상단/하단을 단순화한다."""
    name = esc(p['name'])
    # 상단: 로고 + 전화 버튼만
    t = re.sub(r'<header class="thd" id="thd">.*?</header>',
               '<header class="thd" id="thd"><div class="thd-in"><a class="thd-logo" href="/"><img src="/images/logo-90.jpg" alt="토르철거" width="30" height="30"><span>토르철거</span></a>'
               '<a class="thd-cta" style="margin-left:auto" href="tel:01022256775">전화 상담 010-2225-6775</a></div></header>', t, count=1, flags=re.S)
    # 하단: 바로가기 목록을 견적·전화로 한정
    t = re.sub(r'<h4>바로가기</h4>\s*<ul class="fnav">.*?</ul>',
               '<h4>문의</h4>\n<ul class="fnav">\n<li><a href="/contact">견적 문의</a></li>\n<li><a href="tel:01022256775">전화 상담 010-2225-6775</a></li>\n<li><a href="tel:01086946775">추가 문의 010-8694-6775</a></li>\n</ul>', t, count=1, flags=re.S)
    t = re.sub(r'<p class="fdesc">.*?</p>',
               f'<p class="fdesc">서울 · 인천 · 경기 수도권 전 지역, {name}. 토르철거가 직접 진행합니다.</p>', t, count=1, flags=re.S)
    t = re.sub(r'(<div class="fbot">\s*<em>[^<]*</em>\s*)<em>[^<]*</em>', lambda m: m.group(1) + f'<em>{name}</em>', t, count=1)
    return t


def build_page(p, pages):
    t = (TPL / 'post.html').read_text(encoding='utf-8')
    t = re.sub(r'<div class="thorBI">.*?</div>\n(?=<style>)', lambda m: header_block(p), t, count=1, flags=re.S)
    url = f'{SITE}/{p["slug"]}'
    rep = {'{{TITLE_TAG}}': esc(p['title']), '{{DESC}}': esc(p['description']), '{{URL}}': url,
           '{{OG_IMAGE}}': SITE + p['image'], '{{DATE}}': p.get('date', '2026-11-02'),
           '{{JSONLD}}': jsonld(p), '{{ARTICLE}}': article(p, pages), '{{TAGS}}': ''}
    for k, v in rep.items():
        t = t.replace(k, v)
    assert '{{' not in t
    t = focus(t, p)
    (ROOT / f'{p["slug"]}.html').write_text(t, encoding='utf-8')


def links_li(pages):
    return LI_MARK + ''.join(f'\n<li><a href="/{p["slug"]}">{esc(p["name"])}</a></li>' for p in pages)


def ensure_footer(pages):
    li = links_li(pages)
    n = 0
    files = list(ROOT.glob('*.html')) + list((ROOT / 'blog').glob('*.html')) + list((ROOT / 'insight').glob('*.html')) + list(TPL.glob('*.html'))
    for f in files:
        t = f.read_text(encoding='utf-8')
        t2 = re.sub(re.escape(LI_MARK) + r'.*?(?=\n?<li><a href="/(?:gangnam|incheon)"|</ul>)', '', t, flags=re.S) if LI_MARK in t else t
        key = '<li><a href="/insight">인사이트</a></li>'
        head, sep, tail = t2.rpartition(key)
        new = (head + sep + '\n' + li + tail) if sep else t2
        if new != t:
            f.write_text(new, encoding='utf-8')
            n += 1
    return n


def build_sitemap(pages):
    f = ROOT / 'sitemap.xml'
    t = f.read_text(encoding='utf-8')
    for p in pages:
        t = re.sub(r'\s*<url><loc>' + re.escape(f'{SITE}/{p["slug"]}') + r'</loc>.*?</url>', '', t)
    add = ''.join(f'\n  <url><loc>{SITE}/{p["slug"]}</loc><lastmod>{p.get("date", "2026-11-02")}</lastmod></url>' for p in pages)
    t = t.replace('</urlset>', add + '\n</urlset>')
    f.write_text(t, encoding='utf-8')


def build_llms(pages):
    f = ROOT / 'llms.txt'
    t = f.read_text(encoding='utf-8')
    t = re.sub(r'\n*<!-- services:start -->.*?<!-- services:end -->\n*', '\n', t, flags=re.S).rstrip() + '\n'
    lines = ['', '<!-- services:start -->', '# 토르철거 시공 서비스', '',
             '> 서울·경기·인천 지역 철거·원상복구·인테리어·건축·폐기물 운반처리·유품정리·화재복구 시공.', '']
    lines += [f'- [{p["name"]}]({SITE}/{p["slug"]}): {p["description"]}' for p in pages]
    lines += ['<!-- services:end -->', '']
    f.write_text(t + '\n'.join(lines), encoding='utf-8')


VC_START, VC_END = '<!-- vert:start -->', '<!-- vert:end -->'


def vert_block(pages):
    cards = ''
    for q in pages:
        first = q['lead'].split('. ')[0].split('습니다.')[0]
        first = first if first.endswith('.') else first + ('습니다.' if q['lead'].startswith(first + '습니다') else '.')
        cards += (f'<a class="vc-card" href="/{q["slug"]}"><span class="vc-img"><img src="{q["image"]}" alt="{esc(q["name"])}" loading="lazy"></span>'
                  f'<span class="vc-bd"><b>{esc(q["name"])}</b><span>{esc(first)}</span><em>자세히 보기 →</em></span></a>')
    return (f'{VC_START}<section class="vc"><div class="vc-in"><p class="vc-k">SERVICE</p><h2>분야별 전문 시공</h2>'
            f'<p class="vc-d">찾으시는 분야를 눌러 전용 안내를 확인하세요.</p><div class="vc-grid">{cards}</div></div></section>{VC_END}\n')


def ensure_vert(pages):
    block = vert_block(pages)
    targets = {'index.html': '<section class="sec ba">',
               'service.html': '<section class="sec"><div class="wrap"><p class="eyebrow">FAQ'}
    n = 0
    for name, anchor in targets.items():
        f = ROOT / name
        t = f.read_text(encoding='utf-8')
        t2 = re.sub(re.escape(VC_START) + r'.*?' + re.escape(VC_END) + r'\n?', '', t, flags=re.S)
        assert anchor in t2, (name, anchor)
        t2 = t2.replace(anchor, block + anchor, 1)
        if t2 != t:
            f.write_text(t2, encoding='utf-8')
            n += 1
    return n


def main():
    pages = load()
    errs = validate(pages)
    if errs:
        print('검증 실패:')
        for e in errs:
            print(' -', e)
        sys.exit(1)
    for p in pages:
        build_page(p, pages)
    build_sitemap(pages)
    build_llms(pages)
    print('푸터 링크 갱신 파일 수:', ensure_footer(pages))
    print('홈·서비스 분야 카드 갱신:', ensure_vert(pages))
    print('서비스 페이지', len(pages), '개 빌드 완료')


if __name__ == '__main__':
    main()
