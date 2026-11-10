"""LeadFlow: zero-paid-API lead intake demo. Local loopback only."""
import argparse, csv, hashlib, json, re, sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LIMIT = 64 * 1024

def clean(value, limit):
    return " ".join(value.split())[:limit] if isinstance(value, str) else ""

class Store:
    def __init__(self, dbpath):
        self.dbpath = str(dbpath)
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS leads (
              id INTEGER PRIMARY KEY, dedup_key TEXT UNIQUE NOT NULL,
              name TEXT NOT NULL, email TEXT NOT NULL,
              source TEXT NOT NULL, company TEXT NOT NULL,
              budget_usd INTEGER NOT NULL, message TEXT NOT NULL,
              priority TEXT NOT NULL, created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS outbox (
              lead_id INTEGER UNIQUE NOT NULL, event TEXT NOT NULL,
              state TEXT NOT NULL DEFAULT 'PENDING'
            );
            """)
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.dbpath, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()
    def add(self, payload):
        if not isinstance(payload, dict):
            return 400, {"error": "Expected JSON object"}
        name = clean(payload.get("name"), 120)
        email = clean(payload.get("email"), 240).lower()
        source = clean(payload.get("source"), 60).lower() or "unknown"
        company = clean(payload.get("company"), 180)
        message = clean(payload.get("message"), 2000)
        budget = payload.get("budget_usd", 0)
        if not name or not EMAIL.fullmatch(email):
            return 400, {"error": "Valid name and email required"}
        if (isinstance(budget, bool) or not isinstance(budget, (int, float))
                or int(budget) != budget or not 0 <= budget <= 10_000_000):
            return 400, {"error": "Invalid budget"}
        budget = int(budget)
        priority = "HIGH" if budget >= 500 or (budget >= 200 and len(message) >= 35) else "NORMAL"
        dedup = hashlib.sha256((email + "\0" + source).encode()).hexdigest()
        try:
            with self.connect() as db:
                result = db.execute(
                    """INSERT INTO leads
                    (dedup_key,name,email,source,company,budget_usd,message,priority,created)
                    VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(dedup_key) DO NOTHING""",
                    (dedup,name,email,source,company,budget,message,priority,
                     datetime.now(timezone.utc).isoformat()))
                fresh = result.rowcount == 1
                if fresh:
                    lead_id = result.lastrowid
                    if priority == "HIGH":
                        db.execute("INSERT INTO outbox(lead_id,event) VALUES(?,?)",
                                   (lead_id,"HIGH_PRIORITY"))
                else:
                    lead_id = db.execute("SELECT id FROM leads WHERE dedup_key=?",
                                         (dedup,)).fetchone()[0]
            return (201 if fresh else 200), {
                "id":lead_id, "status":"created" if fresh else "duplicate",
                "priority":priority if fresh else "unchanged"}
        except sqlite3.Error:
            return 500, {"error": "Database write failed"}
    def health(self):
        with self.connect() as db:
            return {
                "leads":db.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
                "pending":db.execute("SELECT COUNT(*) FROM outbox WHERE state='PENDING'").fetchone()[0]
            }
    def export(self, filename):
        with self.connect() as db, open(filename, "w", newline="", encoding="utf-8") as f:
            w=csv.writer(f)
            w.writerow(["id","name","email","source","company","budget_usd","priority","created"])
            w.writerows(db.execute(
                "SELECT id,name,email,source,company,budget_usd,priority,created FROM leads ORDER BY id"))

def make_handler(store):
    class API(BaseHTTPRequestHandler):
        def respond(self, code, payload):
            body=json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",str(len(body)))
            self.end_headers();self.wfile.write(body)
        def do_GET(self):
            if urlsplit(self.path).path == "/health":
                self.respond(200,{"ok":True,**store.health()})
            else:self.respond(404,{"error":"Not found"})
        def do_POST(self):
            if urlsplit(self.path).path != "/leads":
                return self.respond(404,{"error":"Not found"})
            if self.headers.get_content_type() != "application/json":
                return self.respond(415,{"error":"Use application/json"})
            try: n=int(self.headers.get("Content-Length","0"))
            except ValueError:return self.respond(400,{"error":"Invalid Content-Length"})
            if not 0 < n <= LIMIT:
                return self.respond(413,{"error":"Invalid body length"})
            try: incoming=json.loads(self.rfile.read(n))
            except (ValueError,UnicodeError):
                return self.respond(400,{"error":"Invalid JSON"})
            status,reply=store.add(incoming)
            self.respond(status,reply)
    return API

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",default="leads.db")
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("health")
    sub.add_parser("serve").add_argument("--port",type=int,default=8765)
    sub.add_parser("export").add_argument("filename")
    o=parser.parse_args()
    s=Store(o.db)
    if o.command == "health":print(json.dumps(s.health()))
    elif o.command == "export":s.export(o.filename);print(o.filename)
    else:
        server=ThreadingHTTPServer(("127.0.0.1",o.port),make_handler(s))
        print("LeadFlow listening on local loopback only",flush=True)
        server.serve_forever()

if __name__ == "__main__": main()
