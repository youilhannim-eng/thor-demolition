#!/usr/bin/env python3
"""브라우저(Gemini)에서 받은 dataURL 결과 파일을 images/ai-<name>.jpg 로 저장하고 content/ai_images.json 에 등록.
사용: python3 tools/aiimg.py <tool-result-file> <name> "<alt: ...예시 이미지>"
"""
import base64, io, json, pathlib, re, sys
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parent.parent
src, name, alt = sys.argv[1:4]
assert '예시 이미지' in alt, 'alt에 "예시 이미지" 표기 필요'
t = pathlib.Path(src).read_text(encoding='utf-8')
m = re.search(r'data:image/(?:jpeg|png);base64,([A-Za-z0-9+/=]+)', t)
im = Image.open(io.BytesIO(base64.b64decode(m.group(1)))).convert('RGB')
if im.width > 1600:
    im = im.resize((1600, round(im.height * 1600 / im.width)))
out = ROOT / 'images' / f'ai-{name}.jpg'
im.save(out, quality=84, optimize=True)
reg = ROOT / 'content' / 'ai_images.json'
d = json.loads(reg.read_text(encoding='utf-8')) if reg.exists() else {}
d[f'/images/ai-{name}.jpg'] = alt
reg.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
print(out, im.size)
