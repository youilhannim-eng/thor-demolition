#!/usr/bin/env python3
"""포털 검색어 전체 목록 생성 (서울·경기·인천 전 지역 × 전 서비스, 빠짐없이).

    python3 tools/keywords_all.py

출력: keywords/keywords_all.xlsx, keywords/keywords_all.csv
  시트 '검색어'   : 검색어 → 뜨게 할 페이지, 페이지 상태
  시트 '만들 페이지': 전용 페이지가 없는 지역×서비스 조합 (우선순위순)
  시트 '등록처'   : 백링크·등록 가능한 곳
"""
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
SITE = 'https://thorthor.co.kr'
OUT_X = ROOT / 'keywords' / 'keywords_all.xlsx'
OUT_C = ROOT / 'keywords' / 'keywords_all.csv'

PROV_PAGE = {'서울': '/seoul-demolition', '경기': '/gyeonggi-demolition', '인천': '/incheon'}

# 서비스군 -> (기본 페이지, [세부 검색어])   ※ 검색어 앞에 지역명이 붙음
GROUPS = {
    '철거': ('REGION', [
        '철거', '철거업체', '철거 업체', '철거 전문업체', '철거업체 추천', '철거 잘하는곳', '철거 비용', '철거 견적', '철거 가격',
        '철거 공사', '내부철거', '내부 철거 비용', '소규모 철거', '부분 철거', '당일 철거', '24시간 철거',
        '상가 철거', '상가 철거업체', '상가 철거 비용', '상가 내부철거', '점포 철거', '매장 철거',
        '인테리어 철거', '인테리어 철거 비용', '인테리어 철거업체',
        '원상복구', '원상복구 업체', '원상복구 비용', '원상복구 견적', '원상복구 공사', '상가 원상복구', '상가 원상복구 비용',
        '임차 원상복구', '퇴거 원상복구', '폐업 철거', '폐업 원상복구', '폐업 철거 비용',
        '간판 철거', '천장 철거', '바닥 철거', '칸막이 철거', '파티션 철거', '주방 철거', '덕트 철거', '타일 철거', '벽 철거',
        '건물 철거', '주택 철거', '빌라 철거', '창고 철거', '공장 철거', '구조물 해체', '구조물 철거', '비계 철거',
    ]),
    '업종 철거': ('INDUSTRY', [
        f'{biz} {suffix}'
        for biz in ['사무실', '학원', '병원', '의원', '치과', '한의원', '카페', '식당', '음식점', '주점', '술집',
                    '미용실', '네일샵', 'PC방', '헬스장', '노래방', '편의점', '옷가게', '학원가', '프랜차이즈', '매장', '점포']
        for suffix in ['철거', '철거 비용', '철거업체', '원상복구', '원상복구 비용', '인테리어 철거', '폐업 철거']
    ]),
    '폐기물': ('/waste-transport', [
        '폐기물 처리', '폐기물 수거', '폐기물 처리업체', '폐기물 처리 비용', '폐기물 수거 비용', '폐기물 운반',
        '철거 폐기물', '건설폐기물 처리', '사업장폐기물 처리', '혼합폐기물 처리', '인테리어 폐기물 처리',
        '폐기물 배차', '폐기물 1톤', '폐기물 차량', '폐기물 처리장',
    ]),
    '화재복구': ('/fire-restoration', [
        '화재복구', '화재 복구', '화재복구 업체', '화재복구 비용', '화재 철거', '화재 현장 정리', '화재 청소', '화재 원상복구',
        '화재 잔해 처리', '화재 복구 공사',
    ]),
    '유품정리': ('/memorial-cleanup', [
        '유품정리', '유품정리 업체', '유품정리 비용', '유품 정리 서비스', '유품정리 전문', '유품 처리',
    ]),
    '인테리어': ('/interior-construction', [
        '인테리어', '인테리어 업체', '인테리어 비용', '인테리어 견적', '상가 인테리어', '사무실 인테리어', '카페 인테리어',
        '식당 인테리어', '주택 인테리어', '아파트 인테리어', '인테리어 시공',
    ]),
    '리모델링': ('/remodeling', [
        '리모델링', '리모델링 업체', '리모델링 비용', '대수선', '대수선 공사', '대수선 업체', '상가 리모델링', '주택 리모델링',
        '건물 리모델링', '구조 변경 공사', '구조변경',
    ]),
    '건축': ('/building-construction', [
        '건축', '건축업체', '건축 시공', '소규모 건축', '꼬마빌딩 건축', '신축', '증축', '구조 보수', '건물 보수', '건축 견적',
    ]),
    '폐업지원금': ('/support', [
        '폐업지원금', '폐업지원금 신청', '폐업 지원금 철거', '점포철거비 지원', '희망리턴패키지 철거', '폐업 철거 지원금',
    ]),
}
INDUSTRY_PAGE = [  # (검색어에 포함된 말, 페이지)
    ('사무실', '/office-demolition'), ('학원', '/academy-demolition'), ('병원', '/hospital-demolition'),
    ('의원', '/hospital-demolition'), ('치과', '/hospital-demolition'), ('한의원', '/hospital-demolition'),
    ('카페', '/cafe-demolition'), ('식당', '/restaurant-demolition'), ('음식점', '/restaurant-demolition'),
    ('주점', '/restaurant-demolition'), ('술집', '/restaurant-demolition'),
]
# 동 단위는 사람들이 실제로 많이 치는 것만
DONG_KWS = {
    '철거': ['철거', '철거업체', '철거 비용', '상가 철거', '인테리어 철거', '원상복구', '상가 원상복구', '원상복구 비용', '폐업 철거', '내부철거'],
    '업종 철거': ['사무실 철거', '사무실 철거 비용', '카페 철거', '식당 철거', '학원 철거', '병원 철거', '사무실 원상복구', '미용실 철거', '헬스장 철거'],
    '폐기물': ['폐기물 처리', '폐기물 수거', '폐기물 처리 비용'],
    '화재복구': ['화재복구', '화재 철거'],
    '유품정리': ['유품정리', '유품정리 업체'],
    '인테리어': ['인테리어', '상가 인테리어', '인테리어 업체'],
    '리모델링': ['리모델링', '대수선'],
    '건축': ['건축', '건축업체'],
}

