/* 토르철거 공통 스크립트: 모바일 메뉴, 블로그 옛 주소 이동, 게시판 검색, 견적문의 폼(Web3Forms) */
(function () {
  // 아임웹 시절 블로그 글 주소(/blog/?...&idx=번호) → 새 글 주소
  var BLOG_MAP = {"173144014": "/blog/closure-subsidy-schedule", "173143968": "/blog/lease-end-restoration", "173143041": "/blog/restoration-8-steps", "173143019": "/blog/regional-demolition-guide", "173142994": "/blog/closure-subsidy-checklist", "173142755": "/blog/restoration-cost"};
  if (/^\/blog\/?$/.test(location.pathname)) {
    var m = location.search.match(/[?&]idx=(\d+)/);
    if (m && BLOG_MAP[m[1]]) { location.replace(BLOG_MAP[m[1]]); return; }
  }

  // 모바일 메뉴
  var ham = document.querySelector('.thd-ham');
  var drawer = document.getElementById('thd-drawer');
  function setOpen(open) {
    if (!drawer) return;
    drawer.hidden = !open;
    if (ham) ham.setAttribute('aria-expanded', open ? 'true' : 'false');
    document.documentElement.style.overflow = open ? 'hidden' : '';
    document.documentElement.classList.toggle('thd-open', open);
    // 메뉴가 열려 있는 동안 상단 메뉴 전체를 하단 고정 바(전화상담 등)보다 위로 올린다
    document.documentElement.classList.toggle('thd-menu-open', open);
  }
  if (ham) ham.addEventListener('click', function () { setOpen(true); });
  if (drawer) drawer.addEventListener('click', function (e) {
    if (e.target.closest('[data-close]')) setOpen(false);
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') setOpen(false); });

  // 게시판 검색
  var q = document.querySelector('[data-board-search]');
  if (q) q.addEventListener('input', function () {
    var v = q.value.trim().toLowerCase(), shown = 0;
    document.querySelectorAll('.bcard').forEach(function (c) {
      var ok = !v || c.textContent.toLowerCase().indexOf(v) !== -1;
      c.style.display = ok ? '' : 'none'; if (ok) shown++;
    });
    var empty = document.querySelector('.bboard-empty'); if (empty) empty.hidden = shown !== 0;
  });

  // 견적문의 폼
  var form = document.getElementById('tform');
  if (form) {
    var msg = form.querySelector('.tform-msg');
    var tels = form.querySelectorAll('.tform-tel input');
    tels.forEach(function (t, i) {
      t.addEventListener('input', function () {
        t.value = t.value.replace(/\D/g, '');
        if (t.value.length >= t.maxLength && tels[i + 1]) tels[i + 1].focus();
      });
    });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      msg.className = 'tform-msg';
      var name = form.querySelector('[name="성함"]').value.trim();
      var phone = [tels[0].value, tels[1].value, tels[2].value];
      if (!name) { msg.textContent = '성함을 입력해 주세요.'; msg.className = 'tform-msg err'; return; }
      if (phone[0].length < 2 || phone[1].length < 3 || phone[2].length < 4) { msg.textContent = '연락처를 정확히 입력해 주세요.'; msg.className = 'tform-msg err'; return; }
      form.querySelector('[name="연락처"]').value = phone.join('-');
      var key = form.querySelector('[name="access_key"]').value;
      if (!key) {
        // 접수 메일 키가 없을 때: 입력한 내용을 문자 앱에 채워서 열어 준다
        var ta = form.querySelector('[name="문의 내용"]');
        var body = '[토르철거 견적 문의]\n성함: ' + name + '\n연락처: ' + phone.join('-') + (ta && ta.value.trim() ? '\n내용: ' + ta.value.trim() : '') + '\n(현장 사진을 함께 보내 주세요)';
        msg.innerHTML = '문자 앱이 열립니다. 전송 버튼을 눌러 주세요. 열리지 않으면 <a href="tel:01022256775">010-2225-6775</a>로 전화 또는 문자 주세요.';
        window.location.href = 'sms:01022256775?&body=' + encodeURIComponent(body);
        return;
      }
      var btn = form.querySelector('button[type=submit]');
      btn.disabled = true; msg.textContent = '보내는 중입니다…';
      fetch(form.action, { method: 'POST', headers: { Accept: 'application/json' }, body: new FormData(form) })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.success) {
            form.reset();
            msg.textContent = '문의가 접수되었습니다. 확인 후 연락드리겠습니다.';
          } else { throw new Error((d && d.message) || 'fail'); }
        })
        .catch(function () { msg.textContent = '전송에 실패했습니다. 전화(010-2225-6775)로 연락 주세요.'; msg.className = 'tform-msg err'; })
        .then(function () { btn.disabled = false; });
    });
  }
})();

/* 전화·문자·문의 클릭 측정 (GA4) */
(function () {
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || typeof window.gtag !== 'function') return;
    var h = a.getAttribute('href') || '', t = '', n = '';
    if (h.indexOf('tel:') === 0) { t = 'phone_click'; n = h.replace('tel:', ''); }
    else if (h.indexOf('sms:') === 0) { t = 'sms_click'; n = h.replace('sms:', ''); }
    else if (/^\/contact(\?|#|$)/.test(h)) { t = 'quote_click'; n = 'contact'; }
    if (!t) return;
    window.gtag('event', t, { link_url: h, phone_number: n, page_path: location.pathname, event_label: (a.textContent || '').trim().slice(0, 40) });
  }, true);
})();

/* 공종별 현장 사진: 12장 이후 '더 보기' */
(function () {
  var root = document.getElementById('genre-gallery');
  if (!root) return;
  [].forEach.call(root.querySelectorAll('.gal'), function (g) {
    var n = g.children.length;
    if (n <= 12) return;
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'gmore';
    b.textContent = '사진 ' + (n - 12) + '장 더 보기';
    b.addEventListener('click', function () {
      var open = g.classList.toggle('open');
      b.textContent = open ? '접기' : '사진 ' + (n - 12) + '장 더 보기';
      if (!open) g.scrollIntoView({ block: 'start' });
    });
    g.parentNode.insertBefore(b, g.nextSibling);
  });
})();

/* 키워드 랜딩: 상단 메뉴가 지금 보고 있는 구역을 빨간색으로 표시 */
(function () {
  var navs = document.querySelectorAll('.thd-spy');
  if (!navs.length || !('IntersectionObserver' in window)) return;
  var ids = [].map.call(navs[0].querySelectorAll('a[href^="#"]'), function (a) { return a.getAttribute('href').slice(1); });
  var secs = ids.map(function (i) { return document.getElementById(i); }).filter(Boolean);
  function mark(id) {
    [].forEach.call(navs, function (n) {
      [].forEach.call(n.querySelectorAll('a'), function (a) {
        var on = a.getAttribute('href') === '#' + id;
        a.classList.toggle('on', on);
        if (on && n.classList.contains('thd-sub') && n.scrollWidth > n.clientWidth) {
          n.scrollTo({ left: a.offsetLeft - 16, behavior: 'smooth' });
        }
      });
    });
  }
  var cur = null;
  function update() {
    var y = 140, best = null;
    secs.forEach(function (s) { if (s.getBoundingClientRect().top - y <= 0) best = s.id; });
    if (best !== cur) { cur = best; mark(best); }
  }
  window.addEventListener('scroll', update, { passive: true });
  update();
})();
