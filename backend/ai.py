"""Frontier: soul + memory + web research (RAG) + plan / artifact generation.

Pipeline:  request -> read soul -> recall memory -> search web -> craft plans
           -> user picks -> build artifact (quest board / activity plan)

If ANTHROPIC_API_KEY is missing (or a call fails) we fall back to deterministic
offline templates so the demo never dead-ends.
"""
import datetime
import json
import os
import re
from pathlib import Path

import db

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
SOUL_PATH = Path(__file__).parent / "soul.md"
_client = None


def ai_enabled():
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def client():
    global _client
    if _client is None:
        from anthropic import Anthropic

        _client = Anthropic(timeout=180.0)
    return _client


def load_soul():
    return SOUL_PATH.read_text(encoding="utf-8")


def system_prompt():
    return f"{load_soul()}\n\n---\nToday's date: {datetime.date.today().isoformat()}"


# ------------------------------------------------------------------ context
LABELS = {
    "duration": {"short": "Short-term (a few weeks to ~3 months)", "long": "Long-term (6+ months, a real journey)"},
    "time_investment": {"casual": "Casual (a few hours a week)", "grind": "Grind (daily, serious commitment)"},
    "budget": {"cheap": "Cheap / frugal", "moderate": "Moderate", "expensive": "Expensive / money is no object"},
    "level": {"beginner": "Beginner", "intermediate": "Intermediate", "pro": "Pro / advanced"},
    "location": {"indoor": "Indoors", "outdoor": "Outdoors", "either": "Either indoor or outdoor"},
}


def _lab(key, val):
    return LABELS.get(key, {}).get(val, val or "unspecified")


def describe_request(kind, p):
    if kind == "goal":
        lines = [
            "TYPE: GOAL (a specific aim the user wants to achieve)",
            f"Goal: {p.get('goal', '')}",
            f"Duration: {_lab('duration', p.get('duration'))}",
            f"Time investment: {_lab('time_investment', p.get('time_investment'))}",
            f"Budget: {_lab('budget', p.get('budget'))}"
            + (f" (about {p['budget_amount']} total)" if p.get("budget_amount") else ""),
            f"Advancement level: {_lab('level', p.get('level'))}",
            f"Gamify it: {'YES - make it feel like a game (levels, quests, XP, boss fights)' if p.get('gamify', True) else 'no'}",
        ]
        if p.get("details"):
            lines.append(f"Extra details: {p['details']}")
        return "\n".join(lines)
    lines = [
        "TYPE: ACTIVITY (a real-world outing or experience to go do)",
        f"Recreation: {p.get('recreation', '')}",
        f"Setting: {_lab('location', p.get('location'))}",
        f"Max distance from user: {p.get('distance_miles', 'any')} miles",
        f"Group size: {p.get('group_size', 1)} people",
    ]
    if p.get("more_info"):
        lines.append(f"More info: {p['more_info']}")
    return "\n".join(lines)


def build_context(kind, params):
    """Retrieve profile + relevant memories and format the shared context block."""
    prof = db.get_profile() or {}
    req_text = describe_request(kind, params)
    mems = db.search_memories(req_text + " " + (prof.get("interests") or ""), k=8)
    prof_txt = "\n".join(
        f"- {k}: {prof.get(k)}" for k in ("name", "about", "location", "interests") if prof.get(k)
    ) or "- (user has not filled in a profile yet)"
    mem_txt = "\n".join(f"- [{m['kind']}] {m['text']}" for m in mems) or "- (no memories yet)"
    ctx = f"# USER PROFILE\n{prof_txt}\n\n# WHAT I REMEMBER (most relevant)\n{mem_txt}\n\n# REQUEST\n{req_text}"
    used = [{"id": m["id"], "kind": m["kind"], "text": m["text"]} for m in mems]
    return ctx, used


# ------------------------------------------------------------------ LLM helpers
def extract_json(text):
    text = re.sub(r"```(?:json)?", "", text).strip()
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[s : e + 1])


