"""Checks use an isolated temporary database, never the user's saved data."""
import concurrent.futures
import json
import tempfile
import unittest
from pathlib import Path
import server

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DB = Path(self.tmp.name) / 'test.sqlite3'
        server.initialize()
    def tearDown(self):
        self.tmp.cleanup()
    def create(self, name, semester='26-27上学期', weekday='周一'):
        return server.add_record(dict(name=name,semester=semester,weekday=weekday))
    def test_import_and_restart(self):
        seed=json.loads((server.ROOT/'data/initial.json').read_text())
        with server.connect() as con:
            actual=server.all_records(con)
        self.assertEqual(len(actual),273)
        self.assertEqual(sorted((r['name'],r['semester'],r['weekday'],r['source_row']) for r in seed),sorted((r['name'],r['semester'],r['weekday'],r['source_row']) for r in actual))
        self.assertEqual(self.create('全新测试团')[0],201)
        server.initialize()
        with server.connect() as con:
            self.assertEqual(len(server.all_records(con)),274)
        self.assertEqual(self.create('全新测试团')[0],409)
    def test_normalized_duplicates_and_aliases(self):
        for name in ['彩虹团',' 小 f a n 团 ','小ＦＵＮ团','ｓｈａｒｅ团','T one团','彩\u200b虹团','新别名/小fun团']:
            self.assertEqual(self.create(name)[0],409,name)
        self.assertEqual(self.create('独立甲团/独立乙团')[0],201)
        self.assertEqual(self.create('独立乙团')[0],409)
    def test_validation(self):
        for name in ['', ' ', '/', '新团/', 'a'*101]:
            self.assertEqual(self.create(name)[0],400)
        self.assertEqual(self.create('新团','26-28上学期')[0],400)
        self.assertEqual(self.create('新团',weekday='周八')[0],400)
        self.assertEqual(server.add_record([])[0],400)
    def test_concurrent_duplicate(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(lambda _:self.create('并发测试团')[0],range(2)))
        self.assertEqual(sorted(statuses),[201,409])

if __name__=='__main__':
    unittest.main()
