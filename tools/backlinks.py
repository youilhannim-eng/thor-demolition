#!/usr/bin/env python3
"""백링크용 키워드(앵커텍스트) + 연결 URL 목록 생성.

content/regions.json 의 서울·경기·인천 시·군·구·동과 실제 존재하는 페이지를
조합해 keywords/backlink_keywords.xlsx 로 저장한다.

    python3 tools/backlinks.py
"""
import json
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
SITE = 'https://thorthor.co.kr'
OUT = ROOT / 'keywords' / 'backlink_keywords.xlsx'

PROV_PAGE = {'서울': '/seoul-demolition', '경기': '/gyeonggi-demolition', '인천': '/incheon'}

# 지역 페이지가 아닌, 서비스 페이지로 보내는 키워드
SERVICE_PAGES = [
    ('폐기물 처리', '/waste-transport'),
    ('폐기물 수거', '/waste-transport'),
    ('화재복구', '/fire-restoration'),
    ('화재 철거', '/fire-restoration'),
    ('유품정리', '/memorial-cleanup'),
    ('상가 인테리어', '/interior-construction'),
    ('리모델링', '/remodeling'),
    ('대수선', '/remodeling'),
]
# 지역 페이지로 보내는 키워드 (지역 페이지 내용이 상가 원상복구·인테리어 철거)
REGION_KWS = ['철거', '철거업체', '상가 철거', '원상복구', '상가 원상복구', '인테리어 철거', '철거 견적']
# 업종 페이지
INDUSTRY = [
    ('사무실 철거', '/office-demolition'),
    ('사무실 원상복구', '/office-demolition'),
    ('학원 철거', '/academy-demolition'),
    ('병원 철거', '/hospital-demolition'),
    ('카페 철거', '/cafe-demolition'),
    ('식당 철거', '/restaurant-demolition'),
    ('상가 철거업체', '/store-demolition'),
]
DONG_KWS = ['철거', '상가 철거', '원상복구', '인테리어 철거']

# 1순위: 사무소 인접·상권 큰 지역
TIER1 = {
    '강남구', '서초구', '송파구', '용산구', '마포구', '영등포구', '성동구', '강서구', '구로구', '금천구', '중구', '종로구',
    '미추홀구', '남동구', '부평구', '연수구',
    '성남시', '수원시', '고양시', '용인시', '부천시', '안양시', '화성시', '남양주시', '김포시', '하남시', '광명시', '안산시',
}
TIER3 = {'가평군', '양평군', '연천군', '강화군', '옹진군', '동두천시', '포천시', '여주시', '안성시', '이천시', '양주시'}


def load_pages():
    """district 페이지: 시군구 이름 -> slug"""
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
    if c in TIER1:
        return 1
    if c in TIER3:
        return 3
    return 2