def json_call(user, max_tokens=6000):
    last = None
    for _ in range(2):
        resp = client().messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system_prompt(),
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        try:
            return extract_json(text)
        except ValueError as e:  # includes JSONDecodeError
            last = e
            user += "\n\nYour previous reply was not valid JSON. Reply with ONLY the JSON object."
    raise RuntimeError(f"model did not return valid JSON: {last}")


def research_web(kind, params, ctx):
    """Live web search through Claude's server-side web_search tool."""
    prompt = (
        f"{ctx}\n\n# TASK\nResearch the live web so you can build real, specific plans for this "
        "request. "
        + (
            "Find: the best learning paths/programs/courses/communities, realistic costs, typical "
            "timelines, certifications or governing bodies, and well-regarded free resources."
            if kind == "goal"
            else "Find: real venues/operators near the user within the distance limit, current prices, "
            "group packages and minimum ages, hours, booking links, and safety requirements."
        )
        + " Respect the user's budget, level and location. Write concise notes (bullets) with "
        "concrete names, numbers and URLs. Say plainly when you could not verify something."
    )
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}]
    texts, sources = [], {}
    for _ in range(4):
        resp = client().messages.create(
            model=MODEL, max_tokens=3500, system=system_prompt(), tools=tools, messages=messages
        )
        for b in resp.content:
            t = getattr(b, "type", "")
            if t == "text":
                texts.append(b.text)
                for c in getattr(b, "citations", None) or []:
                    url = getattr(c, "url", None)
                    if url:
                        sources.setdefault(url, {"url": url, "title": getattr(c, "title", None) or url})
            elif t == "web_search_tool_result" and isinstance(b.content, list):
                for r in b.content:
                    url = getattr(r, "url", None)
                    if url:
                        sources.setdefault(url, {"url": url, "title": getattr(r, "title", None) or url})
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        break
    return "\n".join(texts).strip(), list(sources.values())[:15]


# ------------------------------------------------------------------ plans
PLAN_SHAPE = """{
 "plans": [
  {
   "title": "2-4 words",
   "tagline": "max 8 words",
   "summary": "ONE sentence, max 25 words",
   "cost_estimate": "short, e.g. $150-300",
   "time_commitment": "short, e.g. 5 hrs/week",
   "difficulty": "Easy | Moderate | Hard",
   "why_it_fits": "max 12 words, tied to this user",
   "source_refs": [0, 2]
  }
 ]
}"""


def generate_plans(kind, params, ctx, research_text, sources):
    src = "\n".join(f"[{i}] {s['title']} - {s['url']}" for i, s in enumerate(sources)) or "(none)"
    user = (
        f"{ctx}\n\n# WEB RESEARCH NOTES\n{research_text or '(none)'}\n\n# SOURCES\n{src}\n\n"
        "# TASK\nCraft 3 genuinely different plans (never fewer than 2) for this user. They must differ "
        "in strategy and trade-offs, not just price. Use only facts from the research notes. "
        "BE EXTREMELY CONCISE: short phrases, obey every word limit, no filler. "
        "`source_refs` are indexes into SOURCES that back the plan.\n"
        f"Return ONLY JSON in exactly this shape:\n{PLAN_SHAPE}"
    )
    data = json_call(user, max_tokens=2500)
    plans = [p for p in data.get("plans", []) if isinstance(p, dict) and p.get("title")]
    if len(plans) < 2:
        raise RuntimeError("model returned fewer than 2 plans")
    out = []
    for p in plans[:3]:
        refs = [i for i in p.get("source_refs", []) if isinstance(i, int) and 0 <= i < len(sources)]
        p["sources"] = [sources[i] for i in refs][:2] or sources[:1]
        p.pop("source_refs", None)
        out.append(p)
    return out


# ------------------------------------------------------------------ artifacts
GOAL_SHAPE = """{
 "title": "max 6 words",
 "intro": "ONE sentence",
 "levels": [
  {"name": "2-3 words",
   "quests": [{"title": "max 8 words", "detail": "max 12 words, concrete", "xp": 20, "url": "optional https link from SOURCES"}]}
 ],
 "achievements": [{"name": "2-3 words", "icon": "emoji"}],
 "budget": [{"label": "...", "cost": "$..."}]
}"""

