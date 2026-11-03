"""Read the exact public content report supplied by the user."""
from datetime import datetime, timezone, timedelta
import json
import re
import urllib.request
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

BASE = 'https://jehyeonyang-oss.github.io/chaakan-creator-guide/edit-status/'


def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'ChaakanWeeklyReport/1.0'}), timeout=30).read().decode('utf-8')


def numeric(x):
    if x is None or isinstance(x, bool):return None
    if isinstance(x,(int,float)):return x
    text=str(x).strip()
    if text in ('','—','-','미확인','협업비 미확인'):return None
    text=text.replace(',','').replace('원','')
    return float(text) if re.fullmatch(r'\d+(?:\.\d+)?',text) else None


def fee(x):
    value=numeric(x)
    if value is not None:return value
    match=re.fullmatch(r'(\d+(?:\.\d+)?)만(?:원)?',str(x).strip())
    return float(match[1])*10000 if match else 0 if str(x).strip()=='무상' else None


def post_key(url):
    p=urlparse(url or '')
    match=re.search(r'/(?:reel|p)/([\w-]+)',p.path)
    return match[1] if p.hostname and p.hostname.endswith('instagram.com') and match else url


def timestamp_day(x):
    if isinstance(x,(float,int)):
        return datetime.fromtimestamp(x/1000,timezone(timedelta(hours=9))).date().isoformat()
    try:return datetime.fromisoformat(str(x).replace('Z','+00:00')).date().isoformat()
    except ValueError:return None


