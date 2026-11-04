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
# Google Sheet path: one tab, one row = one post (sheet_rows gets the raw values grid).
from report import sheet_rows, SHEET_HEAD, TARGET_ROWS
from openpyxl.utils.datetime import to_excel
H=[h+'*' for h in SHEET_HEAD];D=lambda y,m,d:to_excel(datetime(y,m,d))
T=[[g,v] for g,v in zip(TARGET_ROWS,[50000,'',8000,'',''])]
base=['담당A','c_creator','https://example.org/c','일본','인스타그램','컨택','무상']
xhs=['담당B','xhs_creator','https://example.org/x','중국','샤오홍슈','업로드 완료','유상',200000,100,'',D(2026,10,20),'성수점',D(2026,10,26),'https://example.org/xp',D(2026,11,2),100,30,10,'']
tw=['담당C','tw_creator','','대만','인스타그램','협상 완료','유상',100000,'',5000]
sb=sheet_rows([H,base,[],xhs,tw,tw[:5]+['촬영 완료']+tw[6:]],T,today=date(2026,11,3));rows={r['key']:r for r in sb['people']}
assert sb['asof']=='2026-11-03' and sb['targets']=={'한국':50000,'대만·홍콩':8000} and len(sb['people'])==4,sb
c,x=rows['c_creator'],rows['xhs_creator']
assert (c['stage'],c['price'],c['free'],c['group'],c['exp_ss'])==('①',0,True,'일본',None),c
assert (x['views'],x.get('views_est'),x['avg'],x.get('avg_est'),x['group'],x['upload'],x['measured'],x['shoot'],x['post_url'],x['shares'],x['saves'])==(7500,True,7500,True,'샤오홍슈','2026-10-26','2026-11-02','2026-10-20','https://example.org/xp',10,30),x
assert rows['tw_creator']['group']=='대만·홍콩' and rows['tw_creator']['avg']==5000 and rows['tw_creator'].get('avg_est') is None
assert rows['tw_creator_2']['id']=='tw_creator' and rows['tw_creator_2']['stage']=='⑥'
assert len(merge_books([sb])['people'])==4
for bad,msg in [([H,base[:6]+['무상',30000]],'무상'),([H,base[:3]+['']+base[4:]],'2행 필수'),([H[:3]+['x']+H[4:],base],'4열 머리글')]:
 try:sheet_rows(bad,T);raise AssertionError('not rejected: '+msg)
 except InputError as e:assert msg in str(e),(msg,str(e))
try:sheet_rows([H],T[:4]);raise AssertionError('target table move not detected')
except InputError:pass
p.row_dimensions[6].hidden=True;wb.save(fixture)
try:read_book(fixture,'overseas');raise AssertionError('hidden progress/orphan performance not detected')
except InputError:pass
# Sheet failure isolation: overseas keeps last good data + error flag, Excel teams still parse.
from report import build
T=ROOT/'docs/templates'
cfg={'sources':{'content':{'primary':str(T/'콘텐츠기획_주간보고.xlsx'),'inbox':str(OUT/'none')},'marketing':{'primary':str(T/'마케팅_주간보고.xlsx'),'inbox':str(OUT/'none')},
 'overseas':{'sheet':'A'*30,'token':str(OUT/'missing-token.json')}}}
