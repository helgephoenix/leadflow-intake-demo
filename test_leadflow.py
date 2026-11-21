import csv, http.client, json, tempfile, threading, unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from leadflow import Store, make_handler
class TestLeadFlow(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/"demo.db")
    def tearDown(self):self.tmp.cleanup()
    def test_duplicate_normalization(self):
        sample={"name":"A","email":"A@EXAMPLE.ORG","source":"Web","budget_usd":600}
        self.assertEqual(self.store.add(sample)[0],201)
        self.assertEqual(self.store.add({**sample,"email":"a@example.org","source":"web"})[0],200)
        self.assertEqual(self.store.health()["leads"],1)
    def test_invalid(self):
        self.assertEqual(self.store.add({"name":"X","email":"bad"})[0],400)
        self.assertEqual(self.store.add({"name":"X","email":"x@example.org","budget_usd":-1})[0],400)
    def test_high_priority(self):
        self.store.add({"name":"X","email":"x@example.org","budget_usd":500})
        self.assertEqual(self.store.health()["pending"],1)
    def test_nonfinite_budgets_rejected(self):
        for bad in (float('nan'), float('inf'), float('-inf'), 1e308, -1e308):
            with self.subTest(value=str(bad)):
                code, result = self.store.add({
                    "name": "Test", "email": "test@example.org", "budget_usd": bad})
                self.assertEqual(code, 400)
                self.assertEqual(result["error"], "Invalid budget")
        self.assertEqual(self.store.health()["leads"], 0)
    def test_csv_neutralizes_spreadsheet_formulas(self):
        code, _ = self.store.add({
            "name": "=HYPERLINK(\"https://example.invalid\")",
            "email": "test@example.org",
            "source": "+web",
            "company": "@SUM(1,2)",
            "budget_usd": 300})
        self.assertEqual(code, 201)
        path = Path(self.tmp.name) / "safe.csv"
        self.store.export(path)
        with path.open(newline="", encoding="utf-8") as fp:
            row = next(csv.DictReader(fp))
        self.assertTrue(row["name"].startswith("'="))
        self.assertEqual(row["source"], "'+web")
        self.assertEqual(row["company"], "'@SUM(1,2)")
        self.assertEqual(row["budget_usd"], "300")
    def test_http_rejects_nan_budget(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            conn.request("POST", "/leads",
                         '{"name":"X","email":"x@example.org","budget_usd":NaN}',
                         {"Content-Type": "application/json"})
            response = conn.getresponse()
            self.assertEqual(response.status, 400)
            self.assertEqual(json.loads(response.read())["error"], "Invalid budget")
            conn.close()
        finally:
            server.shutdown()
            server.server_close()
    def test_csv(self):
        self.store.add({"name":"Y","email":"y@example.org"})
        p=Path(self.tmp.name)/"export.csv"
        self.store.export(p)
        self.assertIn("y@example.org",p.read_text())
    def test_real_http(self):
        server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(self.store))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=3)
            payload=json.dumps({"name":"Z","email":"z@example.org","budget_usd":700})
            conn.request("POST","/leads",payload,{"Content-Type":"application/json"})
            response=conn.getresponse();self.assertEqual(response.status,201);response.read()
            conn.request("GET","/health")
            response=conn.getresponse();self.assertEqual(response.status,200)
            self.assertEqual(json.loads(response.read())["leads"],1)
            conn.close()
        finally:server.shutdown();server.server_close()
if __name__=="__main__":unittest.main()