TIER1 = {
    '강남구', '서초구', '송파구', '용산구', '마포구', '영등포구', '성동구', '강서구', '구로구', '금천구', '중구', '종로구',
    '미추홀구', '남동구', '부평구', '연수구',
    '성남시', '수원시', '고양시', '용인시', '부천시', '안양시', '화성시', '남양주시', '김포시', '하남시', '광명시', '안산시',
}
TIER3 = {'가평군', '양평군', '연천군', '강화군', '옹진군', '동두천시', '포천시', '여주시', '안성시', '이천시', '양주시'}


def district_pages():
    m = {}
    for f in (ROOT / 'content' / 'services').glob('*.json'):
        p = json.loads(f.read_text(encoding='utf-8'))
        if p.get('district'):
            m[p['district']] = '/' + p['slug']
    m['강남구'] = '/gangnam'
    return m


def short_name(prov, c):
    if c == '중구':
        return '서울 중구'
    if c == '광주시':
        return '경기 광주'
    s = re.sub(r'(구|시|군)$', '', c)
    if prov == '인천' and c in ('서해구', '검단구', '영종구', '제물포구', '강화군', '옹진군'):
        return f'인천 {s}'
    return s


def tier(c):
    return 1 if c in TIER1 else 3 if c in TIER3 else 2


