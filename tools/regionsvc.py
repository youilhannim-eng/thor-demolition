"""지역 × 서비스 전용 페이지 생성기 (2026-11-07)

"인천 화재복구", "강남 유품정리"처럼 지역 이름이 붙은 검색어는 제목에 지역+서비스가 들어간 페이지가 있어야 노출됩니다.
이 스크립트는 지역 페이지(content/services/<지역>-demolition.json 등)와 서비스 페이지(fire-restoration.json 등)를 합쳐
content/services/<지역>-<서비스>.json 을 만듭니다. 그다음 `python3 tools/services.py` 가 HTML 로 빌드합니다.

- 지역 정보(동 목록, 상권 특징, 가까운 사무소)는 지역 페이지에서, 서비스 설명·진행 순서·비용·FAQ 는 서비스 페이지에서 가져옵니다.
- 회사에 대한 사실은 기존 페이지에 이미 있는 내용만 씁니다. 지어낸 사례·수치는 넣지 않습니다.
- 다시 실행해도 안전합니다(같은 파일을 덮어씀). 손으로 고친 파일은 "handmade": true 를 넣으면 건너뜁니다.

실행: python3 tools/regionsvc.py && python3 tools/services.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / 'content' / 'services'
sys.path.insert(0, str(ROOT / 'tools'))

# 서비스군 → (기본 페이지 slug, 페이지 이름, 짧은 이름, 브랜드, 검색어에 붙는 말)
SERVICES = {
    'fire-restoration': ('화재복구', '화재복구', '토르환경', '화재 현장 잔해 철거·폐기물 처리·복구 시공'),
    'memorial-cleanup': ('유품정리', '유품정리', '토르환경', '유품 분류·정리·폐기물 처리·청소'),
    'waste-transport': ('폐기물 처리', '폐기물', '토르환경', '철거·사업장 폐기물 운반·처리'),
    'interior-construction': ('인테리어', '인테리어', '토르인테리어', '상가·사무실 인테리어 시공'),
    'remodeling': ('리모델링·대수선', '리모델링', '토르건축', '건물 대수선·리모델링 공사'),
    'building-construction': ('건축·구조 공사', '건축', '토르건축', '구조 변경·보수·건축 공사'),
    'closure-support': ('폐업지원금 철거', '폐업지원금', '토르철거', '폐업 점포 철거비 지원 제도 안내·철거 시공'),
    'business-demolition': ('업종별 철거', '업종별 철거', '토르철거', '상가·음식점·사무실·학원·병원·카페 철거'),
}
TYPES = ['store-demolition', 'restaurant-demolition', 'office-demolition', 'academy-demolition', 'hospital-demolition', 'cafe-demolition']

# JSON 이 없는 지역(손으로 만든 페이지)의 지역 정보
META = {
    'gangnam': {'district': '강남구', 'province': '서울', 'short': '강남',
                'locale': '강남구 역삼·논현·삼성·대치·신사·청담·압구정·도곡·개포·일원·수서·세곡 일대',
                'office': '강남 본사(역삼동)가 있어 강남 전 지역 출동이 가장 빠릅니다.',
                'feat': '<ul><li>테헤란로·강남대로 대형 오피스는 관리단의 작업 시간·승강기 사용·보양 규정을 먼저 확인합니다.</li>'
                        '<li>신사·압구정·청담 일대 매장은 인테리어 마감이 두꺼워 철거 범위와 폐기물 양을 현장에서 확인합니다.</li>'
                        '<li>대치·도곡 학원가는 칸막이·방음 벽체·조명 배선이 많아 원상복구 범위를 먼저 정합니다.</li></ul>'},
    'incheon': {'district': None, 'province': '인천', 'short': '인천', 'region': '인천',
                'locale': '인천광역시 미추홀·남동·부평·계양·연수·서해·제물포·영종·검단·강화·옹진 전 지역',
                'office': '인천 사무소(미추홀구 경인북길)가 있어 인천 전 지역 출동이 빠릅니다.',
                'feat': '<ul><li>구월·주안·부평 상권은 음식점·주점 업종 전환이 잦아 주방 설비와 후드·덕트 정리가 많습니다.</li>'
                        '<li>송도·청라·검단 신도시 상가와 오피스는 관리단 공사 규정과 승강기 예약을 먼저 확인합니다.</li>'
                        '<li>남동·서해 공단 지역은 창고·공장 설비 해체와 대형 폐기물 반출이 함께 진행됩니다.</li>'
                        '<li>강화·옹진은 교량 또는 여객선으로 차량을 들여야 해 반출 일정을 먼저 잡습니다.</li></ul>'},
    'seoul': {'district': None, 'province': '서울', 'short': '서울', 'region': '서울',
              'locale': '서울특별시 25개 구 전 지역', 'office': '강남 본사와 용산 사무소에서 서울 전 지역으로 출동합니다.'},
    'gyeonggi': {'district': None, 'province': '경기', 'short': '경기', 'region': '경기',
                 'locale': '경기도 31개 시·군 전 지역', 'office': '강남·용산·인천 세 사무소에서 가까운 팀이 경기 전 지역으로 출동합니다.'},
}


def load(slug):
    f = CONTENT / f'{slug}.json'
    return json.loads(f.read_text(encoding='utf-8')) if f.exists() else None


def short_area(n):
    return n[:-1] if len(n) > 2 and n[-1] in '구시군' else n


def region_info(rslug):
    """지역 slug → dict(district, province, short, locale, office, feat(html), gallery, region)"""
    if rslug in META:
        m = dict(META[rslug])
        base = load(f'{rslug}-demolition')
        if base:
            m['gallery'] = base.get('gallery', [])
            if not m.get('feat') and base.get('sections'):
                m['feat'] = base['sections'][0]['html']
        return m
    d = load(f'{rslug}-demolition')
    if not d or not d.get('district'):
        return None
    desc = d['description']
    m = re.match(r'^(.*?) (철거와 원상복구를|상가·사무실·주택 철거와)', desc)
    locale = m.group(1) if m else d['district']
    office = d['summary'][1] if len(d.get('summary', [])) > 1 else ''
    feat = d['sections'][0]['html'] if d.get('sections') else ''
    return {'district': d['district'], 'province': d.get('province', '서울'), 'short': short_area(d['district']),
            'locale': locale, 'office': office, 'feat': feat, 'gallery': d.get('gallery', []), 'region': None}


def closure_base():
    """/support(폐업지원금) 페이지 내용으로 만든 기본 서비스 데이터. 금액·비율은 적지 않는다."""
    return {
        'name': '폐업지원금 철거', 'image': '/images/8a649338e8303.jpg', 'eyebrow': 'THOR DEMOLITION',
        'description': '폐업 점포 철거·원상복구 비용을 지원하는 소상공인 지원 제도 안내와 철거 시공, 증빙 서류 정리까지 토르철거가 함께 진행합니다.',
        'lead': '폐업을 앞두고 철거비가 부담되신다면 정부·지자체의 소상공인 폐업 지원 사업을 먼저 확인하세요. 신청 순서와 증빙 준비를 돕고, 승인 뒤 철거까지 직접 시공합니다.',
        'summary': ['소상공인 폐업 지원 사업에는 점포 철거·원상복구 비용을 지원하는 항목이 있습니다. 대상·한도·기간은 해당 연도 공고 기준입니다.',
                    '철거를 먼저 하면 지원 대상에서 빠질 수 있어, 신청·승인 뒤에 철거하는 순서가 기본입니다.',
                    '견적서·세금계산서·시공 전후 사진 등 정산에 필요한 자료를 시공과 함께 정리해 드립니다.'],
        'chips': ['신청 순서 안내', '증빙 서류 정리', '승인 후 철거 시공', '상담 24시간 · 연중무휴'],
        'sections': [
            {'h2': '폐업 점포 철거비, 지원받을 수 있는 제도가 있습니다',
             'html': '<p>소상공인 폐업을 지원하는 정부 사업(희망리턴패키지 등)에는 점포 철거·원상복구 비용을 지원하는 항목이 포함되어 있습니다. 대상 요건과 지원 한도는 매년 사업 공고에 따라 달라지며, 신청 후 심사를 거쳐 결정됩니다.</p>'
                     '<ul><li><strong>무엇을 지원하나요</strong> 폐업(예정) 점포의 철거·원상복구 비용 일부를 지원하는 방식입니다.</li>'
                     '<li><strong>누가 신청하나요</strong> 사업자 본인이 공식 신청 시스템에서 직접 신청합니다. 대리 신청은 원칙적으로 불가합니다.</li>'
                     '<li><strong>언제 신청하나요</strong> 철거를 진행하기 전에 신청·승인 절차를 먼저 밟는 것이 기본 순서입니다.</li></ul>'
                     '<p>지원 금액·비율·신청 기간은 해당 연도 공고에 따라 달라집니다. 토르철거는 시공 업체이며 지급 여부를 보장하거나 대신 신청해 드리지 않습니다. 정확한 내용은 소상공인시장진흥공단과 관할 지자체 공고를 확인해 주세요. 자세한 안내는 <a href="/support">폐업지원금 안내</a>에 있습니다.</p>'},
            {'h2': '대상 여부, 이런 항목을 봅니다',
             'html': '<ul><li>업종·규모: 소상공인 기준에 해당하는 사업자(업종별 매출·상시근로자 기준)</li><li>사업 기간: 일정 기간 이상 사업을 영위한 사업자(공고 기준)</li>'
                     '<li>점포 형태: 임차 점포 등 원상복구·철거가 필요한 사업장</li><li>진행 시점: 철거 전에 신청·승인 절차를 먼저 밟는 것이 원칙</li>'
                     '<li>제외 대상: 일부 업종과 중복 수혜 등은 제외될 수 있음</li></ul><p>위 내용은 일반 안내이며 개별 사업장의 지원 가능 여부를 판단하는 기준이 아닙니다.</p>'},
        ],
        'steps_h2': '신청부터 정산까지',
        'steps': [{'t': '사업 공고 확인', 'd': '해당 연도 소상공인 폐업 지원 사업 공고에서 대상·한도·기간을 먼저 확인합니다.'},
                  {'t': '온라인 신청', 'd': '지정된 신청 시스템에서 사업자 정보와 점포 정보를 등록합니다.'},
                  {'t': '대상 확정', 'd': '서류 검토와 심사를 거쳐 지원 대상 여부가 결정됩니다.'},
                  {'t': '철거 시공', 'd': '승인 이후 철거를 진행하고, 진행 과정을 사진으로 남깁니다.'},
                  {'t': '증빙·정산', 'd': '견적서, 세금계산서, 시공 전후 사진 등을 제출해 정산합니다.'}],
        'cost': {'h2': '철거 견적이 달라지는 이유', 'intro': '같은 평수여도 견적은 현장 조건에 따라 달라집니다. 견적서를 받으면 아래 항목부터 비교해 보세요.',
                 'items': [{'t': '철거 범위', 'd': '내부 전체인지 일부인지, 천장·바닥·벽 중 어디까지인지에 따라 달라집니다.'},
                           {'t': '폐기물 종류와 양', 'd': '주방 설비·집기·마감재 등 종류와 양에 따라 처리 방식이 달라집니다.'},
                           {'t': '층수와 반출 동선', 'd': '엘리베이터 사용 가능 여부, 주차 거리, 야간 작업 조건에 따라 달라집니다.'},
                           {'t': '원상복구 마감', 'd': '임대차 계약서의 원상복구 기준에 따라 마감 작업이 추가될 수 있습니다.'}]},
        'check': {'h2': '철거 전에 확인할 것', 'items': ['임대차 종료일과 지원 사업 일정을 먼저 비교했는지', '승인 전에 철거를 시작하지 않았는지', '시공 전 상태 사진을 남겨 두었는지',
                                                  '견적서·세금계산서의 사업자 정보가 신청 정보와 일치하는지', '필요 서류를 시공 중에 함께 정리하는지']},
        'prep': {'h2': '상담 전에 준비하면 좋은 정보', 'intro': '모두 준비하지 못하셔도 사진 몇 장과 주소만 보내 주시면 상담을 시작할 수 있습니다.',
                 'items': ['현장 주소와 층수, 대략적인 평수', '현재 상태 사진(입구, 내부 전경, 천장, 바닥)', '임대차 종료일과 원상복구 조항', '지원 사업 신청 여부와 진행 단계', '희망 철거일']},
        'subs': [{'t': '철거 견적서', 'd': '작업 범위와 항목이 구분된 견적서를 발행합니다.', 'img': '/images/demolition-dc4c767d.jpg', 'alt': '주방 설비를 철거하고 배관이 드러난 업소 주방'},
                 {'t': '세금계산서·계약서', 'd': '사업자 간 정식 거래 증빙으로 발행합니다.', 'img': '/images/demolition-ca1ba1fa.jpg', 'alt': '점포 내부 마감을 철거한 뒤 전면 유리가 남은 현장'},
                 {'t': '시공 전·후 사진', 'd': '같은 각도에서 촬영한 전후 사진을 정리합니다.', 'img': '/images/demolition-0bb69dc9.jpg', 'alt': '바닥 마감을 철거해 콘크리트가 드러난 좁고 긴 점포'},
                 {'t': '폐기물 처리 자료', 'd': '배출·처리 관련 자료가 필요하면 함께 준비합니다.', 'img': '/images/demolition-e09988a1.jpg', 'alt': '벽체 마감을 철거하고 바닥을 정리 중인 소형 점포'}],
        'situations': [{'t': '임대차 종료일이 얼마 안 남았다', 'd': '지원 사업 일정과 철거 일정을 함께 놓고 순서를 정합니다.'},
                       {'t': '신청을 먼저 해야 하는지 모르겠다', 'd': '철거 전에 신청·승인을 받는 것이 기본 순서입니다.'},
                       {'t': '서류가 어렵다', 'd': '견적서·세금계산서·사진을 정산 양식에 맞춰 정리해 드립니다.'},
                       {'t': '지원 대상이 아니어도 철거는 해야 한다', 'd': '지원 여부와 관계없이 예산에 맞춰 범위를 조정해 진행합니다.'}],
        'redflags': ['승인 전에 철거부터 하자고 하는 경우', '지원금 지급을 보장한다고 말하는 경우', '견적서에 항목 구분 없이 총액만 적는 경우', '시공 전 사진을 남기지 않는 경우'],
        'gallery_h2': '폐업 점포 철거 현장 사진', 'gallery_note': '폐업 점포를 철거하고 정리한 실제 현장 사진입니다.',
        'gallery': [{'src': '/images/demolition-6b98d8da.jpg', 'alt': '보양 비닐과 테이프로 구획한 철거 현장', 'w': 480, 'h': 640},
                    {'src': '/images/demolition-f3eca618.jpg', 'alt': '보양 비닐로 구획하고 장비를 배치한 철거 현장', 'w': 480, 'h': 640},
                    {'src': '/images/demolition-e48d15be.jpg', 'alt': '바닥 마감을 철거한 넓은 창가 사무 공간', 'w': 480, 'h': 640},
                    {'src': '/images/demolition-61d057ac.jpg', 'alt': '천장을 철거해 구조물이 드러난 좁은 상가 내부', 'w': 480, 'h': 640}],
        'faq': [{'q': '지원 금액이 정확히 얼마인가요?', 'a': '한도와 지원 비율은 해당 연도 사업 공고에 따라 달라지고, 심사 결과에 따라 실제 지급액도 달라집니다. 반드시 공식 공고를 확인해 주세요.'},
                {'q': '철거를 먼저 하고 나중에 신청해도 되나요?', 'a': '일반적으로 신청과 승인 절차를 먼저 거치는 것이 원칙입니다. 순서를 지키지 않으면 지원 대상에서 제외될 수 있습니다.'},
                {'q': '신청은 토르철거가 대신 해주나요?', 'a': '신청은 사업자 본인이 직접 하셔야 합니다. 저희는 철거 시공과 함께 견적서, 세금계산서, 시공 전후 사진 등 증빙 자료를 정리해 드립니다.'},
                {'q': '지원 대상이 아니면 철거를 못 하나요?', 'a': '아닙니다. 지원 여부와 관계없이 철거·원상복구 시공은 그대로 진행할 수 있습니다. 예산에 맞춰 범위를 조정하는 방법도 상담해 드립니다.'}],
    }


def business_base(reg):
    """업종별 철거 지역 페이지: 6개 업종 페이지의 내용을 모아 지역 이름을 붙인다."""
    types = [load(t) for t in TYPES]
    subs = [{'t': t['name'], 'd': t['lead'].split('. ')[0] + '.', 'img': t['image'], 'alt': t.get('h1', t['name']) + ' 현장', 'href': f'/{t["slug"]}'} for t in types]
    sec = ''.join(f'<li><a href="/{t["slug"]}"><strong>{reg["short"]} {t["name"]}</strong></a> {t["lead"].split(". ")[0]}.</li>' for t in types)
    return {
        'name': '업종별 철거', 'image': types[0]['image'], 'eyebrow': 'THOR DEMOLITION',
        'description': '상가·음식점·사무실·학원·병원·카페 등 업종별 철거와 원상복구를 토르철거가 직접 시공합니다. 사진 견적 바로 회신, 현장 방문 견적 무료.',
        'lead': '상가, 음식점, 사무실, 학원, 병원, 카페는 업종마다 설비와 마감이 달라 철거 범위와 폐기물 처리가 달라집니다. 업종에 맞춰 범위를 정하고 직접 시공합니다.',
        'summary': ['상가·음식점·사무실·학원·병원·카페 등 업종별 철거와 원상복구를 직접 시공합니다.', '업종마다 다른 설비(주방·후드·칸막이·급배수·전기)를 먼저 확인해 철거 범위를 정합니다.', '사진·주소·평수·층수를 문자로 보내면 바로 견적을 안내합니다.'],
        'chips': ['업종별 철거 범위 안내', '직접 시공', '폐기물 처리까지', '상담 24시간 · 연중무휴'],
        'sections': [{'h2': '업종별로 철거 범위가 다릅니다', 'html': f'<ul>{sec}</ul>'}],
        'steps_h2': '업종별 철거 진행 순서', 'steps': types[0]['steps'], 'cost': types[0]['cost'], 'check': types[0]['check'], 'prep': types[0]['prep'],
        'subs': subs, 'situations': types[0].get('situations', []), 'redflags': types[0].get('redflags', []),
        'gallery_h2': '철거 현장 사진', 'gallery_note': '토르철거가 직접 철거한 현장 사진입니다. 철거 범위와 마무리 상태를 확인하세요.',
        'gallery': [], 'faq': [f for t in types for f in t['faq'][:1]],
    }


def make(rslug, svc):
    reg = region_info(rslug)
    if not reg:
        return None
    if svc == 'closure-support':
        base = closure_base()
    elif svc == 'business-demolition':
        base = business_base(reg)
        base['gallery'] = reg.get('gallery', [])[:8]
        base['image'] = base['gallery'][0]['src'] if base['gallery'] else '/images/demolition-2c6544d5.jpg'
    else:
        base = load(svc)
    sname, sshort, brand, tagline = SERVICES[svc]
    short, district, prov = reg['short'], reg.get('district'), reg['province']
    area = district or f'{prov} 전 지역'
    name = f'{short} {sname}'
    title = f'{short} {sname} | {area} {tagline} | {brand}'
    desc = f'{reg["locale"]} {sname} 시공을 {brand}(토르철거)가 직접 진행합니다. {reg["office"]} 사진 견적 당일 회신, 현장 방문 견적 무료.'
    if len(desc) > 160:
        desc = f'{area} {sname}을 {brand}(토르철거)가 직접 진행합니다. {reg["office"]} 사진 견적 당일 회신, 현장 방문 견적 무료.'
    if len(desc) > 160:
        desc = desc[:157].rsplit(' ', 1)[0] + '.'
    lead = f'{reg["locale"]}까지, {base["lead"]} {reg["office"]}'.strip()
    summary = [f'{area} {base["summary"][0]}', reg['office'] or base['summary'][1], base['summary'][2]]
    # 지역 특징 + 서비스 설명
    secs = []
    if reg.get('feat'):
        secs.append({'h2': f'{area} 현장·상권 특징', 'html': reg['feat']})
    for s in base['sections']:
        secs.append({'h2': s['h2'] if short in s['h2'] else s['h2'], 'html': s['html']})
    link_svc = '/support' if svc == 'closure-support' else ('/store-demolition' if svc == 'business-demolition' else f'/{svc}')
    secs.append({'h2': f'{short} {sname}, 이렇게 의뢰하세요',
                 'html': f'<ol><li>{area} 현장 사진 몇 장과 주소, 대략적인 평수·층수를 문자로 보내 주세요. 당일에 견적 방향을 안내합니다.</li>'
                         f'<li>현장 방문 견적은 무료입니다. {reg["office"]}</li>'
                         f'<li>견적서에 작업 범위를 적어 드리고, 요청하신 추가 작업이 없으면 추가 요금이 없습니다.</li></ol>'
                         f'<p>{sname} 전체 안내는 <a href="{link_svc}">{sname} 서비스</a>에서, {short} 철거·원상복구는 <a href="/{rslug if rslug in ("gangnam", "incheon") else rslug + "-demolition"}">{short} 철거</a>에서 확인하실 수 있습니다.</p>'})
    faq = [{'q': f'{area}도 {sname} 출동이 되나요?', 'a': f'됩니다. {reg["locale"]}까지 같은 팀이 출동합니다. {reg["office"]}'.strip()}]
    faq += base['faq'][:4]
    chips = [f'{area} 출동'] + [c for c in base.get('chips', []) if '서울' not in c and '출동' not in c][:2] + ['상담 24시간 · 연중무휴']
    p = {
        'name': name, 'title': title, 'description': desc, 'lead': lead, 'image': base['image'], 'summary': summary,
        'strengths': load('fire-restoration')['strengths'], 'sections': secs, 'faq': faq,
        'slug': f'{rslug}-{svc}', 'order': 300, 'date': '2026-11-07', 'licenses': load('fire-restoration')['licenses'],
        'h1': name, 'eyebrow': base.get('eyebrow', 'THOR SERVICE'), 'chips': chips,
        'gallery_h2': base.get('gallery_h2'), 'gallery_note': base.get('gallery_note'), 'gallery': base.get('gallery', []),
        'steps_h2': f'{short} {base.get("steps_h2", sname + " 진행 순서")}' if base.get('steps_h2') and short not in base.get('steps_h2', '') else base.get('steps_h2'),
        'steps': base.get('steps'), 'cost': dict(base['cost'], h2=f'{short} {base["cost"]["h2"]}') if base.get('cost') else None,
        'check': base.get('check'), 'prep': base.get('prep'), 'subs': base.get('subs'), 'situations': base.get('situations'),
        'redflags': base.get('redflags'), 'rates': base.get('rates'), 'kind': 'regionsvc', 'svc': svc,
    }
    if district:
        p['district'] = district
        p['province'] = prov
    else:
        p['region'] = reg['region']
    p = {k: v for k, v in p.items() if v is not None}
    return p


def main():
    regions = [f.name[:-len('-demolition.json')] for f in CONTENT.glob('*-demolition.json')
               if (load(f.stem).get('district') or load(f.stem).get('region')) and load(f.stem).get('kind') != 'regionsvc']
    regions = sorted(set(regions) | {'gangnam', 'incheon'})
    regions = [r for r in regions if r not in ('seoul', 'gyeonggi')] + ['seoul', 'gyeonggi']
    n = 0
    for r in regions:
        for svc in SERVICES:
            out = CONTENT / f'{r}-{svc}.json'
            if out.exists() and json.loads(out.read_text(encoding='utf-8')).get('handmade'):
                continue
            p = make(r, svc)
            if not p:
                continue
            out.write_text(json.dumps(p, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
            n += 1
    print(f'지역×서비스 페이지 JSON {n}개 생성 (지역 {len(regions)}곳 × 서비스 {len(SERVICES)}개)')


if __name__ == '__main__':
    main()
