"""A small client for a ServiceNow instance: the Table API, the data dictionary, and run-once server scripts.

Credentials come from .env (SN_INSTANCE, SN_USER, SN_PASSWORD), never from the repository.
"""

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import cache

from shopfloor.vocab import ROOT

TOOL_TAG = "[shopfloor-tool]"


class Instance:
    def __init__(self, name: str, user: str, password: str):
        self.base = f"https://{name}.service-now.com"
        self.name = name
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.headers = {"Accept": "application/json", "Content-Type": "application/json",
                        "Authorization": f"Basic {token}"}

    def call(self, method: str, path: str, body=None, params: dict | None = None, retries: int = 4):
        url = self.base + path + ("?" + urllib.parse.urlencode(params) if params else "")
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(retries):
            req = urllib.request.Request(url, data=data, headers=self.headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    raw = r.read()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                if e.code in (429, 502, 503, 504) and attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                detail = e.read().decode(errors="replace")[:500]
                raise RuntimeError(f"{method} {path}: HTTP {e.code}: {detail}") from e
            except urllib.error.URLError:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise

    # --- Table API ---

    def query(self, table: str, q: str = "", fields: list[str] | None = None, limit: int = 10000) -> list[dict]:
        out, offset = [], 0
        while True:
            params = {"sysparm_query": q, "sysparm_limit": min(1000, limit - len(out)), "sysparm_offset": offset,
                      "sysparm_exclude_reference_link": "true"}
            if fields:
                params["sysparm_fields"] = ",".join(fields)
            page = self.call("GET", f"/api/now/table/{table}", params=params)["result"]
            out += page
            offset += len(page)
            if len(page) < params["sysparm_limit"] or len(out) >= limit:
                return out

    def count(self, table: str, q: str = "") -> int:
        r = self.call("GET", f"/api/now/stats/{table}", params={"sysparm_count": "true", "sysparm_query": q})
        return int(r["result"]["stats"]["count"])

    def insert(self, table: str, record: dict, fields: str = "sys_id") -> dict:
        return self.call("POST", f"/api/now/table/{table}", record, {"sysparm_fields": fields})["result"]

    def insert_many(self, table: str, records: list[dict], workers: int = 16) -> list[dict]:
        with ThreadPoolExecutor(workers) as ex:
            return list(ex.map(lambda r: self.insert(table, r), records))

    def update(self, table: str, sys_id: str, record: dict) -> dict:
        return self.call("PATCH", f"/api/now/table/{table}/{sys_id}", record, {"sysparm_fields": "sys_id"})["result"]

    def delete(self, table: str, sys_id: str) -> None:
        self.call("DELETE", f"/api/now/table/{table}/{sys_id}")

    def delete_where(self, table: str, q: str, workers: int = 16) -> int:
        ids = [r["sys_id"] for r in self.query(table, q, ["sys_id"])]
        with ThreadPoolExecutor(workers) as ex:
            list(ex.map(lambda i: self.delete(table, i), ids))
        return len(ids)

    def order(self, item: str, variables: dict, requested_for: str) -> dict:
        """Order a catalogue item as a person would, through the Service Catalog API. Returns the request item."""
        r = self.call("POST", f"/api/sn_sc/servicecatalog/items/{item}/order_now",
                      {"sysparm_quantity": "1", "sysparm_requested_for": requested_for, "variables": variables})
        req = r["result"]["sys_id"]
        items = self.query("sc_req_item", f"request={req}", ["sys_id", "number", "opened_at", "request"], limit=1)
        if not items:  # the catalogue took the order, but a rule on the request item aborted it
            self.delete("sc_request", req)
            raise RuntimeError(f"order of {item} refused: the platform aborted the request item")
        return items[0]

    # --- Data dictionary ---

    @cache
    def parent(self, table: str) -> str | None:
        r = self.query("sys_db_object", f"name={table}", ["super_class.name"], limit=1)
        return (r[0].get("super_class.name") or None) if r else None

    @cache
    def field_type(self, table: str, field: str) -> str | None:
        """The field's type, looking up through the table hierarchy (e.g. sc_req_item -> task)."""
        t = table
        while t:
            r = self.query("sys_dictionary", f"name={t}^element={field}", ["internal_type"], limit=1)
            if r:
                return r[0]["internal_type"]
            t = self.parent(t)
        return None

    # --- Server scripts, run once by the scheduler ---

    def run_script(self, script: str, timeout: int = 600) -> str:
        """Run a server-side script as a run-once scheduled job and return what it reported.

        The script reports by calling `report(text)`. The job and its log lines are tooling and are tagged.
        """
        marker = uuid.uuid4().hex[:12]
        wrapped = (f"function report(t) {{ gs.info('{TOOL_TAG} {marker} ' + t); }}\n"
                   f"try {{\n{script}\n}} catch (e) {{ report('ERROR ' + e); }}\n"
                   f"report('DONE');")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        job = self.insert("sysauto_script", {"name": f"{TOOL_TAG} {marker}", "run_type": "once",
                                             "run_start": now, "active": "true", "script": wrapped})
        deadline = time.time() + timeout
        lines: list[str] = []
        try:
            while time.time() < deadline:
                rows = self.query("syslog", f"messageSTARTSWITH{TOOL_TAG} {marker}^ORDERBYsys_created_on",
                                  ["message", "sys_created_on"])
                lines = [r["message"].split(marker, 1)[1].strip() for r in rows]
                if "DONE" in lines:
                    break
                time.sleep(3)
            else:
                raise TimeoutError(f"server script {marker} did not finish in {timeout}s")
        finally:
            self.delete("sysauto_script", job["sys_id"])
        errors = [x for x in lines if x.startswith("ERROR")]
        if errors:
            raise RuntimeError(f"server script failed: {errors[0]}")
        return "\n".join(x for x in lines if x != "DONE")


def from_env() -> Instance:
    env = dict(os.environ)
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    return Instance(env["SN_INSTANCE"], env["SN_USER"], env["SN_PASSWORD"])
