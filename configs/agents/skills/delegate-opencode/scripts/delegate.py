#!/usr/bin/env python3
"""Drive OpenCode sessions through the background service REST API.

  run        send a prompt (new session, or --session to follow up), then watch
  watch      re-attach to a running session without prompting
  reject     refuse its pending permission requests with a message, then watch
  interrupt  stop a session
  status     one-shot: running?, pending requests, last progress lines

Watching is foreground and exits as soon as the session needs attention; the
session keeps running unless the status says it was interrupted. Writes
OUT/progress.log, OUT/events.jsonl and OUT/result.md; prints a short summary.
"""
import argparse
import base64
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

EXIT = {"succeeded": 0, "no-start": 3, "blocked": 4, "idle": 5, "timeout": 7}
ANSWER_PREVIEW = 6000


def die(msg, code=2):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def service():
    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    path = os.path.join(state, "opencode", "service.json")
    try:
        with open(path) as f:
            s = json.load(f)
        return s["url"].rstrip("/"), s["password"]
    except (OSError, KeyError, ValueError):
        die(f"cannot read {path}; run `opencode service start`")


class Api:
    def __init__(self, url, password):
        self.url = url
        tok = base64.b64encode(f"opencode:{password}".encode()).decode()
        self.headers = {"Authorization": f"Basic {tok}", "Content-Type": "application/json"}

    def call(self, method, path, body=None, timeout=30):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            die(f"{method} {path} -> HTTP {e.code}: {e.read()[:300].decode(errors='replace')}")
        except OSError as e:
            die(f"{method} {path} failed: {e}; check `opencode service status`")
        return json.loads(raw) if raw else {}

    def try_data(self, path):
        try:
            return self.call("GET", path, timeout=10).get("data") or []
        except SystemExit:
            return []

    def active(self, sid):
        return sid in (self.try_data("/api/session/active") or {})

    def pending(self, sid):
        return self.try_data(f"/api/session/{sid}/permission") + self.try_data(f"/api/session/{sid}/form")


def describe(item):
    what = item.get("resources") or item.get("title") or ""
    return f"{item.get('action', 'form')} {json.dumps(what)[:300]}"


class Run:
    def __init__(self, api, sid, out):
        self.api, self.sid, self.out = api, sid, out
        self.started = False
        self.terminal = None
        self.last_event = time.time()
        self.names = {}
        self.stop = False
        self.lock = threading.Lock()
        self.progress = open(os.path.join(out, "progress.log"), "a", buffering=1)
        self.events = open(os.path.join(out, "events.jsonl"), "a", buffering=1)

    def log(self, msg):
        self.progress.write(f"{time.strftime('%H:%M:%S')} {msg}\n")

    def handle(self, e):
        d = e.get("data") or {}
        if d.get("sessionID") != self.sid:
            return
        t = e["type"]
        with self.lock:
            self.last_event = time.time()
            self.events.write(json.dumps(e) + "\n")
            if t == "session.execution.started":
                self.started = True
                self.log("run started")
            elif t.startswith("session.execution."):
                self.terminal = t.rsplit(".", 1)[1]
                self.log(f"run {self.terminal} {json.dumps(d.get('error') or d.get('reason') or '')[:200]}")
            elif t == "session.tool.input.started":
                self.names[d["id"]] = d.get("name", "tool")
            elif t == "session.tool.called":
                self.log(f"tool {self.names.get(d['id'], '?')} {json.dumps(d.get('input'))[:160]}")
            elif t == "session.tool.success":
                self.log(f"tool done {self.names.get(d['id'], '?')}")
            elif t in ("session.tool.failed", "session.tool.error"):
                self.log(f"tool FAILED {self.names.get(d['id'], '?')} {json.dumps(d.get('error'))[:160]}")
            elif t == "session.text.ended":
                self.log("text: " + str(d.get("text", ""))[:200].replace("\n", " "))
            elif t == "session.step.started":
                self.log("step")
            elif t == "permission.asked":
                self.log(f"BLOCKED permission {d.get('action')} {json.dumps(d.get('resources'))[:160]}")

    def listen(self):
        while not self.stop and self.terminal is None:
            req = urllib.request.Request(self.api.url + "/api/event", headers=self.api.headers)
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    for line in r:
                        if self.stop:
                            return
                        if line.startswith(b"data:"):
                            try:
                                self.handle(json.loads(line[5:]))
                            except ValueError:
                                pass
            except OSError:
                time.sleep(1)


def final_answer(api, sid):
    msgs = api.call("GET", f"/api/session/{sid}/message")["data"]  # newest first
    outcome, texts = None, []
    for m in msgs:
        if m["type"] == "idle" and outcome is None:
            outcome = m.get("outcome")
        elif m["type"] == "user":
            break
        elif m["type"] == "assistant" and not texts:
            texts = [c["text"] for c in m.get("content", []) if c.get("type") == "text"]
    return outcome, "\n".join(texts).strip()


def tail(out, n=8):
    try:
        with open(os.path.join(out, "progress.log")) as f:
            return [line.rstrip()[:220] for line in f.readlines()[-n:]]
    except OSError:
        return []