def main():
    regions = json.loads((ROOT / 'content' / 'regions.json').read_text(encoding='utf-8'))
    pages = load_pages()
    existing = {('/' + f.stem) for f in ROOT.glob('*.html')}

    def url(path):
        assert path in existing, path
        return SITE + path

    sig, ind, dong, brand = [], [], [], []

    # 시·도 단위
    for prov, path in PROV_PAGE.items():
        for kw in ['철거업체', '철거', '상가 원상복구', '인테리어 철거', '철거 견적']:
            sig.append([1, prov, prov, f'{prov} {kw}', f'{prov} {kw}', url(path), '시도'])
        for kw, p in SERVICE_PAGES + INDUSTRY:
            sig.append([1, prov, prov, f'{prov} {kw}', f'{prov} {kw}', url(p), '시도'])

    for e in regions:
        prov, c = e['p'], e['c']
        full = c
        short = short_name(prov, c)
        t = tier(c)
        region_page = pages.get(c) or PROV_PAGE[prov]
        note = '' if c in pages else f'{c} 전용 페이지 없음 → {prov} 페이지로'
        for kw in REGION_KWS:
            sig.append([t, prov, c, f'{full} {kw}', f'{short} {kw}', url(region_page), note or '지역'])
        for kw, p in SERVICE_PAGES:
            sig.append([t, prov, c, f'{full} {kw}', f'{short} {kw}', url(p), '서비스'])
        for kw, p in INDUSTRY:
            ind.append([t, prov, c, f'{full} {kw}', f'{short} {kw}', url(p)])
        # 일반구(수원시 장안구 등)
        for g in e.get('g') or []:
            gn = g['n']
            for kw in ['철거', '상가 철거', '원상복구', '인테리어 철거']:
                sig.append([t, prov, f'{c} {gn}', f'{c} {gn} {kw}', f'{short} {gn} {kw}', url(region_page), '일반구'])
            for kw, p in INDUSTRY[:4]:
                ind.append([t, prov, f'{c} {gn}', f'{c} {gn} {kw}', f'{short} {gn} {kw}', url(p)])
            for d in g.get('d') or []:
                for kw in DONG_KWS:
                    dong.append([t, prov, c, gn, d, f'{d} {kw}', f'{c} {gn} {d} {kw}', url(region_page)])
        for d in e.get('d') or []:
            for kw in DONG_KWS:
                dong.append([t, prov, c, '', d, f'{d} {kw}', f'{c} {d} {kw}', url(region_page)])

        # 브랜드·자연문 앵커 (과최적화 방지용)
        brand += [
            [t, prov, c, '브랜드', f'토르철거 {short}', url(region_page)],
            [t, prov, c, '브랜드', f'{short} 철거업체 토르철거', url(region_page)],
            [t, prov, c, '자연문', f'{full}에서 상가 원상복구를 맡긴 철거업체', url(region_page)],
            [t, prov, c, '자연문', f'{full} 상가 철거 견적을 문자로 받은 곳', url(region_page)],
            [t, prov, c, '자연문', f'{short} 인테리어 철거 24시간 상담', url(region_page)],
            [t, prov, c, 'URL형', url(region_page).replace('https://', ''), url(region_page)],
            [t, prov, c, '일반형', '여기', url(region_page)],
        ]

    sig.sort(key=lambda r: (r[0], r[1], r[2]))
    ind.sort(key=lambda r: (r[0], r[1], r[2]))
    dong.sort(key=lambda r: (r[0], r[1], r[2], r[3], r[4]))
    brand.sort(key=lambda r: (r[0], r[1], r[2]))

    # ---- 등록처 ----
    platforms = [
        ['네이버 블로그', '블로그', '글 본문에 지역 키워드 1~2개 + 링크. 하루 1편 이상 쓰지 않기', '시군구 1순위'],
        ['티스토리', '블로그', '네이버와 다른 글로. 같은 글 복사 금지', '시군구 2순위'],
        ['브런치', '블로그', '철거 실무 칼럼 형태. 글 끝에 홈페이지 링크', '브랜드·자연문'],
        ['네이버 카페(지역·상가·자영업 카페)', '커뮤니티', '질문에 답하면서 자연스럽게. 광고성 글은 삭제됨', '자연문'],
        ['네이버 지식iN', '커뮤니티', '"OO구 상가 원상복구 비용" 질문에 답변 + 출처 링크', '시군구·동 단위'],
        ['다음 카페', '커뮤니티', '네이버 카페와 같음', '자연문'],
        ['네이버 플레이스(스마트플레이스)', '지도·디렉토리', '사무소 3곳(강남·용산·인천) 각각 등록, 홈페이지 URL 입력', 'URL형'],
        ['카카오맵 매장관리', '지도·디렉토리', '사무소 3곳 등록', 'URL형'],
        ['구글 비즈니스 프로필', '지도·디렉토리', '사무소 3곳 등록, 웹사이트 입력, 게시물에 지역 키워드', 'URL형·브랜드'],
        ['당근 비즈프로필', '지역', '동네별 노출. 소식 글에 동 이름 + 링크', '동 단위'],
        ['숨고 / 크몽 고수 프로필', '플랫폼', '프로필 소개에 홈페이지 링크', '브랜드'],
        ['인스타그램 @thorinterior 프로필', 'SNS', '프로필 링크 1개. 게시물 본문엔 링크 안 걸림', 'URL형'],
        ['유튜브 채널·영상 설명란', 'SNS', '현장 영상 설명에 지역 키워드 + 링크', '시군구'],
        ['블로그 blog.naver.com/yooilhannim', '자사', '기존 글에 새 지역 페이지 링크 추가', '시군구·동 단위'],
        ['인천철거.com', '자사', '인천 구별 페이지에서 thorthor.co.kr 인천 페이지로 링크', '인천 전 지역'],
        ['thordemolition.co.kr', '자사', '인수 후 각 서비스에서 thorthor.co.kr 해당 페이지로 링크', '전체'],
        ['상가·부동산 커뮤니티(아이러브상가 등)', '커뮤니티', '폐업·원상복구 질문에 답변', '자연문'],
        ['폐업지원금 관련 소상공인 커뮤니티', '커뮤니티', '지원금 신청 대행 안내와 함께', '자연문'],
    ]

    wb = Workbook()
    hdr_font = Font(name='Arial', bold=True, color='FFFFFF')
    hdr_fill = PatternFill('solid', start_color='CA050E')
    body = Font(name='Arial')

    def sheet(ws, headers, rows, widths):
        ws.append(headers)
        for cell in ws[1]:
            cell.font = hdr_font
            cell.fill = hdr_fill
            cell.alignment = Alignment(vertical='center')
        for r in rows:
            ws.append(r)
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.font = body
        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = ws.dimensions

    ws = wb.active
    ws.title = '사용법'
    guide = [
        ['토르철거 백링크 키워드 목록'],
        [''],
        ['시트', '내용', '행 수'],
        ['전체목록', '아래 1~4번 시트를 한 시트에 전부 모은 것. 이것만 봐도 됨 (화면 맨 아래 시트 탭을 누르면 이동)', '=COUNTA(전체목록!A:A)-1'],
        ['1_시군구', '서울 25구·경기 31시군(일반구 포함)·인천 11구군 × 서비스 키워드. 백링크의 중심', '=COUNTA(\'1_시군구\'!A:A)-1'],
        ['2_업종별', '사무실·학원·병원·카페·식당·상가 철거 × 지역 → 업종 페이지', '=COUNTA(\'2_업종별\'!A:A)-1'],
        ['3_동단위', '782개 동 × 4개 키워드. 지식iN·당근·동네 카페용 롱테일', '=COUNTA(\'3_동단위\'!A:A)-1'],
        ['4_브랜드·자연문', '"토르철거 강남", "강남구에서 원상복구를 맡긴 업체" 같은 변형 앵커. 과최적화 방지', '=COUNTA(\'4_브랜드·자연문\'!A:A)-1'],
        ['5_등록처', '백링크를 걸 수 있는 곳과 어떤 시트의 키워드를 쓸지', '=COUNTA(\'5_등록처\'!A:A)-1'],
        [''],
        ['우선순위', '1 = 사무소 인접·상권 큰 지역(강남·서초·송파·용산·미추홀·성남·수원 등). 2 = 나머지 구·시. 3 = 군·외곽'],
        [''],
        ['앵커텍스트 비율(권장)', '정확일치(시군구 철거업체) 30% / 부분일치(지역+서비스 변형) 30% / 브랜드(토르철거 OO) 25% / URL·일반형(여기, thorthor.co.kr) 15%'],
        ['한 글에 지역명', '1~2개만. 지역명을 10개씩 나열한 글은 검색엔진이 스팸으로 봄'],
        ['같은 앵커 반복', '같은 앵커로 같은 URL에 10개 이상 걸지 않기. 변형 시트와 섞기'],
        ['연결 URL', '시트의 URL은 2026-11-07 기준 실제 존재하는 페이지만 넣음. 구 전용 페이지가 없는 강화군·옹진군은 인천 페이지로'],
        ['다시 만들기', 'python3 tools/backlinks.py (행정구역·페이지가 바뀌면 자동 반영)'],
    ]
    for r in guide:
        ws.append(r)
    ws['A1'].font = Font(name='Arial', bold=True, size=14)
    for c in ws[3]:
        c.font = hdr_font
        c.fill = hdr_fill
    for row in ws.iter_rows(min_row=4):
        for cell in row:
            cell.font = body
            cell.alignment = Alignment(wrap_text=True, vertical='top')
    for i, w in enumerate([22, 110, 10], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # 한 시트에 전부 모은 목록 (탭을 찾지 않아도 되게)
    allrows = []
    for r in sig:
        allrows.append(['시군구', r[0], r[1], r[2], r[3], r[4], r[5]])
    for r in ind:
        allrows.append(['업종', r[0], r[1], r[2], r[3], r[4], r[5]])
    for r in dong:
        allrows.append(['동', r[0], r[1], f'{r[2]} {r[3]} {r[4]}'.replace('  ', ' '), r[6], r[5], r[7]])
    for r in brand:
        allrows.append([f'변형·{r[3]}', r[0], r[1], r[2], r[4], r[4], r[5]])
    sheet(wb.create_sheet('전체목록'), ['종류', '우선순위', '시도', '지역', '앵커(정식)', '앵커(축약)', '연결 URL'],
          allrows, [10, 9, 7, 24, 36, 30, 50])

    sheet(wb.create_sheet('1_시군구'), ['우선순위', '시도', '시군구', '앵커(정식)', '앵커(축약)', '연결 URL', '구분'],
          sig, [9, 7, 16, 30, 30, 50, 28])
    sheet(wb.create_sheet('2_업종별'), ['우선순위', '시도', '시군구', '앵커(정식)', '앵커(축약)', '연결 URL'],
          ind, [9, 7, 16, 32, 32, 50])
    sheet(wb.create_sheet('3_동단위'), ['우선순위', '시도', '시군구', '일반구', '동', '앵커(짧게)', '앵커(정식)', '연결 URL'],
          dong, [9, 7, 12, 10, 12, 24, 34, 50])
    sheet(wb.create_sheet('4_브랜드·자연문'), ['우선순위', '시도', '시군구', '유형', '앵커텍스트', '연결 URL'],
          brand, [9, 7, 12, 8, 48, 50])
    sheet(wb.create_sheet('5_등록처'), ['등록처', '종류', '방법', '쓸 키워드 시트'],
          platforms, [34, 14, 70, 18])

    OUT.parent.mkdir(exist_ok=True)
    wb.save(OUT)
    print(f'시군구 {len(sig)} / 업종 {len(ind)} / 동 {len(dong)} / 브랜드 {len(brand)} / 등록처 {len(platforms)} -> {OUT}')


if __name__ == '__main__':
    main()
