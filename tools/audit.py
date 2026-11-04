"""사이트 SEO 점검 도구. 사용: python3 tools/audit.py . audit.json  (제목·설명 길이, 제목 구조, 이미지 크기, 구조화 데이터 종류를 페이지별로 출력)"""
import re, sys, glob, os, json
from html.parser import HTMLParser

ROOT = sys.argv[1]


class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False
        self.meta = {}
        self.metaprop = {}
        self.canonical = None
        self.h = {"h1": [], "h2": 0, "h3": 0}
        self.cur = None
        self.imgs = []
        self.links = []
        self.ld = []
        self.in_ld = False
        self.ldbuf = ""
        self.text = []
        self.skip = 0
        self.lang = None

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            if a.get("name"):
                self.meta[a["name"]] = a.get("content", "")
            if a.get("property"):
                self.metaprop[a["property"]] = a.get("content", "")
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")
        if tag in ("h1", "h2", "h3"):
            self.cur = tag
            self.buf = ""
        if tag == "img":
            self.imgs.append((a.get("src"), a.get("alt"), a.get("width"), a.get("height"), a.get("loading")))
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "script":
            self.skip += 1
            if a.get("type") == "application/ld+json":
                self.in_ld = True
                self.ldbuf = ""
        if tag == "style":
            self.skip += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in ("h1", "h2", "h3") and self.cur == tag:
            if tag == "h1":
                self.h["h1"].append(self.buf.strip())
            else:
                self.h[tag] += 1
            self.cur = None
        if tag == "script":
            self.skip -= 1
            if self.in_ld:
                self.ld.append(self.ldbuf)
                self.in_ld = False
        if tag == "style":
            self.skip -= 1

    def handle_data(self, d):
        if self.in_title:
            self.title += d
        if self.cur:
            self.buf += d
        if self.in_ld:
            self.ldbuf += d
        if not self.skip:
            self.text.append(d)


rows = []
for f in sorted(glob.glob(ROOT + "/**/*.html", recursive=True)):
    rel = os.path.relpath(f, ROOT)
    s = open(f, encoding="utf-8").read()
    p = P()
    p.feed(s)
    types = []
    for l in p.ld:
        try:
            j = json.loads(l)
            js = j if isinstance(j, list) else [j]
            for x in js:
                if "@graph" in x:
                    types += [g.get("@type") for g in x["@graph"]]
                else:
                    types.append(x.get("@type"))
        except Exception as e:
            types.append("ERR")
    words = len(re.sub(r"\s+", " ", " ".join(p.text)).strip())
    noalt = sum(1 for i in p.imgs if not i[1])
    nodim = sum(1 for i in p.imgs if not (i[2] and i[3]))
    rows.append(dict(f=rel, title=p.title.strip(), tl=len(p.title.strip()), desc=p.meta.get("description", ""),
                     dl=len(p.meta.get("description", "")), canon=p.canonical, h1=p.h["h1"], h2=p.h["h2"], h3=p.h["h3"],
                     imgs=len(p.imgs), noalt=noalt, nodim=nodim, ld=types, og=sorted(p.metaprop.keys()),
                     ogname=[k for k in p.meta if k.startswith("og") or k.startswith("meta-og")],
                     chars=words, links=len(p.links), lang=p.lang, robots=p.meta.get("robots"),
                     viewport="viewport" in p.meta, twitter=[k for k in p.meta if k.startswith("twitter")]))

for r in rows:
    print(f"{r['f']:42} T{r['tl']:3} D{r['dl']:3} h1={len(r['h1'])} h2={r['h2']:2} h3={r['h3']:2} img={r['imgs']:2} noalt={r['noalt']} nodim={r['nodim']} chars={r['chars']:5} ld={r['ld']} og={len(r['og'])} tw={len(r['twitter'])} canon={'Y' if r['canon'] else 'N'}")
json.dump(rows, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