def main():
    regions = json.loads((ROOT / 'content' / 'regions.json').read_text(encoding='utf-8'))
    dpages = district_pages()
    existing = {('/' + f.stem) for f in ROOT.glob('*.html')}

    def page_for(group, kw, region_page):
        base = GROUPS[group][0]
        if base == 'REGION':
            return region_page
        if base == 'INDUSTRY':
            for word, p in INDUSTRY_PAGE:
                if word in kw:
                    return p
            return '/store-demolition'
        return base

    rows = []   # 검색어, 서비스군, 세부, 시도, 지역, 단위, 우선순위, 페이지, 상태
    seen = set()

    def add(kw, group, detail, prov, region, unit, t, page, status):
        if kw in seen:
            return
        seen.add(kw)
        assert page in existing, page
        rows.append([kw, group, detail, prov, region, unit, t, SITE + page, status])

    # 0) 지역 없는 검색어 (전국형)
    for g, (base, kws) in GROUPS.items():
        for kw in kws:
            p = page_for(g, kw, '/service')
            add(kw, g, kw, '', '전국', '지역없음', 1, p, '서비스 페이지')

    # 1) 시도
    for prov, ppage in PROV_PAGE.items():
        for g, (base, kws) in GROUPS.items():
            for kw in kws:
                p = page_for(g, kw, ppage)
                status = '지역+서비스 페이지 있음' if base == 'REGION' else '서비스 페이지만 (지역 전용 없음)'
                add(f'{prov} {kw}', g, kw, prov, prov, '시도', 1, p, status)

    # 2) 시군구·일반구·동
    for e in regions:
        prov, c = e['p'], e['c']
        t = tier(c)
        rp = dpages.get(c) or PROV_PAGE[prov]
        has_rp = c in dpages
        names = [c, short_name(prov, c)]
        for g, (base, kws) in GROUPS.items():
            for kw in kws:
                p = page_for(g, kw, rp)
                if base == 'REGION':
                    status = '지역+서비스 페이지 있음' if has_rp else f'{c} 전용 페이지 없음 → {prov} 페이지'
                else:
                    status = '서비스 페이지만 (지역 전용 없음)'
                for n in names:
                    add(f'{n} {kw}', g, kw, prov, c, '시·군·구', t, p, status)
        for gq in e.get('g') or []:
            gn = gq['n']
            gnames = [f'{c} {gn}', f'{short_name(prov, c)} {gn}', gn]
            for g, (base, kws) in GROUPS.items():
                for kw in kws:
                    p = page_for(g, kw, rp)
                    status = ('지역 페이지(시 단위)' if base == 'REGION' else '서비스 페이지만 (지역 전용 없음)')
                    for n in gnames:
                        add(f'{n} {kw}', g, kw, prov, f'{c} {gn}', '일반구', t, p, status)
            for d in gq.get('d') or []:
                for g, kws in DONG_KWS.items():
                    for kw in kws:
                        p = page_for(g, kw, rp)
                        status = '지역 페이지(시 단위)' if GROUPS[g][0] == 'REGION' else '서비스 페이지만'
                        for n in (d, f'{gn} {d}', f'{c} {d}'):
                            add(f'{n} {kw}', g, kw, prov, f'{c} {gn} {d}', '동', t, p, status)
        for d in e.get('d') or []:
            for g, kws in DONG_KWS.items():
                for kw in kws:
                    p = page_for(g, kw, rp)
                    status = ('지역 페이지(구 단위)' if has_rp else f'{prov} 페이지') if GROUPS[g][0] == 'REGION' else '서비스 페이지만'
                    for n in (d, f'{c} {d}', f'{short_name(prov, c)} {d}'):
                        add(f'{n} {kw}', g, kw, prov, f'{c} {d}', '동', t, p, status)

    # ---- 만들 페이지: 지역×서비스군 중 전용 페이지가 없는 조합 ----
    need = Counter()
    for r in rows:
        if r[5] in ('시도', '시·군·구') and '지역 전용 없음' in r[8]:
            need[(r[6], r[3], r[4], r[1])] += 1
    need_rows = [[t, prov, region, g, n, f'{region} {g} 전용 페이지'] for (t, prov, region, g), n in need.items()]
    need_rows.sort(key=lambda r: (r[0], r[1], r[2], r[3]))
    # 지역 전용 페이지 자체가 없는 시군구
    for e in regions:
        if e['c'] not in dpages:
            need_rows.insert(0, [tier(e['c']), e['p'], e['c'], '철거(지역 페이지)', sum(1 for r in rows if r[4] == e['c'] and r[1] == '철거'), f'{e["c"]} 철거 지역 페이지'])

    platforms = [
        ['네이버 블로그', '글 본문에 지역 키워드 1~2개 + 링크'],
        ['티스토리', '네이버와 다른 글로'],
        ['브런치', '철거 실무 칼럼, 글 끝에 링크'],
        ['네이버 카페(지역·상가·자영업)', '질문에 답하며 자연스럽게'],
        ['네이버 지식iN', '"OO구 원상복구 비용" 질문에 답변 + 출처 링크'],
        ['네이버 플레이스', '강남·용산·인천 사무소 3곳 등록'],
        ['카카오맵 매장관리', '사무소 3곳 등록'],
        ['구글 비즈니스 프로필', '사무소 3곳 등록, 게시물에 지역 키워드'],
        ['당근 비즈프로필', '동네별 소식 글에 동 이름 + 링크'],
        ['숨고·크몽', '프로필 소개에 홈페이지 링크'],
        ['인스타그램 @thorinterior', '프로필 링크'],
        ['유튜브 설명란', '현장 영상 설명에 지역 키워드 + 링크'],
        ['blog.naver.com/yooilhannim', '기존 글에 새 지역 페이지 링크'],
        ['인천철거.com / thordemolition.co.kr', '자사 사이트끼리 해당 페이지로 링크'],
    ]

    # ---- 저장 ----
    hdr = ['검색어', '서비스군', '세부 키워드', '시도', '지역', '단위', '우선순위', '뜨게 할 페이지', '페이지 상태']
    order = list(GROUPS)
    rows.sort(key=lambda r: (order.index(r[1]), {'': 0, '서울': 1, '경기': 2, '인천': 3}[r[3]],
                             ['지역없음', '시도', '시·군·구', '일반구', '동'].index(r[5]), r[6], r[4], r[0]))

    wb = Workbook()
    hf = Font(name='Arial', bold=True, color='FFFFFF')
    hfill = PatternFill('solid', start_color='CA050E')

    def sheet(ws, headers, data, widths):
        ws.append(headers)
        for c in ws[1]:
            c.font, c.fill = hf, hfill
        for r in data:
            ws.append(r)
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = ws.dimensions

    ws = wb.active
    ws.title = '검색어'
    sheet(ws, hdr, rows, [36, 11, 22, 7, 24, 9, 9, 50, 34])
    sheet(wb.create_sheet('만들 페이지'), ['우선순위', '시도', '지역', '서비스군', '해당 검색어 수', '만들 페이지'],
          need_rows, [9, 7, 16, 14, 14, 36])
    sheet(wb.create_sheet('등록처'), ['등록처', '방법'], platforms, [34, 60])
    OUT_X.parent.mkdir(exist_ok=True)
    wb.save(OUT_X)
    with open(OUT_C, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(hdr)
        w.writerows(rows)
    print(f'검색어 {len(rows)}개, 만들 페이지 {len(need_rows)}개 -> {OUT_X}')
    print(Counter(r[5] for r in rows))
    print(Counter(r[1] for r in rows))


if __name__ == '__main__':
    main()