def content_source():
    data=json.loads(fetch(BASE+'data.json'))
    html=BeautifulSoup(fetch(BASE),'html.parser')
    if data.get('schemaVersion') not in (1,2) or not data.get('creators'):
        raise ValueError('콘텐츠기획 원본 데이터 구조 확인 필요')
    embedded=html.find('script',id='content-data')
    if embedded is None:raise ValueError('콘텐츠 성과 원본 누락')
    items=json.loads(embedded.string).get('items',[])
    exact={post_key(x['url']):x for x in items if x.get('mine') and x.get('url')}
    people=[]
    for c in data['creators']:
        item=exact.get(post_key(c.get('postUrl')),{})
        windows=item.get('w',{})
        latest=windows.get('latest') or {}
        cost=numeric(item.get('cost'))
        # The source's verified cost includes contract allocation + product cost.
        price=fee(c.get('fee'))
        status=c.get('status') or c.get('stage') or ''
        if c.get('postUrl') and status=='게시완료':stage='⑦'
        elif any(x in status for x in ['종료','보류','취소']):stage='보류'
        elif any(x in (c.get('stage','')+status) for x in ['초안','검수','피드백']):stage='⑥'
        elif any(x in (c.get('stage','')+status) for x in ['발송','배송','수령']):stage='⑤'
        else:stage='④'
        record_id=parse_qs(urlparse(c.get('recordUrl','')).query).get('id',[f"{c.get('account')}:{c.get('track')}"])[0]
        people.append({'key':'live:'+record_id,'id':c['account'],'name':c.get('name'),'url':f"https://www.instagram.com/{c['account']}/",
            'who':'양제현','campaign':c.get('track') or '미분류','country':'한국','channel':'인스타그램','group':'한국',
            'status':status,'stage':stage,'free':price==0 or str(c.get('fee','')).startswith(('무가','무상')),'price':price,'fee_label':c.get('fee'),'content_cost':cost,'avg':None,'exp_ss':None,
            'shoot':None,'store':'','planned_upload':None,'upload':c.get('postDate') if c.get('postUrl') else None,
            'post_url':c.get('postUrl') or '', 'measured':timestamp_day(latest.get('at')),
            **{k:numeric(latest.get(k)) for k in ['views','likes','comments','shares','saves']},
            'windows':windows,'revenue':numeric((item.get('rev') or {}).get('revenue')),
            'purchases':numeric((item.get('rev') or {}).get('purchases')),'revenue_window':(item.get('rev') or {}).get('window'),
            'source':'live'})
    for c in data.get('contacts',[]):
        people.append({'key':'contact:'+c.get('track','')+':'+c['account'],'id':c['account'],'url':f"https://www.instagram.com/{c['account']}/",
          'who':'양제현','campaign':c.get('track') or '미분류','country':'한국','channel':'인스타그램','group':'한국','status':'컨택 중','stage':'②',
          'free':False,'price':None,'avg':None,'exp_ss':None,'shoot':None,'store':'','upload':None,'post_url':'','measured':None,
          'views':None,'likes':None,'comments':None,'shares':None,'saves':None,'source':'live'})
    ads=[];store_ads=[]
    section=html.find(id='tab-ads')
    if section is None:raise ValueError('메타광고 원본 누락')
    tables=section.find_all('table')
    pa=next((t for t in tables if [x.get_text(' ',strip=True) for x in t.find_all('th')][:2]==['크리에이터 · 제품','상태']),None)
    if pa is None:raise ValueError('크리에이터 PA 광고 표 구조 변경')
    for tr in pa.find_all('tr')[1:]:
        cells=tr.find_all('td')
        if len(cells)!=16:continue
        t=[x.get_text(' ',strip=True) for x in cells]
        spend=numeric(t[3])
        if spend is None:continue
        account=re.search(r'@([\w.]+)',t[0])
        ss=t[8].split('·')
        ads.append({'key':'pa:'+(account[1] if account else t[0]),'campaign':account[1] if account else t[0],
            'label':t[0].replace('게시물 ↗','').strip(),'channel':'크리에이터 PA','period':t[2],'status':t[1],
            'spend':spend,'impressions':numeric(t[4]),'clicks':numeric(t[6]),'shares':numeric(ss[0]),'saves':numeric(ss[1]) if len(ss)>1 else None,
            'content_cost':numeric(t[10]),'total_cost':numeric(t[11]),'purchases':numeric(t[13]),'revenue':numeric(t[14]),
            'source':'live','url':next((a.get('href') for a in cells[0].find_all('a') if 'instagram.com' in a.get('href','')),'')})
    store=next((t for t in tables if [x.get_text(' ',strip=True) for x in t.find_all('th')][:2]==['크리에이터','상태']),None)
    if store:
        for tr in store.find_all('tr')[1:]:
            cells=tr.find_all('td')
            if len(cells)!=15:continue
            t=[x.get_text(' ',strip=True) for x in cells];ss=t[9].split('·')
            store_ads.append({'key':'store:'+t[0],'campaign':t[0],'channel':'매장광고','status':t[1],'period':t[2],
                'spend':numeric(t[4]),'impressions':numeric(t[5]),'clicks':numeric(t[7]),
                'shares':numeric(ss[0]),'saves':numeric(ss[1]) if len(ss)>1 else None,
                'content_cost':numeric(t[11]),'total_cost':numeric(t[12]),'purchases':None,'revenue':None,'source':'live'})
    return {'people':people,'ads':ads,'store_ads':store_ads,'source_url':BASE,'source_at':data['syncedAt'],'source_state':'ok'}


def attach_sources(payload, old=None):
    old=old or {}
    old_teams={t['slug']:t for t in old.get('teams',[])}
    for team in payload['teams']:
        if team['slug']=='content':
            try:
                live=content_source()
                existing={post_key(r['post_url']) for r in team['people'] if r.get('post_url')}
                if any(post_key(r.get('post_url')) in existing for r in live['people'] if r.get('post_url')):
                    raise ValueError('기존 운영 페이지와 엑셀에 같은 게시물이 중복되어 있습니다.')
                team['people'] += live.pop('people');team['ads'] += live.pop('ads');team.update(live)
            except Exception as exc:
                previous=old_teams.get('content',{})
                team['people'] += [r for r in previous.get('people',[]) if r.get('source')=='live']
                team['ads'] += [r for r in previous.get('ads',[]) if r.get('source')=='live']
                team['store_ads']=previous.get('store_ads',[])
                team.update(source_url=BASE,source_at=previous.get('source_at'),source_state='error',source_message='기존 운영 페이지를 불러오지 못해 마지막 정상 데이터를 표시합니다.')
                # Keep diagnostic data local; no full URL parameters or filesystem paths in the published output.
        elif team['slug']=='marketing':
            team.update(source_url='https://chaakan-creator-hub.web.app/',source_state='auth_required',source_message='기존 허브 자동연동은 읽기 권한 연결 대기 중입니다. 현재는 제출된 엑셀 실적만 표시합니다.')
    return payload
