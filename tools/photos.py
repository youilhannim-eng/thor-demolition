#!/usr/bin/env python3
"""토르철거 현장 사진 정리 도구.

사진을 photos-inbox/ 폴더에 넣고 `python3 tools/photos.py ingest` 를 실행하면
  1. 방향 보정(휴대폰 사진 회전) → 위치정보·촬영기기 정보(EXIF) 제거
  2. 긴 변 1600px 이하로 줄여 /images/<장르>-<해시8자>.jpg 로 저장
     (WebP 사본은 polish.py 가 페이지 빌드 때 자동으로 만든다)
  3. 이미 올린 사진과 거의 같은 사진(연사·재촬영·같은 사진 중복)은 걸러냄
  4. content/photos.json 에 기록 (장르·설명은 비워둠 → 사람이 보고 채움)

그 뒤:
  python3 tools/photos.py todo               # 아직 장르·설명이 없는 사진 목록
  python3 tools/photos.py label <파일> <장르> "<사진 설명>"
  python3 tools/photos.py unused [장르]      # 인사이트 글에 아직 안 쓴 사진
  python3 tools/photos.py check              # 기록 검증

※ 사진 파일의 해시값을 일부러 바꿔서 같은 사진을 다른 사진처럼 올리는 기능은 없습니다.
  (검색엔진이 중복 이미지를 걸러내는 것을 속이는 방식이라 오히려 사이트 신뢰를 깎습니다.)
  이 도구는 반대로 중복을 찾아서 빼 줍니다.
"""
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
INBOX = ROOT / 'photos-inbox'
IMG = ROOT / 'images'
MANIFEST = ROOT / 'content' / 'photos.json'
INSIGHT = ROOT / 'content' / 'insight'
KST = timezone(timedelta(hours=9))

# 장르 → 파일명에 붙는 영문 단어
GENRES = {
    '철거': 'demolition',
    '인테리어': 'interior',
    '건축': 'building',
    '화재복구': 'fire',
    '유품정리': 'cleanup',
    '폐기물': 'waste',
}
MAX_SIDE = 1600
MIN_SIDE = 600          # 이보다 작은 사진은 화질이 낮아 제외
DUP_DISTANCE = 6        # dhash 64비트 중 이 이하로 다르면 같은 사진으로 본다


def load():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding='utf-8'))
    return {'photos': []}


def save(m):
    MANIFEST.parent.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def dhash(im):
    g = im.convert('L').resize((9, 8))
    px = list(g.tobytes())
    bits = 0
    for r in range(8):
        for c in range(8):
            bits = (bits << 1) | (px[r * 9 + c] > px[r * 9 + c + 1])
    return f'{bits:016x}'


def dist(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count('1')


def sharpness(im):
    """가장자리 변화량(클수록 선명). 초점 나간 사진 거르기용."""
    from PIL import ImageFilter, ImageStat
    g = im.convert('L')
    g.thumbnail((800, 800))
    return ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).var[0]


