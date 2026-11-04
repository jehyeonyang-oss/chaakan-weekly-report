from pathlib import Path
import json
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from datetime import date, datetime
from openpyxl import load_workbook
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from report import read_book, merge_books, InputError
OUT=ROOT/'runtime/check';OUT.mkdir(exist_ok=True,parents=True)
source=ROOT/'docs/templates/해외시딩_주간보고.xlsx'
wb=load_workbook(source);g=wb['작성안내'];g['D5']=datetime(2026,11,3)
p=wb['1_섭외진행'];s=wb['2_업로드성과']
for i,v in enumerate(['qa_001','테스트 담당','FW','test_creator','https://example.org/profile','일본','인스타그램','일본','업로드 완료','유상',300000,100000,750,None,'테스트 매장'],1):p.cell(6,i,v)
for col,value in {'A':'qa_001','I':datetime(2026,10,26),'J':'https://example.org/post','L':datetime(2026,11,2),'M':100000,'N':2000,'O':50,'P':200,'Q':400}.items():s[f'{col}6']=value
fixture=OUT/'fixture.xlsx';wb.save(fixture)
parsed=read_book(fixture,'overseas');r=parsed['people'][0]
assert (r['price'],r['views'],r['shares'],r['saves'],r['upload'])==(300000,100000,200,400,'2026-10-26')
assert len(merge_books([parsed,parsed])['people'])==1
changed=json.loads(json.dumps(parsed));changed['people'][0]['views']=1
try:merge_books([parsed,changed]);raise AssertionError('conflict not detected')
except InputError:pass
# Google Sheet path: values-only grid -> in-memory workbook (contact stage, XHS views estimated from likes).
from report import values_book
from openpyxl.utils.datetime import to_excel
grid=lambda ws:[[to_excel(x) if isinstance(x,datetime) else ('' if x is None else x) for x in row] for row in ws.iter_rows(values_only=True)]
g['D5']=datetime(2026,11,3)
for i,v in enumerate(['qa_002','테스트 담당','FW','xhs_creator','https://example.org/xhs','중국','샤오홍슈','샤오홍슈','업로드 완료','유상',200000,7500,None],1):p.cell(7,i,v)
for i,v in enumerate(['qa_003','테스트 담당','FW','contact_creator','https://example.org/c','일본','인스타그램','일본','컨택','무상',0],1):p.cell(8,i,v)
for col,value in {'A':'qa_002','I':datetime(2026,10,26),'J':'https://example.org/xhs-post','L':datetime(2026,11,2),'N':100}.items():s[f'{col}7']=value
book=read_book(values_book([{'values':grid(wb[n])} for n in ['작성안내','1_섭외진행','2_업로드성과']]),'overseas')
rows={r['key']:r for r in book['people']}
assert book['asof']=='2026-11-03' and rows['qa_001']['upload']=='2026-10-26' and rows['qa_001']['url']=='https://example.org/profile'
assert (rows['qa_002']['views'],rows['qa_002'].get('views_est'),rows['qa_002']['avg'])==(7500,True,7500),rows['qa_002']
assert rows['qa_001'].get('views_est') is None and rows['qa_003']['stage']=='①'
for r in (7,8):
 for col in range(1,20):p.cell(r,col).value=None
