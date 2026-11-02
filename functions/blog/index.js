// 아임웹 시절 블로그 글 주소(/blog/?...&bmode=view&idx=번호) → 새 글 주소로 301 리디렉션
// 그 밖의 /blog 요청은 그대로 blog.html 을 보여준다.
const OLD_POSTS = {
  "173144014": "/blog/closure-subsidy-schedule",
  "173143968": "/blog/lease-end-restoration",
  "173143041": "/blog/restoration-8-steps",
  "173143019": "/blog/regional-demolition-guide",
  "173142994": "/blog/closure-subsidy-checklist",
  "173142755": "/blog/restoration-cost"
};

export async function onRequest(context) {
  const url = new URL(context.request.url);
  const idx = url.searchParams.get('idx');
  if (idx && OLD_POSTS[idx]) {
    return Response.redirect(new URL(OLD_POSTS[idx], url.origin).toString(), 301);
  }
  return context.next();
}