def ingest(inbox=INBOX, manifest_path=None, keep=False):
    from PIL import Image, ImageOps
    if not inbox.exists():
        print(f'{inbox} 폴더가 없습니다.')
        return
    m = load()
    known = [(p['dhash'], p['file']) for p in m['photos']]
    added = dup = small = blur = bad = 0
    files = sorted(f for f in inbox.rglob('*') if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'))
    for f in files:
        try:
            im = Image.open(f)
            im.load()
            im = ImageOps.exif_transpose(im).convert('RGB')
        except Exception as e:
            print(f'  읽기 실패: {f.name} ({e})')
            bad += 1
            continue
        if min(im.size) < MIN_SIDE:
            print(f'  제외(너무 작음 {im.size}): {f.name}')
            small += 1
            continue
        if sharpness(im) < 150:
            print(f'  제외(흐릿함): {f.name}')
            blur += 1
            continue
        h = dhash(im)
        same = next((n for d, n in known if dist(d, h) <= DUP_DISTANCE), None)
        if same:
            print(f'  제외(중복: 기존 {same} 와 거의 같은 사진): {f.name}')
            dup += 1
            continue
        if max(im.size) > MAX_SIDE:
            im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        tmp = IMG / '_tmp_upload.jpg'
        im.save(tmp, 'JPEG', quality=82, optimize=True, progressive=True)      # EXIF 는 넣지 않으므로 위치정보가 사라진다
        sha = hashlib.sha1(tmp.read_bytes()).hexdigest()[:8]
        name = f'photo-{sha}.jpg'                                           # 장르가 정해지면 label 이 이름을 바꾼다
        tmp.replace(IMG / name)
        m['photos'].append({'file': name, 'genre': None, 'alt': None, 'w': im.width, 'h': im.height, 'dhash': h,
                            'added': datetime.now(KST).strftime('%Y-%m-%d')})
        known.append((h, name))
        added += 1
        if not keep:
            f.unlink()
    save(m)
    print(f'완료: 새 사진 {added}장 / 중복 {dup} / 너무 작음 {small} / 흐릿함 {blur} / 읽기 실패 {bad}')
    if added:
        print('다음: python3 tools/photos.py todo  → 사진을 보고 장르·설명 입력')


def find(m, name):
    name = pathlib.Path(name).name
    for p in m['photos']:
        if p['file'] == name:
            return p
    sys.exit(f'기록에 없는 파일: {name}')


def label(name, genre, alt):
    if genre not in GENRES:
        sys.exit(f'장르는 {list(GENRES)} 중 하나')
    if len(alt) < 12:
        sys.exit('사진 설명(alt)은 12자 이상, 사진에 실제로 보이는 것만 적습니다.')
    m = load()
    p = find(m, name)
    old = p['file']
    new = f'{GENRES[genre]}-{old.rsplit("-", 1)[-1]}'        # 예: demolition-3fa9c21b.jpg  (파일명에 장르 포함)
    if old != new and (IMG / old).exists():
        (IMG / old).rename(IMG / new)
        for v in (IMG / 'opt').glob(old.rsplit('.', 1)[0] + '-*.webp'):
            v.unlink()
        p['file'] = new
    p['genre'], p['alt'] = genre, alt
    save(m)
    print(f'{old} → {p["file"]}  [{genre}] {alt}')


def todo():
    m = load()
    t = [p for p in m['photos'] if not p['genre']]
    for p in t:
        print(f'/images/{p["file"]}  {p["w"]}x{p["h"]}')
    print(f'미분류 {len(t)}장')


def used_images():
    used = set()
    for f in INSIGHT.glob('*.json'):
        used.add(json.loads(f.read_text(encoding='utf-8')).get('image'))
    return used


def unused(genre=None):
    m = load()
    used = used_images()
    for p in m['photos']:
        if p['genre'] and (not genre or p['genre'] == genre) and f'/images/{p["file"]}' not in used:
            print(f'/images/{p["file"]}  [{p["genre"]}] {p["alt"]}')


def check():
    m = load()
    err = []
    names = set()
    for p in m['photos']:
        if p['file'] in names:
            err.append(f'중복 기록: {p["file"]}')
        names.add(p['file'])
        if not (IMG / p['file']).exists():
            err.append(f'파일 없음: {p["file"]}')
        if p['genre'] and p['genre'] not in GENRES:
            err.append(f'장르 오류: {p["file"]}')
        if p['genre'] and not p['alt']:
            err.append(f'설명 없음: {p["file"]}')
    for e in err:
        print(' -', e)
    print('이상 없음' if not err else f'문제 {len(err)}건', f'/ 사진 {len(m["photos"])}장')
    return not err


def photo_alts():
    """insight.py 가 쓰는 {경로: 설명} — 장르·설명이 채워진 사진만."""
    return {f'/images/{p["file"]}': p['alt'] for p in load()['photos'] if p.get('genre') and p.get('alt')}


if __name__ == '__main__':
    a = sys.argv[1:]
    cmd = a[0] if a else ''
    if cmd == 'ingest':
        ingest(keep='--keep' in a)
    elif cmd == 'todo':
        todo()
    elif cmd == 'label' and len(a) == 4:
        label(a[1], a[2], a[3])
    elif cmd == 'unused':
        unused(a[1] if len(a) > 1 else None)
    elif cmd == 'check':
        sys.exit(0 if check() else 1)
    else:
        print(__doc__)