def watch(api, sid, out, a, prompt=None):
    """Watch until the session ends or needs attention; print the summary and exit."""
    os.makedirs(out, exist_ok=True)
    run = Run(api, sid, out)
    run.log(f"session {sid} ({'prompt' if prompt else 'watch'})")
    threading.Thread(target=run.listen, daemon=True).start()
    time.sleep(0.5)  # let the subscription attach before prompting
    if prompt is not None:
        api.call("POST", f"/api/session/{sid}/prompt", {"text": prompt})
    else:
        run.started = api.active(sid)  # attaching to a running session

    t0 = time.time()
    status, detail, interrupt = None, "", False
    blocked_since, last_poll = None, 0.0
    while status is None and run.terminal is None:
        time.sleep(2)
        now = time.time()
        if not run.started and prompt is None:
            break  # nothing running: report the last answer
        if not run.started and now - t0 > a.startup_timeout:
            status, detail, interrupt = "no-start", f"no execution start within {a.startup_timeout}s", True
        elif now - t0 > a.max_runtime:
            status, detail, interrupt = "timeout", f"watched for {a.max_runtime}s", True
        elif run.started and now - last_poll >= 5:
            last_poll = now
            if not api.active(sid):
                break  # finished; the terminal event may have been missed
            waiting = api.pending(sid)
            if waiting:
                blocked_since = blocked_since or now
                if now - blocked_since >= a.block_grace:
                    status = "blocked"
                    detail = "; ".join(f"[{w.get('id', '?')}] {describe(w)}" for w in waiting)
            else:
                blocked_since = None
            if status is None and not waiting and now - run.last_event >= a.idle:
                status, detail = "idle", f"no events for {int(now - run.last_event)}s; session still running"

    if interrupt:
        api.call("POST", f"/api/session/{sid}/interrupt")
        detail += "; session interrupted"
    if status:
        run.log(f"REPORT {status}: {detail}")
    run.stop = True

    outcome, answer = None, ""
    if status is None:
        outcome, answer = final_answer(api, sid)
        status = outcome or run.terminal or "unknown"
        with open(os.path.join(out, "result.md"), "w") as f:
            f.write(answer + "\n")

    print(f"status: {status}" + (f" ({detail})" if detail else ""))
    print(f"session: {sid}")
    print(f"progress: {out}/progress.log\nevents: {out}/events.jsonl")
    if status in ("idle", "blocked"):
        print("--- last progress ---")
        print("\n".join(tail(out)))
    if answer:
        print(f"result: {out}/result.md\n--- answer ---")
        print(answer[:ANSWER_PREVIEW])
        if len(answer) > ANSWER_PREVIEW:
            print(f"[truncated; {len(answer)} chars in result.md]")
    sys.exit(EXIT.get(status, 6))


def create_session(api, a):
    body = {"title": a.title, "location": {"directory": os.path.abspath(a.dir)}}
    if a.agent:
        body["agent"] = a.agent
    if a.model:
        ref, _, variant = a.model.partition("#")
        prov, _, mid = ref.partition("/")
        if not mid:
            die("--model must look like provider/model#variant")
        body["model"] = {"providerID": prov, "id": mid, **({"variant": variant} if variant else {})}
    if a.rule:
        rules = [r.partition("=") for r in a.rule]
        if any(e not in ("deny", "ask") for _, _, e in rules):
            die("--rule must look like action=deny|ask")
        body["permissions"] = [{"action": x, "resource": "*", "effect": e} for x, _, e in rules]
    return api.call("POST", "/api/session", body)["data"]["id"]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def watched(sp):
        sp.add_argument("--out", required=True, help="output directory (created; appended to on re-watch)")
        sp.add_argument("--idle", type=int, default=120, help="report after this many seconds without events")
        sp.add_argument("--block-grace", type=int, default=20, help="report a pending request after this many seconds")
        sp.add_argument("--startup-timeout", type=int, default=90)
        sp.add_argument("--max-runtime", type=int, default=3600, help="seconds of watching before interrupting")

    r = sub.add_parser("run", help="send a prompt, then watch")
    r.add_argument("--prompt-file", required=True)
    r.add_argument("--session", help="follow up on this session instead of creating one")
    r.add_argument("--dir", default=os.getcwd(), help="working directory for a new session")
    r.add_argument("--model", help="provider/model#variant (new session)")
    r.add_argument("--agent")
    r.add_argument("--title", default="Delegated task")
    r.add_argument("--rule", action="append", default=[], metavar="ACTION=EFFECT", help="new-session rule, e.g. edit=deny")
    watched(r)

    w = sub.add_parser("watch", help="re-attach to a session")
    w.add_argument("--session", required=True)
    watched(w)

    j = sub.add_parser("reject", help="refuse pending permission requests, then watch")
    j.add_argument("--session", required=True)
    j.add_argument("--message", required=True, help="what the agent should do instead")
    watched(j)

    for name in ("interrupt", "status"):
        s = sub.add_parser(name)
        s.add_argument("--session", required=True)
        if name == "status":
            s.add_argument("--out", help="output directory, to show the last progress lines")

    a = p.parse_args()
    api = Api(*service())

    if a.cmd == "run":
        try:
            text = open(a.prompt_file).read()
        except OSError as e:
            die(f"cannot read prompt file: {e}")
        watch(api, a.session or create_session(api, a), a.out, a, prompt=text)
    elif a.cmd == "watch":
        watch(api, a.session, a.out, a)
    elif a.cmd == "reject":
        perms = api.try_data(f"/api/session/{a.session}/permission")
        if not perms:
            die("no pending permission requests; use `watch`")
        for req in perms:
            api.call("POST", f"/api/session/{a.session}/permission/{req['id']}/reply", {"decision": "reject", "message": a.message})
        print(f"rejected {len(perms)} request(s)")
        watch(api, a.session, a.out, a)
    elif a.cmd == "interrupt":
        api.call("POST", f"/api/session/{a.session}/interrupt")
        print(f"interrupted {a.session}")
    else:
        running = api.active(a.session)
        print(f"session: {a.session}\nrunning: {'yes' if running else 'no'}")
        for w in api.pending(a.session):
            print(f"pending: [{w.get('id', '?')}] {describe(w)}")
        if a.out:
            print("--- last progress ---\n" + "\n".join(tail(a.out)))


if __name__ == "__main__":
    main()
