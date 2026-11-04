# 토르철거 사이트 구조와 분류

사이트 전체 분류의 기준은 `content/taxonomy.json` 하나입니다. 페이지의 경로(breadcrumb)와 구조화 데이터(JSON-LD)는 `tools/polish.py`가 이 파일을 읽어 자동으로 만듭니다.

## 분류 (6개)
| 분류 | 페이지 |
|---|---|
| 철거 | /service, /restoration, /interior-demolition |
| 인테리어·건축 시공 | /interior-construction, /building-construction, /remodeling |
| 폐기물·정리 | /waste-transport, /memorial-cleanup, /fire-restoration |
| 지역 | /seoul-demolition, /gyeonggi-demolition, /incheon, /gangnam |
| 정보 | /blog(철거정보), /insight(인사이트), /support(폐업지원금) |
| 회사 | /about, /portfolio, /contact |

블로그 글은 섹션별로 묶습니다: 폐업지원금·정책 / 철거 실무 / 비용·견적.

## 페이지 종류별 구조화 데이터
- 서비스·지역 페이지: Service + BreadcrumbList (지역은 areaServed 포함)
- 목록 페이지(/blog, /insight, /portfolio): CollectionPage + BreadcrumbList
- 글: Article + BreadcrumbList (+ 화면에 보이는 FAQ가 있을 때만 FAQPage)
- 회사/문의: AboutPage, ContactPage
- 전체 공통: GeneralContractor, 홈에는 WebSite

## 작업 순서
1. 새 페이지를 만들면 `content/taxonomy.json`의 `pages`(블로그 글은 `articles`)에 한 줄 추가합니다.
2. `python3 tools/polish.py` 를 실행합니다. 몇 번을 돌려도 결과는 같습니다(두 번째 실행은 "0개 갱신").
3. `python3 tools/audit.py . /tmp/audit.json` 으로 점검합니다.
   - 제목 60자 이하, 설명 70~160자, h1 1개, 이미지 nodim=0, 구조화 데이터 오류 없음.
4. `sitemap.xml`의 lastmod를 바뀐 페이지만 갱신합니다.

## 주의
- 이미지의 width/height는 화면 이동(CLS)을 막기 위한 것입니다. `sizes`가 고정 폭(예: `560px`)이면 그 폭 기준으로 넣습니다. 원본 크기를 그대로 넣으면 글 안의 이미지가 크게 늘어납니다.
- 화면에 보이지 않는 FAQ를 JSON-LD로만 넣지 않습니다(검색엔진 정책 위반).
- "업계 1위", "토르철거가 최저가" 같은 근거 없는 주장은 쓰지 않습니다. 단 "최저가 견적 비교하는 법"처럼 검색어로 쓰는 정보 글은 허용합니다(INSIGHT_GUIDE 참고).