ACTIVITY_SHAPE = """{
 "title": "max 6 words",
 "intro": "ONE sentence",
 "venues": [{"name": "...", "address": "short", "url": "https://...", "price": "...", "why": "max 10 words"}],
 "itinerary": [{"time": "10:00", "title": "max 6 words"}],
 "budget": [{"label": "...", "cost": "$..."}],
 "budget_total": "$...",
 "before_you_go": ["booking actions, max 4, each max 8 words"],
 "packing": ["max 6 short items"],
 "safety": ["max 3, each max 10 words"]
}"""

NO_HOMEWORK = (
    "The user will NOT do any more research. You must resolve every detail NOW from the research notes "
    "(real names, prices, links, times). Never write steps like research, look up, find out, check, "
    "confirm, decide or choose; name the specific thing instead. If a fact is unknown, leave it out. "
    "BE EXTREMELY CONCISE: short phrases, obey every word limit, no paragraphs, no filler."
)


def generate_artifact(kind, params, ctx, plan, research_text, sources):
    src = "\n".join(f"[{i}] {s['title']} - {s['url']}" for i, s in enumerate(sources)) or "(none)"
    shape = GOAL_SHAPE if kind == "goal" else ACTIVITY_SHAPE
    extra = (
        "3-4 levels, 2-3 quests each, XP 10-100 (final quest biggest), 3 achievements, max 4 budget rows. "
        "Light game language only."
        if kind == "goal"
        else "1-3 venues, 3-6 itinerary steps, budget for the whole group, max 4 budget rows."
    )
    user = (
        f"{ctx}\n\n# CHOSEN PLAN\n{json.dumps(plan)}\n\n# WEB RESEARCH NOTES\n{research_text or '(none)'}\n\n"
        f"# SOURCES\n{src}\n\n# TASK\nBuild the final deliverable for the chosen plan. {extra} {NO_HOMEWORK} "
        "Only use URLs that appear in SOURCES or the research notes; otherwise leave url empty.\n"
        f"Return ONLY JSON in exactly this shape:\n{shape}"
    )
    return finalize_artifact(kind, json_call(user, max_tokens=4000))


def _int(v, d=10):
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return d


def finalize_artifact(kind, c):
    """Assign stable ids and XP maps so progress can be tracked."""
    xp_map = {}
    if kind == "goal":
        for li, lvl in enumerate(c.get("levels", []), 1):
            lvl["id"] = f"L{li}"
            for qi, q in enumerate(lvl.get("quests", []), 1):
                q["id"] = f"L{li}Q{qi}"
                q["xp"] = _int(q.get("xp"), 20)
                xp_map[q["id"]] = q["xp"]
            lvl["bonus_xp"] = 50
        c["achievements"] = c.get("achievements") or []
    else:
        items = []
        for i, t in enumerate(c.get("before_you_go", [])):
            items.append({"id": f"b{i}", "text": t, "group": "Before you go", "xp": 10})
        for i, t in enumerate(c.get("packing", [])):
            items.append({"id": f"p{i}", "text": t, "group": "Pack", "xp": 5})
        c["checklist"] = items
        for it in items:
            xp_map[it["id"]] = it["xp"]
    c["xp_map"] = xp_map
    c["total_xp"] = sum(xp_map.values()) + (
        sum(l.get("bonus_xp", 0) for l in c.get("levels", [])) if kind == "goal" else 0
    )
    return c


def compute_xp(kind, content, completed):
    done = set(completed)
    xp = sum(v for k, v in content.get("xp_map", {}).items() if k in done)
    if kind == "goal":
        for lvl in content.get("levels", []):
            ids = [q["id"] for q in lvl.get("quests", [])]
            if ids and all(i in done for i in ids):
                xp += lvl.get("bonus_xp", 0)
    return xp


# ------------------------------------------------------------------ offline fallback
def _cost(params):
    return {"cheap": "$0-$150", "moderate": "$150-$800", "expensive": "$800+"}.get(params.get("budget"), "varies")