prev={'slug':'overseas','name':'해외시딩','asof':'2026-11-01','period':'P','people':[{'key':'old_1'}],'ads':[],'targets':{}}
built=build(cfg,old={'teams':[prev]});teams={t['slug']:t for t in built['teams']}
assert 'source_state' not in teams['content'] and 'source_state' not in teams['marketing'],teams
o=teams['overseas'];assert o['people']==[{'key':'old_1'}] and o['asof']=='2026-11-01' and o['source_state']=='error' and '시트 읽기 실패' in o['source_message'],o
assert o['sheet_url']=='https://docs.google.com/spreadsheets/d/'+'A'*30+'/edit' and 'overseas' in built['errors']
assert build(cfg)['teams'][2]['people']==[]
sheet_fail=json.loads((ROOT/'docs/data.json').read_text(encoding='utf-8'))
for t in sheet_fail['teams']:
 if t['slug']=='overseas':t.update(source_state='error',source_message=o['source_message'],sheet_url=o['sheet_url'])
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
 page.locator('#tab-marketing').click();assert page.locator('#team-panel h2').first.inner_text()=='크리에이터 시딩 진행현황'
 assert '국가별 조회수' not in page.locator('#team-panel').inner_text()
 marketing=next(t for t in json.loads((ROOT/'docs/data.json').read_text(encoding='utf-8'))['teams'] if t['slug']=='marketing')
 if marketing.get('source_state')=='ok' and marketing['ads']:
  spend=sum(r['spend'] for r in marketing['ads']);revenue=sum(r['revenue'] for r in marketing['ads'])
  assert page.locator('#kpis b').nth(1).inner_text()==f'{spend:,.0f}원'
  assert page.locator('#kpis b').nth(2).inner_text()==f'{revenue:,.0f}원'
  assert page.locator('#notice').is_hidden()
  upload=page.locator('#team-panel > section').filter(has_text='크리에이터 시딩 성과')
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
 assert page.locator('#download').inner_text()==('팀 시트 열기' if next(t for t in json.loads((ROOT/'docs/data.json').read_text(encoding='utf-8'))['teams'] if t['slug']=='overseas').get('sheet_url') else '팀 엑셀 양식')
 page.locator('#tab-content').click();assert page.locator('#download').inner_text()=='팀 엑셀 양식' and page.locator('#download').get_attribute('download') is not None
 failed=browser.new_page();failed.route('**/data.json*',lambda route:route.fulfill(content_type='application/json',body=json.dumps(sheet_fail,ensure_ascii=False)))
 failed.route('**/status.json*',lambda route:route.fulfill(content_type='application/json',body='{"state":"ok","message":""}'))
 failed.goto(f'http://127.0.0.1:{server.server_port}/#overseas',wait_until='networkidle');failed.wait_for_function("document.querySelectorAll('#kpis .kpi').length===4")
 assert '시트 읽기 실패' in failed.locator('#notice').inner_text() and failed.locator('#notice').is_visible()
 d=failed.locator('#download');assert (d.inner_text(),d.get_attribute('href'),d.get_attribute('target'),d.get_attribute('download'))==('팀 시트 열기',o['sheet_url'],'_blank',None)
 failed.screenshot(path=str(OUT/'overseas-sheet-fail.png'));failed.locator('#tab-content').click()
 assert failed.locator('#download').inner_text()=='팀 엑셀 양식' and failed.locator('#notice').inner_text()!=o['source_message']
 failed.close()
 demo=json.loads(json.dumps(sheet_fail));ov=next(t for t in demo['teams'] if t['slug']=='overseas')
 ov.update(source_state='ok',source_message='',people=sb['people'],targets=sb['targets'],asof='2026-11-03',period='')
 pg=browser.new_page();pg.on('pageerror',lambda error:errors.append(str(error)))
 pg.route('**/data.json*',lambda route:route.fulfill(content_type='application/json',body=json.dumps(demo,ensure_ascii=False)))
 pg.route('**/status.json*',lambda route:route.fulfill(content_type='application/json',body='{"state":"ok","message":""}'))
 pg.goto(f'http://127.0.0.1:{server.server_port}/#overseas',wait_until='networkidle');pg.wait_for_function("document.querySelectorAll('#kpis .kpi').length===4")
 k=pg.locator('#kpis .kpi').nth(2).inner_text();assert '12,500' in k and '추정' in k,k
 assert '7,500' in pg.locator('#kpis .kpi').nth(3).inner_text()
 for row in pg.locator('tr[data-detail]').all():row.click()
 body=pg.locator('#team-panel').inner_text();assert not any(w in body for w in ['NaN','undefined','null']),body
 assert 'xhs_creator' in body and '추정' in body
 pg.screenshot(path=str(OUT/'overseas-sheet-rows.png'),full_page=True);pg.close()
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
print('PASS: workbook parsing, one-row sheet parsing + estimate labels, sheet failure isolation + download button, conflicting duplicates, hidden rows, 3 team tabs, stage expansion, aggregation math, mobile width, no browser errors')
