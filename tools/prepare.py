from copy import copy
from pathlib import Path
import json
import re
import shutil
import urllib.request
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = Path.home() / 'Desktop'
INPUT = DESKTOP / '착한구두 주간보고'
BASE = DESKTOP / 'seeding-hub/research/chaakan_report_template_20261103/착한구두_직원용_주간보고_데이터양식.xlsx'
TEAMS = [('content','콘텐츠기획'),('marketing','마케팅'),('overseas','해외시딩')]
for path in [ROOT/'docs/templates', ROOT/'runtime', INPUT]: path.mkdir(parents=True,exist_ok=True)
config = {'sources': {}}
for slug,name in TEAMS:
    wb = load_workbook(BASE)
    g = wb['작성안내']
    g['B1'] = f'착한구두 · {name} 주간보고'
    g['B2'] = '이 파일을 저장하면 팀별 주간보고에 자동 반영됩니다. 실제 수치만 입력해 주세요.'
    g.merge_cells('B7:C7');g['B7']='팀명';g.merge_cells('D7:E7');g['D7']=name
    g['D5']='=TODAY()'
    g['F5']='기본: 오늘 / 과거 보고는 날짜 직접 입력'
    g['B22']='숨긴 행은 집계에서 제외됩니다. 연락처·주소·계좌 등 개인정보는 적지 마세요.'
    if slug!='overseas':
        p=wb['1_섭외진행'];p['S5']='제품원가(원)';p['S5']._style=copy(p['K5']._style);p.column_dimensions['S'].width=18
        for row in range(6,206):p.cell(row,19)._style=copy(p.cell(row,11)._style)
        g['B17']='원고료·제품원가는 실제 금액을 원 단위로 입력합니다. 비용이 없으면 0, 미확인은 빈칸입니다. 콘텐츠비는 둘 다 확인돼야 계산합니다.'
        g['B10']='2_업로드성과 · 자체 집계할 시딩 성과 입력. 기존 운영 페이지에 있는 게시물은 중복 입력하지 않습니다.'
        g['B11']='3_메타광고 · 광고일별 성과 입력. 기존 운영 페이지에 있는 광고는 중복 입력하지 않습니다.'
        ws=wb.create_sheet('3_메타광고')
        ws.sheet_view.showGridLines=False;ws.freeze_panes='D6';ws.sheet_properties.tabColor='007F78'
        ws.merge_cells('A1:T1');ws['A1']='03 / 메타광고 성과';ws['A1'].font=Font(name='맑은 고딕',size=20,bold=True,color='FFFFFF');ws['A1'].fill=PatternFill('solid',fgColor='17394A');ws.row_dimensions[1].height=40
        ws.merge_cells('A2:T2');ws['A2']='1행 = 일자 × 광고계정·채널 × 캠페인. 일별 실적만 입력하세요. 누적값을 날짜마다 반복 입력하지 않습니다.'
        ws.merge_cells('A3:T3');ws['A3']='인플루언서비·제품원가·제작비는 발생한 날 한 번만 입력. 없는 비용은 0, 미확인은 빈칸. 총비용 ROAS는 비용이 모두 확인된 경우만 계산합니다.'
        ws.merge_cells('A4:T4');ws['A4']='광고 귀속매출은 광고관리자 기준입니다. 시딩 매출과 합산하지 않습니다. 매장 POS 매출을 개별 광고 매출에 넣지 마세요.'
        headers=['일자 *','채널 *','캠페인 *','목적','광고비(원) *','인플루언서비(원)','제품원가(원)','제작비(원)','노출','클릭','구매건수','광고 귀속매출(원)','비고','총비용 · 자동','광고비 ROAS · 자동','총비용 ROAS · 자동','클릭률 · 자동','클릭당 비용 · 자동','구매전환율 · 자동','구매당 비용 · 자동']
        from openpyxl.utils import get_column_letter
        for c,h in enumerate(headers,1):
            ws.cell(5,c,h);ws.cell(5,c).font=Font(name='맑은 고딕',bold=True,color='FFFFFF');ws.cell(5,c).fill=PatternFill('solid',fgColor='007F78');ws.cell(5,c).alignment=Alignment(wrap_text=True,vertical='center');ws.column_dimensions[get_column_letter(c)].width=26 if c in (3,13) else 18
        ws.row_dimensions[5].height=38
        for r in range(6,206):
            for c in range(1,21):
                ws.cell(r,c).fill=PatternFill('solid',fgColor='EAF5FB' if c<=13 else 'F1F3F5');ws.cell(r,c).font=Font(name='맑은 고딕',size=10,color='1466A2' if c<=13 else '233A47');ws.cell(r,c).number_format='#,##0';ws.row_dimensions[r].height=25
            ws.cell(r,1).number_format='yyyy-mm-dd'
            formulas={'N':f'IF(COUNT(E{r}:H{r})=4,SUM(E{r}:H{r}),"")','O':f'IF(AND(ISNUMBER(E{r}),E{r}>0,ISNUMBER(L{r})),L{r}/E{r},"")','P':f'IF(AND(ISNUMBER(N{r}),N{r}>0,ISNUMBER(L{r})),L{r}/N{r},"")','Q':f'IF(AND(ISNUMBER(I{r}),I{r}>0,ISNUMBER(J{r})),J{r}/I{r},"")','R':f'IF(AND(ISNUMBER(E{r}),ISNUMBER(J{r}),J{r}>0),E{r}/J{r},"")','S':f'IF(AND(ISNUMBER(K{r}),ISNUMBER(J{r}),J{r}>0),K{r}/J{r},"")','T':f'IF(AND(ISNUMBER(E{r}),ISNUMBER(K{r}),K{r}>0),E{r}/K{r},"")'}
            for col,formula in formulas.items():ws[f'{col}{r}']='='+formula
            for col in ['O','P','Q','S']:ws[f'{col}{r}'].number_format='0.0%'
        dv=DataValidation(type='decimal',operator='between',formula1=0,formula2=1000000000000,allow_blank=True);dv.showErrorMessage=True;dv.error='0以上の数値'.replace('0以上の数値','0 이상의 숫자만 입력하세요.');ws.add_data_validation(dv);dv.add('E6:L205')
        ws.auto_filter.ref='A5:T205'
    filename=f'{name}_주간보고.xlsx'
    public=ROOT/'docs/templates'/filename
    wb.save(public)
    working=INPUT/filename
    if not working.exists():shutil.copy2(public,working)
    elif slug!='overseas':
        existing=load_workbook(working)
        p=existing['1_섭외진행']
        if p['S5'].value is None:
            p['S5']='제품원가(원)';p['S5']._style=copy(p['K5']._style);p.column_dimensions['S'].width=18
            for row in range(6,206):p.cell(row,19)._style=copy(p.cell(row,11)._style)
            existing.save(working)
    inbox=INPUT/'직원 제출'/name;inbox.mkdir(parents=True,exist_ok=True)
    config['sources'][slug]={'primary':str(working),'inbox':str(inbox)}
    config['sources'][slug]['live'] = slug != 'overseas'