def offline_plans(kind, p):
    if kind == "goal":
        g = p.get("goal", "your goal")
        base = [
            ("Fast Track", "Maximum momentum.", f"Daily focused practice toward {g}, with a hard deadline.", "10-15 hrs/week", "Hard"),
            ("Steady Climb", "Small wins that compound.", f"A sustainable weekly rhythm toward {g}.", "4-6 hrs/week", "Moderate"),
            ("Guild Route", "Learn from people who've done it.", f"A club, coach or course to get you to {g}.", "5-8 hrs/week", "Moderate"),
        ]
        return [
            {"title": t, "tagline": tag, "summary": s, "cost_estimate": _cost(p), "time_commitment": tm,
             "difficulty": d, "why_it_fits": f"Fits your {_lab('level', p.get('level')).lower()} level.", "sources": []}
            for t, tag, s, tm, d in base
        ]
    r = p.get("recreation", "an activity")
    n = p.get("group_size", 1)
    base = [
        ("Budget Crew Day", "Most fun per dollar.", f"Off-peak {r} for {n}, using group deals.", "$"),
        ("Classic Outing", "The local favorite.", f"A well-rated {r} spot for {n}, plus food.", "$$"),
        ("VIP Experience", "Go big.", f"A premium {r} package for {n}.", "$$$"),
    ]
    return [
        {"title": t, "tagline": tag, "summary": s, "cost_estimate": f"{price} per person",
         "time_commitment": "Half day", "difficulty": "Easy",
         "why_it_fits": f"Within {p.get('distance_miles', 'your')} miles, for {n} people.", "sources": []}
        for t, tag, s, price in base
    ]


def offline_artifact(kind, p, plan):
    if kind == "goal":
        g = p.get("goal", "your goal")
        lv = [
            ("Base Camp", [("Pick your main learning resource", "One book, course or coach.", 15),
                           ("Block 4 weekly sessions", "Add them to your calendar.", 20)]),
            ("First Reps", [("Complete your first session", "Keep it easy; just start.", 30),
                            ("Finish the fundamentals", f"Core basics of {g}.", 35),
                            ("Join a community", "Club, forum or study group.", 30)]),
            ("Final Boss", [("Do a full dress rehearsal", f"Simulate the real {g} milestone.", 60),
                            ("Complete the milestone", f"Achieve: {g}.", 100)]),
        ]
        c = {
            "title": f"{plan.get('title', 'Your plan')}",
            "intro": "Offline demo template. Add an API key for a researched plan.",
            "levels": [{"name": n, "quests": [{"title": t, "detail": d, "xp": x} for t, d, x in qs]} for n, qs in lv],
            "achievements": [{"name": "First Step", "icon": "🏁"}, {"name": "On a Roll", "icon": "🔥"}, {"name": "Boss Slayer", "icon": "🏆"}],
            "budget": [{"label": "Estimated total", "cost": plan.get("cost_estimate", "varies")}],
        }
        return finalize_artifact("goal", c)
    r = p.get("recreation", "the activity")
    c = {
        "title": f"{plan.get('title', 'Your outing')}",
        "intro": "Offline demo template. Add an API key for real venues and prices.",
        "venues": [],
        "itinerary": [
            {"time": "10:00", "title": "Arrive and gear up"},
            {"time": "10:30", "title": f"First {r} session"},
            {"time": "12:30", "title": "Lunch"},
            {"time": "14:00", "title": "Second session"},
        ],
        "budget": [{"label": "Activity (per person)", "cost": plan.get("cost_estimate", "varies")}],
        "budget_total": "",
        "before_you_go": ["Book for your group size", "Share the meetup point"],
        "packing": ["Water", "Closed-toe shoes", "Phone charger"],
        "safety": ["Follow the venue's safety briefing", "Wear all required gear"],
    }
    return finalize_artifact("activity", c)


# ------------------------------------------------------------------ memory note
def memory_for_choice(kind, params, plan):
    if kind == "goal":
        return f"Chose the plan '{plan.get('title')}' for the goal '{params.get('goal')}' ({params.get('level', '?')} level, {params.get('budget', '?')} budget)."
    return f"Chose the plan '{plan.get('title')}' for {params.get('recreation')} with a group of {params.get('group_size', 1)}."