for col in range(1,26):s.cell(7,col).value=None
p.row_dimensions[6].hidden=True;wb.save(fixture)
try:read_book(fixture,'overseas');raise AssertionError('hidden progress/orphan performance not detected')
except InputError:pass
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT/'docs')))
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
errors=[]
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True)
 context=browser.new_context(viewport={'width':1440,'height':1000},device_scale_factor=1,color_scheme='light')
 page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
 page.goto(f'http://127.0.0.1:{server.server_port}/',wait_until='networkidle')
 page.wait_for_function("document.querySelectorAll('#kpis .kpi').length===4")
 assert page.locator('[role=tab]').all_text_contents()==['콘텐츠기획','마케팅','해외시딩']
 assert page.locator('#team-panel h2').first.inner_text()=='크리에이터 시딩 진행현황'
 page.locator('tr[data-detail]').first.click();assert page.locator('tr.sub').count()==1
 page.screenshot(path=str(OUT/'content.png'),full_page=True)
 page.locator('#tab-marketing').click();assert page.locator('#team-panel h2').first.inner_text()=='메타광고 성과'
 assert '국가별 조회수' not in page.locator('#team-panel').inner_text()
 marketing=next(t for t in json.loads((ROOT/'docs/data.json').read_text(encoding='utf-8'))['teams'] if t['slug']=='marketing')
 if marketing.get('source_state')=='ok' and marketing['ads']:
  spend=sum(r['spend'] for r in marketing['ads']);revenue=sum(r['revenue'] for r in marketing['ads'])
  assert page.locator('#kpis b').nth(0).inner_text()==f'{spend:,.0f}원'
  assert page.locator('#kpis b').nth(1).inner_text()==f'{revenue:,.0f}원'
  assert page.locator('#notice').is_hidden()
  upload=page.locator('#team-panel > section').last
  upload.locator('tr[data-detail]').first.click()
  assert upload.locator('tr.sub tbody tr').count()==len(marketing['people'])
  page.locator('#window').select_option('7d')
  observed=page.evaluate('(t)=>ReportMath.aggregateUploads(t.people,t,false)',marketing)
  measured=[r['windows']['7d'] for r in marketing['people'] if r.get('windows',{}).get('7d',{}).get('views') is not None and not r['free']]
  assert observed['views']==sum(r['views'] for r in measured)
  page.locator('#window').select_option('latest')
  page.screenshot(path=str(OUT/'marketing-summary.png'))
 page.screenshot(path=str(OUT/'marketing.png'),full_page=True)
 page.locator('#tab-overseas').click();assert '국가별 조회수' in page.locator('#team-panel').inner_text()
 assert '2. 업로드 인사이트' in page.locator('#team-panel').inner_text()
 page.screenshot(path=str(OUT/'overseas.png'),full_page=True)
 math=page.evaluate('''() => {
 const m=ReportMath;
 const r={post_url:'https://example.org',upload:'2026-10-26',measured:'2026-11-02',views:100000,price:300000,exp_ss:750,shares:200,saves:400,free:false};
 const a=m.aggregateUploads([r],{asof:'2026-11-03'},true);
 return {ss:a.ss,cpv:a.cpv,exp:a.expCost,cost:a.ssCost,partial:m.ss({...r,saves:null}),zero:m.ratio(1,0),tooEarly:m.mature({...r,measured:'2026-10-27'},{asof:'2026-11-03'}),missingRevenue:m.adAgg([{spend:10,revenue:20,total_cost:10},{spend:20,revenue:null,total_cost:20}]).revenue};
 }''')
 assert math=={'ss':600,'cpv':3,'exp':400,'cost':500,'partial':None,'zero':None,'tooEarly':False,'missingRevenue':None},math
 mobile=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=1,color_scheme='light')
 p2=mobile.new_page();p2.goto(f'http://127.0.0.1:{server.server_port}/#overseas',wait_until='networkidle')
 assert p2.evaluate('document.documentElement.scrollWidth <= innerWidth+2')
 p2.screenshot(path=str(OUT/'mobile.png'),full_page=True)
 p2.goto(f'http://127.0.0.1:{server.server_port}/#marketing',wait_until='networkidle')
 assert p2.evaluate('document.documentElement.scrollWidth <= innerWidth+2')
 p2.screenshot(path=str(OUT/'marketing-mobile.png'))
 browser.close()
server.shutdown()
assert not errors,errors
(OUT/'results.json').write_text(json.dumps({'passed':True,'page_errors':errors,'formulas':math,'tabs':['콘텐츠기획','마케팅','해외시딩']},ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: workbook parsing, conflicting duplicates, hidden rows, 3 team tabs, stage expansion, aggregation math, mobile width, no browser errors')
