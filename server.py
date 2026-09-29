#!/usr/bin/env python3
"""Local group archive. Python standard library only."""
import argparse
import hashlib
import json
import re
import sqlite3
import unicodedata
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'data' / 'archive.sqlite3'
ENTRY_ENABLED = False
DAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold()
                   if not c.isspace() and unicodedata.category(c) != 'Cf')

def aliases(name):
    return {normalize(x) for x in re.split(r'[/／]', name) if normalize(x)}

def connect():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    return con

def initialize():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        con.execute('CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, name TEXT NOT NULL, semester TEXT NOT NULL, weekday TEXT NOT NULL, source_row INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        con.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)')
        columns = {r['name'] for r in con.execute('PRAGMA table_info(records)')}
        for name, definition in [('leader', "TEXT NOT NULL DEFAULT ''"), ('is_new', 'INTEGER NOT NULL DEFAULT 0')]:
            if name not in columns:
                con.execute(f'ALTER TABLE records ADD COLUMN {name} {definition}')
        raw = (ROOT / 'data' / 'initial.json').read_bytes()
        version = hashlib.sha256(raw).hexdigest()
        current = con.execute("SELECT value FROM metadata WHERE key='seed_version'").fetchone()
        if not current or current['value'] != version:
            rows = json.loads(raw)
            # Refresh imported history while preserving locally entered records.
            con.execute('DELETE FROM records WHERE source_row IS NOT NULL')
            con.executemany('INSERT INTO records(name,semester,weekday,source_row,leader,is_new) VALUES (:name,:semester,:weekday,:source_row,:leader,:is_new)', rows)
            con.execute("INSERT OR REPLACE INTO metadata VALUES ('seed_version', ?)", (version,))
            con.execute("INSERT OR REPLACE INTO metadata VALUES ('imported', '1')")

def all_records(con):
    return [dict(r) for r in con.execute('SELECT * FROM records ORDER BY semester DESC, id ASC')]

def conflicts(name, rows):
    keys = aliases(name)
    return [r for r in rows if keys & aliases(r['name'])]

def export_xlsx(rows):
    """Generate a real XLSX; inline strings keep user names from becoming formulas."""
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    values = [['小团名称', '学期', '活动时间', '团长名字']] + [[r['name'], r['semester'], r['weekday'], r.get('leader', '')] for r in rows]
    sheet_rows = []
    for index, row in enumerate(values, 1):
        cells = []
        for col, value in zip('ABCD', row):
            clean = ''.join(c for c in str(value) if c in '\t\n\r' or 0x20 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF)
            cells.append(f'<c r="{col}{index}" s="{1 if index == 1 else 0}" t="inlineStr"><is><t xml:space="preserve">{escape(clean)}</t></is></c>')
        sheet_rows.append(f'<row r="{index}" ht="24" customHeight="1">{"".join(cells)}</row>')
    parts = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="小团编年史" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        'xl/styles.xml': f'<styleSheet xmlns="{ns}"><fonts count="2"><font><sz val="12"/><name val="等线"/></font><font><b/><sz val="12"/><color rgb="FFFFFFFF"/><name val="等线"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF2355DC"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
        'xl/worksheets/sheet1.xml': f'<worksheet xmlns="{ns}"><dimension ref="A1:D{len(values)}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="55" customWidth="1"/><col min="2" max="2" width="24" customWidth="1"/><col min="3" max="3" width="16" customWidth="1"/><col min="4" max="4" width="36" customWidth="1"/></cols><sheetData>{"".join(sheet_rows)}</sheetData><autoFilter ref="A1:D{len(values)}"/></worksheet>',
    }
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for path, xml in parts.items():
            archive.writestr(path, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + xml)
    return output.getvalue()

def add_record(payload):
    if not ENTRY_ENABLED:
        return 403, {'error': '新小团录入暂未开放。'}
    if not isinstance(payload, dict):
        return 400, {'error': '录入内容格式不正确。'}
    values = [payload.get(k, '') for k in ('name', 'semester', 'weekday')]
    if not all(isinstance(v, str) for v in values):
        return 400, {'error': '请填写有效的团名、学期和星期。'}
    name, semester, weekday = [v.strip() for v in values]
    if not aliases(name) or len(name) > 100 or any(not normalize(x) for x in re.split(r'[/／]', name)):
        return 400, {'error': '请填写 1–100 字的团名；别名之间用 / 分隔，不能留空。'}
    match = re.fullmatch(r'(\d{2})-(\d{2})(上|下)学期', semester)
    if not match or int(match[2]) != (int(match[1]) + 1) % 100 or weekday not in DAYS:
        return 400, {'error': '请选择有效的连续学年、学期和星期。'}
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        found = conflicts(name, all_records(con))
        if found:
            return 409, {'error': '这个团名已使用，无法重复录入。', 'matches': found}
        cursor = con.execute('INSERT INTO records(name,semester,weekday) VALUES (?,?,?)', (name, semester, weekday))
        record = dict(con.execute('SELECT * FROM records WHERE id=?', (cursor.lastrowid,)).fetchone())
    return 201, {'record': record}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'dist'), **kwargs)

    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/api/export.xlsx':
            try:
                with connect() as con:
                    body = export_xlsx(all_records(con))
            except sqlite3.Error:
                return self.reply(503, {'error': '暂时无法导出，请稍后重试。'})
            filename = '小团编年史-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.xlsx'
            self.send_response(200)
            self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.send_header('Content-Disposition', "attachment; filename=group-archive.xlsx; filename*=UTF-8''" + quote(filename))
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
            return
        if url.path in ('/api/records', '/api/check'):
            with connect() as con:
                rows = all_records(con)
            if url.path == '/api/check':
                name = parse_qs(url.query).get('name', [''])[0]
                return self.reply(200, {'matches': conflicts(name, rows)})
            return self.reply(200, {'records': rows})
        if url.path.startswith('/api/'):
            return self.reply(404, {'error': '找不到这个功能。'})
        return super().do_GET()

    def do_POST(self):
        if self.path != '/api/records':
            return self.reply(404, {'error': '找不到这个功能。'})
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.reply(403, {'error': '请从本地网页提交。'})
        if self.headers.get_content_type() != 'application/json':
            return self.reply(415, {'error': '请使用 JSON 格式提交。'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > 8192:
                return self.reply(400, {'error': '录入内容过长或为空。'})
            payload = json.loads(self.rfile.read(length))
            status, result = add_record(payload)
            return self.reply(status, result)
        except (ValueError, UnicodeDecodeError):
            return self.reply(400, {'error': '录入内容格式不正确。'})
        except sqlite3.Error:
            return self.reply(503, {'error': '暂时无法保存，请稍后重试。'})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--database', type=Path, default=DB)
    args = parser.parse_args()
    DB = args.database
    initialize()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'小团编年史已启动：http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()
