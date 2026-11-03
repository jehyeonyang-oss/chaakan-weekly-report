"""Read employee workbooks; never depend on Excel's cached formula values."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import math
from pathlib import Path
import re
from urllib.parse import urlparse

from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel

TEAMS = [('content', '콘텐츠기획'), ('marketing', '마케팅'), ('overseas', '해외시딩')]
STAGES = {'소통 중': '②', '협상 중': '③', '협상 완료': '④', '일정 확정': '⑤',
          '방문 일정 확정': '⑤', '촬영 완료': '⑥', '업로드 완료': '⑦', '완료': '✅', '보류': '보류', '취소': '취소'}
GROUPS = ['한국', '일본', '대만·홍콩', '샤오홍슈', '기타']


class InputError(ValueError):
    pass


def string(value):
    return '' if value is None else str(value).strip()


def number(value, label='수치'):
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise InputError(f'{label}: 숫자가 아닙니다.')
    try:
        n = float(str(value).replace(',', '').replace('원', '').strip())
    except (TypeError, ValueError):
        raise InputError(f'{label}: 숫자를 입력해 주세요.')
    if not math.isfinite(n) or n < 0:
        raise InputError(f'{label}: 0 이상의 숫자가 필요합니다.')
    return int(n) if n.is_integer() else n


def day(value, epoch=None, label='날짜'):
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float)) and epoch:
        return day(from_excel(value, epoch))
    try:
        return date.fromisoformat(str(value).strip()[:10]).isoformat()
    except ValueError:
        raise InputError(f'{label}: YYYY-MM-DD 날짜가 필요합니다.')


def url(cell):
    value = cell.hyperlink.target if cell.hyperlink else string(cell.value)
    if value.startswith('=HYPERLINK('):
        found = re.match(r'=HYPERLINK\("([^"]+)"', value, re.I)
        value = found.group(1) if found else ''
    parsed = urlparse(value)
    return value if parsed.scheme in ('http', 'https') and parsed.netloc else ''


def rows(ws, last_col, required_key=1):
    for row in range(6, ws.max_row + 1):
        if ws.row_dimensions[row].hidden:
            continue
        cells = [ws.cell(row, col) for col in range(1, last_col + 1)]
        if not string(cells[required_key - 1].value):
            continue
        yield row, cells


def checked_header(ws, expected):
    for col, prefix in expected.items():
        if not string(ws.cell(5, col).value).startswith(prefix):
            raise InputError(f'{ws.title}: {col}열 머리글을 변경하지 마세요 ({prefix}).')


def read_book(path: Path, team: str, today=None):
    today = today or date.today()
    try:
        wb = load_workbook(path, data_only=False)
    except Exception as exc:
        raise InputError(f'{path.name}: 엑셀을 읽을 수 없습니다 ({type(exc).__name__}).') from exc
    try:
        if '작성안내' not in wb:
            raise InputError(f'{path.name}: 작성안내 탭이 없습니다.')
        g = wb['작성안내']
        declared = string(g['D7'].value)
        if declared and declared != dict(TEAMS)[team]:
            raise InputError(f'{path.name}: 팀명과 저장한 팀 폴더가 다릅니다.')
        asof_value = g['D5'].value
        asof = today.isoformat() if not asof_value or str(asof_value).upper() == '=TODAY()' else day(asof_value, wb.epoch)
        out = {'asof': asof, 'period': string(g['D6'].value), 'people': [], 'ads': [], 'targets': {}}
        if team in dict(TEAMS):
            for required in ['1_섭외진행', '2_업로드성과']:
                if required not in wb:
                    raise InputError(f'{path.name}: {required} 탭이 없습니다.')
            p, s = wb['1_섭외진행'], wb['2_업로드성과']
            checked_header(p, {1: '관리번호', 4: '인플루언서 ID', 11: '원고료'})
            checked_header(s, {1: '관리번호', 9: '업로드일', 10: '게시물 링크', 13: '조회수'})
            progress = {}
            for row, c in rows(p, 19):
                v = [x.value for x in c]
                key = string(v[0])
                if key in progress:
                    raise InputError(f'{path.name}: 관리번호 {key}가 중복입니다.')
                if not string(v[3]):
                    raise InputError(f'{path.name}: 섭외 {row}행의 인플루언서 ID가 없습니다.')
                status = string(v[8])
                if status not in STAGES:
                    raise InputError(f'{path.name}: 섭외 {row}행 진행 단계를 선택해 주세요.')
                kind = string(v[9])
                if kind not in ('유상', '무상'):
                    raise InputError(f'{path.name}: 섭외 {row}행 유·무상을 선택해 주세요.')
                price = number(v[10], f'섭외 {row}행 원고료')
                if kind == '무상' and price not in (None, 0, 1):
                    raise InputError(f'{path.name}: 무상 행의 원고료는 0으로 적어 주세요.')
                group = string(v[7]) or ('샤오홍슈' if string(v[6]) == '샤오홍슈' else string(v[5]))
                if group not in GROUPS:
                    group = '기타'
                progress[key] = {
                    'key': key, 'id': string(v[3]), 'url': url(c[4]), 'who': string(v[1]), 'campaign': string(v[2]),
                    'country': string(v[5]), 'channel': string(v[6]), 'group': group,
                    'status': STAGES[status] + ' ' + status, 'stage': STAGES[status], 'free': kind == '무상',
                    'price': 0 if kind == '무상' else price, 'avg': number(v[11]), 'exp_ss': number(v[12]),
                    'shoot': day(v[13], wb.epoch), 'store': string(v[14]), 'planned_upload': day(v[15], wb.epoch),
                    'upload': None, 'post_url': '', 'measured': None,
                    'views': None, 'likes': None, 'comments': None, 'shares': None, 'saves': None,
                }
                product_cost = number(v[18]) if team!='overseas' else None
                progress[key]['content_cost'] = price + product_cost if price is not None and product_cost is not None else None
            seen = set()
            for row, c in rows(s, 25):
                v = [x.value for x in c]
                key = string(v[0])
                if key not in progress or key in seen:
                    raise InputError(f'{path.name}: 성과 {row}행의 관리번호 연결·중복을 확인해 주세요.')
                seen.add(key)
                values = dict(zip(['views', 'likes', 'comments', 'shares', 'saves'], [number(x) for x in v[12:17]]))
                progress[key].update(upload=day(v[8], wb.epoch), post_url=url(c[9]), measured=day(v[11], wb.epoch), **values)
            out['people'] = list(progress.values())
            for row in range(36, 41):
                group = string(g.cell(row, 2).value)
                value = number(g.cell(row, 4).value)
                if group in GROUPS and value is not None:
                    out['targets'][group] = value
        if team in ('content', 'marketing'):
            if '3_메타광고' not in wb:
                raise InputError(f'{path.name}: 3_메타광고 탭이 없습니다.')
            ws = wb['3_메타광고']
            checked_header(ws, {1: '일자', 2: '채널', 3: '캠페인', 5: '광고비', 12: '광고 귀속매출'})
            for row, c in rows(ws, 13):
                v = [x.value for x in c]
                if not string(v[1]) or not string(v[2]):
                    raise InputError(f'{path.name}: 광고 {row}행의 채널·캠페인을 입력해 주세요.')
                rec = {'date': day(v[0], wb.epoch), 'channel': string(v[1]), 'campaign': string(v[2]), 'objective': string(v[3])}
                rec.update(dict(zip(['spend','creator_cost','product_cost','production_cost','impressions','clicks','purchases','revenue'], [number(x) for x in v[4:12]])))
                rec['key'] = '|'.join([rec['date'], rec['channel'], rec['campaign']])
                out['ads'].append(rec)
        return out
    finally:
        wb.close()


def merge_books(books):
    merged = {'asof': None, 'period': '', 'people': [], 'ads': [], 'targets': {}}
    keyed = {k: {} for k in ['people', 'ads']}
    dates = set()
    periods = set()
    for book in books:
        if any(book[k] for k in keyed):
            dates.add(book['asof'])
            if book['period']:
                periods.add(book['period'])
        for kind in keyed:
            for record in book[kind]:
                key = record['key']
                old = keyed[kind].get(key)
                if old is not None and old != record:
                    raise InputError(f'같은 관리번호·날짜/캠페인의 내용이 서로 다릅니다: {key}')
                keyed[kind][key] = record
        for group, value in book['targets'].items():
            if group in merged['targets'] and merged['targets'][group] != value:
                raise InputError(f'{group} 목표 조회수가 파일마다 다릅니다.')
            merged['targets'][group] = value
    if len(dates) > 1 or len(periods) > 1:
        raise InputError('같은 팀의 보고 기준일·보고 기간을 동일하게 맞춰 주세요.')
    merged['asof'] = next(iter(dates), books[0]['asof'] if books else date.today().isoformat())
    merged['period'] = next(iter(periods), '')
    for kind in keyed:
        merged[kind] = list(keyed[kind].values())
    post_keys = {}
    for r in merged['people']:
        if r['post_url']:
            if r['post_url'] in post_keys:
                raise InputError('같은 게시물 링크가 서로 다른 관리번호에 있습니다. 중복을 정리해 주세요.')
            post_keys[r['post_url']] = r['key']
    return merged


def build(config, today=None):
    result = {'teams': []}
    for slug, name in TEAMS:
        settings = config['sources'][slug]
        primary = Path(settings['primary'])
        if not primary.is_file():
            raise InputError(f'{name}: 기본 엑셀 파일이 없습니다.')
        files = [primary]
        inbox = Path(settings['inbox'])
        if inbox.exists():
            files += sorted(x for x in inbox.glob('*.xlsx') if not x.name.startswith('~$'))
        books = [read_book(f, slug, today) for f in files]
        result['teams'].append({'slug': slug, 'name': name, **merge_books(books)})
    return result