if not (ROOT/'local-config.json').exists():(ROOT/'local-config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')

source='https://seoul-link.github.io/weekly-report-91i90h1e/brands/mplayground-gwangjang.html'
html=urllib.request.urlopen(source,timeout=30).read().decode('utf-8')
css=re.search(r'<style>(.*?)</style>',html,re.S).group(1)
(ROOT/'docs/style.css').write_text(css+'\n'+'''
.team-tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin:18px 0 0}
.team-tabs button{font:inherit;font-weight:800;padding:12px 20px;border:0;border-bottom:3px solid transparent;background:none;color:var(--sub);cursor:pointer}
.team-tabs button[aria-selected=true]{color:var(--accent);border-color:var(--accent)}
.team-tabs button:focus-visible,button:focus-visible,select:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.toolbar{display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px;align-items:center;margin:12px 0}
.actions{display:flex;gap:8px;flex-wrap:wrap}.actions a,.actions button,select{font:inherit;border:1px solid var(--line);border-radius:8px;padding:6px 12px;background:var(--card);color:var(--sub);cursor:pointer}
.section-gap{display:flex;flex-direction:column;gap:16px}.muted{color:var(--mute)}
.source-note{font-size:12px;color:var(--sub);margin:8px 0}.bad{color:var(--wait)}.good{color:var(--ok)}
.ccards-four{grid-template-columns:repeat(4,1fr)}.detail-wrap{max-width:100%;overflow:auto}
@media(max-width:640px){.team-tabs button{padding:11px 14px}.ccards-four{grid-template-columns:1fr 1fr}}
''',encoding='utf-8')
(ROOT/'docs/index.html').write_text('''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="robots" content="noindex,nofollow"><title>착한구두 · 팀별 주간보고</title><link rel="stylesheet" href="style.css"></head>
<body><main class="wrap"><header class="box hd"><div class="eb">착한구두 · 주간보고</div><h1 id="title">콘텐츠기획</h1>
<nav class="team-tabs" role="tablist" aria-label="팀 선택"><button role="tab" id="tab-content" data-team="content" aria-selected="true" aria-controls="team-panel">콘텐츠기획</button><button role="tab" id="tab-marketing" data-team="marketing" aria-selected="false" aria-controls="team-panel">마케팅</button><button role="tab" id="tab-overseas" data-team="overseas" aria-selected="false" aria-controls="team-panel">해외시딩</button></nav>
<div class="toolbar"><div class="date num" id="period">자료를 불러오는 중입니다.</div><div class="actions"><a id="source-link" target="_blank" rel="noopener" hidden>기존 운영 페이지</a><a id="download" download>팀 엑셀 양식</a><button id="refresh" type="button">새로고침</button></div></div>
<div class="notice" id="notice" role="status" hidden></div><div class="kpis num" id="kpis"></div><ul class="summary" id="summary"></ul></header>
<div id="team-panel" role="tabpanel" aria-labelledby="tab-content" class="section-gap"></div>
<footer class="foot" id="foot"></footer></main><script src="app.js"></script></body></html>''',encoding='utf-8')
(ROOT/'docs/.nojekyll').touch()
(INPUT/'사용안내.txt').write_text('''착한구두 팀별 주간보고

탭 순서: 콘텐츠기획 → 마케팅 → 해외시딩
콘텐츠기획: 크리에이터 시딩 먼저, 메타광고 다음
마케팅: 메타광고 먼저, 크리에이터 시딩 다음
해외시딩: 서울링크 원본의 국가별 조회수·업로드 인사이트

팀별 주간보고.xlsx 파일을 수정하고 저장하면 자동 반영됩니다.
직원별 파일은 직원 제출\팀명 폴더에 저장할 수도 있습니다.
같은 관리번호가 서로 다른 내용으로 중복되면 자동 집계를 멈추고 마지막 정상 데이터를 유지합니다.
해당 PC가 켜져 있고 인터넷에 연결돼 있어야 자동 갱신됩니다.
2분마다 변경을 확인하며 GitHub Pages 배포에 추가 시간이 걸릴 수 있습니다.

콘텐츠기획·마케팅 기존 운영 페이지의 데이터와 동일한 게시물·광고는 엑셀에 중복 입력하지 마세요.
엑셀은 해외시딩과 기존 운영 페이지에 없는 추가 실적 제출에 사용합니다.
원고료·광고 귀속매출·광고비를 정확히 구분해서 작성해 주세요.
''',encoding='utf-8')
print(json.dumps({'folder':str(INPUT),'teams':[n for _,n in TEAMS]},ensure_ascii=False))
