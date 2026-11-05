"""sitemap.xml 의 <lastmod> 를 각 페이지 HTML 파일의 실제 마지막 변경일로 맞춥니다.

- 커밋된 파일: git 마지막 커밋 날짜(Asia/Seoul)
- 아직 커밋 전 변경이 있는 파일: 오늘 날짜
polish.py 마지막에 자동 실행됩니다. 단독 실행: python3 tools/lastmod.py
"""
import re, subprocess, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = 'https://thorthor.co.kr'


def file_for(url):
    path = url[len(SITE):].strip('/')
    for cand in ([ROOT / 'index.html'] if not path else [ROOT / f'{path}.html', ROOT / path / 'index.html']):
        if cand.exists():
            return cand
    return None


def date_of(p):
    rel = str(p.relative_to(ROOT))
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()
    try:
        dirty = subprocess.run(['git', 'status', '--porcelain', '--', rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        if dirty:
            return today
        out = subprocess.run(['git', 'log', '-1', '--format=%cd', '--date=format-local:%Y-%m-%d', '--', rel],
                             cwd=ROOT, capture_output=True, text=True, env={'TZ': 'Asia/Seoul', 'PATH': '/usr/bin:/bin'}).stdout.strip()
        return out or today
    except Exception:
        return today


def main():
    f = ROOT / 'sitemap.xml'
    s = f.read_text(encoding='utf-8')
    n = 0

    def fix(m):
        nonlocal n
        p = file_for(m.group(1))
        if not p:
            return m.group(0)
        d = date_of(p)
        if d != m.group(2):
            n += 1
        return f'<loc>{m.group(1)}</loc><lastmod>{d}</lastmod>'

    s2 = re.sub(r'<loc>([^<]+)</loc><lastmod>([^<]+)</lastmod>', fix, s)
    if s2 != s:
        f.write_text(s2, encoding='utf-8')
    print(f'sitemap lastmod 갱신: {n}건')


if __name__ == '__main__':
    main()
