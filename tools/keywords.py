#!/usr/bin/env python3
"""서울·경기·인천 지역 키워드 목록 생성 (광고·백링크용).

content/regions.json 의 시·군·구·동 이름과 서비스 키워드를 조합해
keywords/ 폴더에 CSV 로 저장한다. 몇 번 실행해도 결과는 같다.

    python3 tools/keywords.py

출력:
  keywords/keywords_sigungu.csv  시·군·구 단위 (광고 입찰·백링크 앵커)
  keywords/keywords_dong.csv     동 단위 (롱테일, 네이버 플레이스·블로그용)
  keywords/README.txt            사용법
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'keywords'

# (서비스 키워드, 사이트 내 연결 페이지)
SERVICES = [
    ('철거', '/service'),
    ('철거업체', '/service'),
    ('철거 견적', '/service'),
    ('상가 원상복구', '/restoration'),
    ('인테리어 철거', '/interior-demolition'),
    ('폐기물 처리', '/waste-transport'),
    ('화재복구', '/fire-restoration'),
    ('유품정리', '/memorial-cleanup'),
    ('인테리어', '/interior-construction'),
    ('리모델링', '/remodeling'),
]
# 동 단위는 롱테일이 되는 핵심 4개만
DONG_SERVICES = [
    ('철거', '/service'),
    ('원상복구', '/restoration'),
    ('폐기물 처리', '/waste-transport'),
    ('인테리어 철거', '/interior-demolition'),
]
LANDING = {'서울': '/seoul-demolition', '경기': '/gyeonggi-demolition', '인천': '/incheon'}


def units(entry):
    """한 시·군·구 항목에서 (표시 이름 목록, 동 목록)을 돌려준다."""
    c = entry['c']
    names = [c]
    dongs = list(entry.get('d') or [])
    for g in entry.get('g') or []:
        names.append(f'{c} {g["n"]}')
        dongs += g.get('d') or []
    return names, dongs


def main():
    data = json.loads((ROOT / 'content' / 'regions.json').read_text(encoding='utf-8'))
    OUT.mkdir(exist_ok=True)
    sg, dg = [], []
    seen_sg, seen_dg = set(), set()
    for e in data:
        prov = e['p']
        names, dongs = units(e)
        for n in names:
            for svc, page in SERVICES:
                kw = f'{n} {svc}'
                if kw in seen_sg:
                    continue
                seen_sg.add(kw)
                sg.append([prov, n, svc, kw, page, LANDING.get(prov, '')])
        for d in dongs:
            for svc, page in DONG_SERVICES:
                kw = f'{e["c"]} {d} {svc}'
                if kw in seen_dg:
                    continue
                seen_dg.add(kw)
                dg.append([prov, e['c'], d, svc, kw, page])

    with open(OUT / 'keywords_sigungu.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['시도', '시군구', '서비스', '키워드', '연결 페이지', '지역 페이지'])
        w.writerows(sg)
    with open(OUT / 'keywords_dong.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['시도', '시군구', '동', '서비스', '키워드', '연결 페이지'])
        w.writerows(dg)
    (OUT / 'README.txt').write_text(
        '지역 키워드 목록 (python3 tools/keywords.py 로 다시 만들 수 있음)\n'
        f'- keywords_sigungu.csv : {len(sg)}개. 광고 입찰 키워드·백링크 앵커텍스트용.\n'
        f'- keywords_dong.csv    : {len(dg)}개. 동 단위 롱테일. 네이버 플레이스·블로그 제목용.\n'
        '- 행정구역은 content/regions.json(2026년 7월 기준) 을 따른다.\n'
        '- 광고에 쓸 때는 한 번에 전부 넣지 말고 시·군·구 단위부터 올려 성과를 본 뒤 동 단위로 넓힌다.\n'
        '- 한 글·한 페이지에 지역명을 5~10개 넘게 나열하면 스팸으로 판정될 수 있으니 본문에 그대로 붙이지 않는다.\n',
        encoding='utf-8')
    print(f'시군구 키워드 {len(sg)}개, 동 키워드 {len(dg)}개 -> {OUT}')


if __name__ == '__main__':
    main()
