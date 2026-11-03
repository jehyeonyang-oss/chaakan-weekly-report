from pathlib import Path
import json
import psutil
import win32com.client
import win32process
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]
files=list((ROOT/'docs/templates').glob('*.xlsx'))+list((Path.home()/'Desktop'/'착한구두 주간보고').glob('*.xlsx'))
before={p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()=='excel.exe'}
app=win32com.client.DispatchEx('Excel.Application');_,pid=win32process.GetWindowThreadProcessId(app.Hwnd)
if pid in before or app.Workbooks.Count:raise RuntimeError('Not an isolated Excel instance')
try:
 app.Visible=False;app.DisplayAlerts=False;app.ScreenUpdating=False;app.EnableEvents=False
 for file in files:
  book=app.Workbooks.Open(str(file),UpdateLinks=0,ReadOnly=False);app.CalculateFullRebuild();book.Save();book.Close(False)
finally:app.Quit()
errors=[];count=0
for file in files:
 cached=load_workbook(file,data_only=True);formula=load_workbook(file,data_only=False)
 for ws in formula:
  for row in ws:
   for c in row:
    if c.data_type=='f':
     count+=1;value=cached[ws.title][c.coordinate]
     if value.data_type=='e':errors.append([file.name,ws.title,c.coordinate,value.value])
assert not errors,errors
print(json.dumps({'workbooks':len(files),'formulas':count,'errors':errors,'isolated_excel_pid':pid},ensure_ascii=False))
