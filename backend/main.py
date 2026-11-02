"""HackAiThon API — FastAPI + SQLite."""
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

import os

_ENV = Path(__file__).parent / ".env"
try:
    from dotenv import load_dotenv

    load_dotenv(_ENV)
except ImportError:  # python-dotenv not installed: read KEY=VALUE lines ourselves
    if _ENV.exists():
        for _line in _ENV.read_text().splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import ai  # noqa: E402
import db  # noqa: E402


@asynccontextmanager
async def lifespan(app):
    db.init()
    if not db.query("SELECT id FROM memories LIMIT 1"):
        db.add_memory("Ember was just born. Getting to know the user is the first quest.", kind="reflection", source="ember")
    yield


app = FastAPI(title="HackAiThon", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    """Log the traceback and send the real error to the UI instead of a bare 500."""
    traceback.print_exception(type(exc), exc, exc.__traceback__)
    return JSONResponse(status_code=500, content={"detail": f"Backend error in {request.method} {request.url.path}: {type(exc).__name__}: {exc}"})


# ------------------------------------------------------------------ schemas
class ProfileIn(BaseModel):
    name: str = ""
    about: str = ""
    location: str = ""
    interests: str = ""


class MemoryIn(BaseModel):
    text: str
    kind: str = "fact"


class RequestIn(BaseModel):
    kind: Literal["goal", "activity"]
    params: dict


class ProgressIn(BaseModel):
    completed: list[str]


# ------------------------------------------------------------------ basics
@app.get("/api/health")
def health():
    return {"ok": True, "ai_enabled": ai.ai_enabled(), "model": ai.MODEL}


@app.get("/api/soul")
def soul():
    return {"soul": ai.load_soul()}


@app.get("/api/profile")
def get_profile():
    return db.get_profile()


@app.put("/api/profile")
def put_profile(p: ProfileIn):
    prof = db.save_profile(p.name, p.about, p.location, p.interests)
    if p.name:
        db.add_memory(f"The user's name is {p.name}.", kind="fact", source="profile", weight=2)
    if p.location:
        db.add_memory(f"The user is based in {p.location}.", kind="fact", source="profile", weight=2)
    return prof


@app.get("/api/memories")
def list_memories():
    return db.query("SELECT * FROM memories ORDER BY created_at DESC, id DESC")


@app.post("/api/memories")
def add_memory(m: MemoryIn):
    if not m.text.strip():
        raise HTTPException(400, "text required")
    mid = db.add_memory(m.text, kind=m.kind, source="user", weight=1.5)
    return db.one("SELECT * FROM memories WHERE id=?", (mid,))


@app.delete("/api/memories/{mid}")
def delete_memory(mid: int):
    db.execute("DELETE FROM memories WHERE id=?", (mid,))
    return {"ok": True}


# ------------------------------------------------------------------ requests / plans
def run_request(rid: int):
    req = db.one("SELECT * FROM requests WHERE id=?", (rid,))
    kind, params = req["kind"], req["params"]
    mode, note = "live", None
    try:
        db.update("requests", rid, status="running", stage="soul")
        ai.load_soul()
        db.update("requests", rid, stage="memory")
        ctx, used = ai.build_context(kind, params)
        db.update("requests", rid, memories_used=used, stage="research")

        research, sources = "", []
        plans = None
        if ai.ai_enabled():
            try:
                research, sources = ai.research_web(kind, params, ctx)
                db.update("requests", rid, research=research, sources=sources, stage="plans")
                plans = ai.generate_plans(kind, params, ctx, research, sources)
            except Exception as e:  # degrade gracefully so the demo never dead-ends
                traceback.print_exc()
                mode, note = "offline", f"Live AI call failed ({type(e).__name__}: {str(e)[:160]}). Showing template plans."
        else:
            mode, note = "offline", "No ANTHROPIC_API_KEY set. Showing template plans (no live web research)."
        if plans is None:
            plans = ai.offline_plans(kind, params)

        for i, p in enumerate(plans):
            db.insert("plans", request_id=rid, position=i, body=p)
        db.update("requests", rid, status="ready", stage="done", mode=mode, note=note)
    except Exception as e:
        traceback.print_exc()
        db.update("requests", rid, status="failed", error=f"{type(e).__name__}: {e}")


def _request_view(r, with_plans=False):
    r = dict(r)
    if with_plans:
        r["plans"] = [
            {"id": p["id"], "position": p["position"], "chosen": bool(p["chosen"]), **p["body"]}
            for p in db.query("SELECT * FROM plans WHERE request_id=? ORDER BY position", (r["id"],))
        ]
    a = db.one("SELECT id FROM artifacts WHERE request_id=? AND status!='failed' ORDER BY id DESC", (r["id"],))
    r["artifact_id"] = a["id"] if a else None
    return r


@app.post("/api/requests")
def create_request(body: RequestIn, bg: BackgroundTasks):
    p = body.params
    if body.kind == "goal" and not str(p.get("goal", "")).strip():
        raise HTTPException(400, "Tell me what your goal is.")
    if body.kind == "activity" and not str(p.get("recreation", "")).strip():
        raise HTTPException(400, "Tell me what you want to do.")
    rid = db.insert(
        "requests", kind=body.kind, params=p, status="queued", stage="queued",
        mode="live", created_at=time.time(),
    )
    bg.add_task(run_request, rid)
    return _request_view(db.one("SELECT * FROM requests WHERE id=?", (rid,)))


@app.get("/api/requests")
def list_requests():
    return [_request_view(r) for r in db.query("SELECT * FROM requests ORDER BY id DESC")]


@app.get("/api/requests/{rid}")
def get_request(rid: int):
    r = db.one("SELECT * FROM requests WHERE id=?", (rid,))
    if not r:
        raise HTTPException(404, "not found")
    return _request_view(r, with_plans=True)


# ------------------------------------------------------------------ artifacts
def build_artifact(aid: int):
    art = db.one("SELECT * FROM artifacts WHERE id=?", (aid,))
    req = db.one("SELECT * FROM requests WHERE id=?", (art["request_id"],))
    plan = db.one("SELECT * FROM plans WHERE id=?", (art["plan_id"],))["body"]
    kind, params = art["kind"], req["params"]
    try:
        content = None
        if ai.ai_enabled() and req.get("mode") != "offline":
            try:
                ctx, _ = ai.build_context(kind, params)
                content = ai.generate_artifact(kind, params, ctx, plan, req.get("research") or "", req.get("sources") or [])
            except Exception:
                traceback.print_exc()
        if content is None:
            content = ai.offline_artifact(kind, params, plan)
        db.update("artifacts", aid, status="ready", content=content, title=content.get("title", plan.get("title")))
    except Exception as e:
        traceback.print_exc()
        db.update("artifacts", aid, status="failed", error=f"{type(e).__name__}: {e}")


@app.post("/api/plans/{pid}/choose")
def choose_plan(pid: int, bg: BackgroundTasks):
    plan = db.one("SELECT * FROM plans WHERE id=?", (pid,))
    if not plan:
        raise HTTPException(404, "plan not found")
    existing = db.one("SELECT * FROM artifacts WHERE plan_id=? AND status!='failed'", (pid,))
    if existing:
        return existing
    req = db.one("SELECT * FROM requests WHERE id=?", (plan["request_id"],))
    db.execute("UPDATE plans SET chosen=(id=?) WHERE request_id=?", (pid, plan["request_id"]))
    aid = db.insert(
        "artifacts", request_id=req["id"], plan_id=pid, kind=req["kind"],
        title=plan["body"].get("title", "Your plan"), status="building",
        content={}, completed=[], created_at=time.time(),
    )
    db.add_memory(ai.memory_for_choice(req["kind"], req["params"], plan["body"]), kind="event", source="ember")
    bg.add_task(build_artifact, aid)
    return db.one("SELECT * FROM artifacts WHERE id=?", (aid,))


@app.get("/api/artifacts")
def list_artifacts():
    rows = db.query("SELECT * FROM artifacts ORDER BY id DESC")
    out = []
    for r in rows:
        c = r.get("content") or {}
        out.append({
            "id": r["id"], "kind": r["kind"], "title": r["title"], "status": r["status"],
            "xp_earned": r["xp_earned"], "total_xp": c.get("total_xp", 0),
            "done": len(r.get("completed") or []), "items": len(c.get("xp_map", {})),
            "created_at": r["created_at"],
        })
    return out


@app.get("/api/artifacts/{aid}")
def get_artifact(aid: int):
    a = db.one("SELECT * FROM artifacts WHERE id=?", (aid,))
    if not a:
        raise HTTPException(404, "not found")
    a["request"] = db.one("SELECT id, kind, params FROM requests WHERE id=?", (a["request_id"],))
    return a


@app.put("/api/artifacts/{aid}/progress")
def set_progress(aid: int, body: ProgressIn):
    a = db.one("SELECT * FROM artifacts WHERE id=?", (aid,))
    if not a or a["status"] != "ready":
        raise HTTPException(404, "artifact not ready")
    c = a["content"]
    valid = set(c.get("xp_map", {}))
    before = set(a["completed"] or [])
    after = [i for i in dict.fromkeys(body.completed) if i in valid]
    xp = ai.compute_xp(a["kind"], c, after)
    db.update("artifacts", aid, completed=after, xp_earned=xp)
    # remember finished levels / prepared outings
    if a["kind"] == "goal":
        for lvl in c.get("levels", []):
            ids = [q["id"] for q in lvl.get("quests", [])]
            if ids and all(i in after for i in ids) and not all(i in before for i in ids):
                db.add_memory(f"Cleared '{lvl['name']}' in the quest '{a['title']}'.", kind="event", source="ember", weight=1.2)
    elif c.get("checklist") and all(i["id"] in after for i in c["checklist"]) and not all(i["id"] in before for i in c["checklist"]):
        db.add_memory(f"Finished all prep for '{a['title']}'.", kind="event", source="ember")
    return {"completed": after, "xp_earned": xp}


@app.get("/api/stats")
def stats():
    xp = db.one("SELECT COALESCE(SUM(xp_earned),0) AS xp FROM artifacts")["xp"]
    return {
        "xp": xp,
        "level": int((xp / 60) ** 0.5) + 1,
        "goals": db.one("SELECT COUNT(*) AS n FROM artifacts WHERE kind='goal'")["n"],
        "activities": db.one("SELECT COUNT(*) AS n FROM artifacts WHERE kind='activity'")["n"],
        "memories": db.one("SELECT COUNT(*) AS n FROM memories")["n"],
    }


# ------------------------------------------------------------------ static frontend (production build)
DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
