// 대표님 네이버 블로그(yooilhannim)의 최신 글을 RSS로 읽어 JSON으로 돌려준다.
// 제목·날짜·링크만 사용한다(본문은 가져오지 않는다). 1시간 캐시.
const RSS = 'https://rss.blog.naver.com/yooilhannim.xml';

function pick(block, tag) {
  const m = block.match(new RegExp('<' + tag + '[^>]*>([\\s\\S]*?)</' + tag + '>'));
  if (!m) return '';
  return m[1].replace(/^<!\[CDATA\[/, '').replace(/\]\]>$/, '').trim();
}
function decode(s) {
  return s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
}
export function parse(xml, limit = 12) {
  const items = xml.split('<item>').slice(1).map(b => b.split('</item>')[0]);
  return items.slice(0, limit).map(b => {
    const link = decode(pick(b, 'link'));
    const d = new Date(pick(b, 'pubDate'));
    return {
      title: decode(pick(b, 'title')).slice(0, 120),
      link: link.startsWith('https://blog.naver.com/') ? link : '',
      date: isNaN(d) ? '' : new Date(d.getTime() + 9 * 3600e3).toISOString().slice(0, 10),
    };
  }).filter(x => x.title && x.link);
}
export async function onRequest() {
  let posts = [];
  try {
    const r = await fetch(RSS, { cf: { cacheTtl: 3600, cacheEverything: true } });
    if (r.ok) posts = parse(await r.text());
  } catch (e) {}
  return new Response(JSON.stringify({ posts }), {
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'public, max-age=3600' },
  });
}
