// 전 페이지 모바일 점검: 가로 넘침, 깨진 이미지, 대표번호 2개, 너무 작은 글씨, 작은 터치 영역, 화면 밖으로 나간 요소
// 사용법: 저장소 폴더에서 (python3 -m http.server 8765 &) 후 node tools/mobile_qa.js — 문제 있으면 목록 출력
const {chromium,devices}=require('playwright');const fs=require('fs');
const pages=[...fs.readFileSync(require('path').join(__dirname,'..','sitemap.xml'),'utf8').matchAll(/<loc>https:\/\/thorthor\.co\.kr\/([^<]*)<\/loc>/g)].map(m=>m[1]);
(async()=>{const b=await chromium.launch();const bad=[];
for(const dev of [{name:'갤럭시S(360)',ctx:{...devices['Galaxy S9+'],viewport:{width:360,height:740}}},{name:'아이폰13',ctx:devices['iPhone 13']}]){
 const c=await b.newContext(dev.ctx);const p=await c.newPage();
 for(const u of pages){
  const r=await p.goto('http://localhost:8765/'+(u===''?'':u+'.html'),{waitUntil:'load'}).catch(e=>null);
  if(!r||r.status()!==200){bad.push(`${dev.name} /${u} 응답 ${r&&r.status()}`);continue;}
  const o=await p.evaluate(()=>{const W=innerWidth;const res={};
   res.over=document.documentElement.scrollWidth-W;
   res.img=[...document.images].filter(i=>i.complete&&i.naturalWidth===0).map(i=>i.src.split('/').pop()).slice(0,3);
   const t=document.body.innerText;res.phones=t.includes('010-2225-6775')&&t.includes('010-8694-6775');
   res.wide=[...document.querySelectorAll('body *')].filter(e=>{const s=getComputedStyle(e);if(s.position==='fixed'||s.display==='none')return false;const R=e.getBoundingClientRect();return R.width>0&&R.right>W+2&&!e.closest('table')&&!(()=>{for(let a=e.parentElement;a;a=a.parentElement){const x=getComputedStyle(a).overflowX;if(x==='auto'||x==='scroll'||x==='hidden')return true;}return false})()}).map(e=>e.tagName+'.'+(e.className||'').toString().split(' ')[0]).slice(0,3);
   res.tiny=[...document.querySelectorAll('p,li,td,span,a')].filter(e=>e.offsetParent&&e.textContent.trim().length>3&&parseFloat(getComputedStyle(e).fontSize)<12).length;
   res.tap=[...document.querySelectorAll('a[href^="tel:"],a[href^="sms:"],button')].filter(e=>{const R=e.getBoundingClientRect();return e.offsetParent&&R.width>0&&(R.height<32||R.width<32)&&!e.closest('p:not(.ftel),li')}).map(e=>(e.textContent||'').trim().slice(0,10)).slice(0,3);
   res.tel=document.querySelectorAll('a[href^="tel:"]').length;
   return res;});
  const issues=[];
  if(o.over>1)issues.push('가로넘침 '+o.over+'px');
  if(o.img.length)issues.push('깨진이미지 '+o.img.join(','));
  if(!o.phones)issues.push('대표번호 누락');
  if(o.wide.length)issues.push('화면밖 '+o.wide.join(','));
  if(o.tiny>0)issues.push('12px 미만 글씨 '+o.tiny+'개');
  if(o.tap.length)issues.push('작은 버튼 '+o.tap.join('/'));
  if(o.tel<1)issues.push('전화 버튼 없음');
  if(issues.length)bad.push(`${dev.name} /${u}: ${issues.join(' · ')}`);
 }
 await c.close();}
console.log('점검 페이지',pages.length,'x 기기 2');console.log(bad.length?bad.join('\n'):'문제 없음');await b.close();})();
