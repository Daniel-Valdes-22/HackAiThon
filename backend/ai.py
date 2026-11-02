"""Ember: soul + memory + web research (RAG) + plan / artifact generation.

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
   "title": "short, memorable name for this path",
   "tagline": "one punchy line",
   "approach": "1-2 sentences: what makes this path different from the others",
   "summary": "3-5 sentences describing the plan concretely",
   "highlights": ["3-5 short bullets"],
   "cost_estimate": "e.g. $150-$300 total",
   "time_commitment": "e.g. 5 hrs/week",
   "timeline": "e.g. 3 months to first milestone",
   "difficulty": "Easy | Moderate | Hard",
   "why_it_fits": "explicitly tie this to the user's profile, memories and answers",
   "tradeoffs": "the honest downside",
   "source_refs": [0, 2]
  }
 ]
}"""


def generate_plans(kind, params, ctx, research_text, sources):
    src = "\n".join(f"[{i}] {s['title']} - {s['url']}" for i, s in enumerate(sources)) or "(none)"
    user = (
        f"{ctx}\n\n# WEB RESEARCH NOTES\n{research_text or '(none)'}\n\n# SOURCES\n{src}\n\n"
        "# TASK\nCraft 3 genuinely different plans (never fewer than 2) for this user. They must differ "
        "in strategy and trade-offs, not just price. Use only facts from the research notes; flag "
        "anything unverified. `source_refs` are indexes into SOURCES that back the plan.\n"
        f"Return ONLY JSON in exactly this shape:\n{PLAN_SHAPE}"
    )
    data = json_call(user, max_tokens=5000)
    plans = [p for p in data.get("plans", []) if isinstance(p, dict) and p.get("title")]
    if len(plans) < 2:
        raise RuntimeError("model returned fewer than 2 plans")
    out = []
    for p in plans[:4]:
        refs = [i for i in p.get("source_refs", []) if isinstance(i, int) and 0 <= i < len(sources)]
        p["sources"] = [sources[i] for i in refs] or sources[:2]
        p.pop("source_refs", None)
        p.setdefault("highlights", [])
        out.append(p)
    return out


# ------------------------------------------------------------------ artifacts
GOAL_SHAPE = """{
 "title": "name of the quest line",
 "hero_class": "fun title for the user, e.g. 'Apprentice Navigator'",
 "intro": "2-3 motivating sentences in Ember's voice",
 "levels": [
  {"name": "Level name", "description": "what this level is about", "boss": "the end-of-level challenge",
   "quests": [
    {"title": "...", "description": "concrete what-to-do", "xp": 20, "est_time": "2 hrs",
     "type": "learn | practice | milestone | boss",
     "resources": [{"title": "...", "url": "https://..."}]}
   ]}
 ],
 "achievements": [{"name": "...", "description": "how to unlock", "icon": "emoji"}],
 "weekly_rhythm": ["e.g. Mon: 30 min drills"],
 "budget_breakdown": [{"label": "...", "cost": "$..."}],
 "tips": ["..."]
}"""

ACTIVITY_SHAPE = """{
 "title": "name of the outing",
 "intro": "2-3 fun sentences in Ember's voice",
 "best_time": "when to go and why",
 "venues": [{"name": "...", "address": "...", "url": "https://...", "price": "...", "why": "..."}],
 "itinerary": [{"time": "10:00", "title": "...", "details": "..."}],
 "budget": [{"label": "...", "cost": "$..."}],
 "budget_total": "$...",
 "before_you_go": ["booking / logistics tasks"],
 "packing": ["items to bring"],
 "safety": ["age limits, waivers, gear, rules"],
 "group_tips": ["tips for this group size"],
 "backup_plan": "what to do if weather/availability fails",
 "side_quests": [{"title": "optional fun challenge", "xp": 25}]
}"""


def generate_artifact(kind, params, ctx, plan, research_text, sources):
    src = "\n".join(f"[{i}] {s['title']} - {s['url']}" for i, s in enumerate(sources)) or "(none)"
    shape = GOAL_SHAPE if kind == "goal" else ACTIVITY_SHAPE
    extra = (
        "Build 4-6 levels, 3-5 quests each, XP scaled 10-100 (bosses bigger), a gentle first level, "
        "and a final boss that proves the goal. Use game language if gamify is YES."
        if kind == "goal"
        else "Build a realistic timeline sized for the group, with budget math for the whole group."
    )
    user = (
        f"{ctx}\n\n# CHOSEN PLAN\n{json.dumps(plan, indent=1)}\n\n# WEB RESEARCH NOTES\n{research_text or '(none)'}\n\n"
        f"# SOURCES\n{src}\n\n# TASK\nBuild the final deliverable for the chosen plan. {extra} "
        "Only use URLs that appear in SOURCES or the research notes; otherwise leave url empty.\n"
        f"Return ONLY JSON in exactly this shape:\n{shape}"
    )
    return finalize_artifact(kind, json_call(user, max_tokens=8000))


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
            items.append({"id": f"p{i}", "text": t, "group": "Pack list", "xp": 5})
        c["checklist"] = items
        for it in items:
            xp_map[it["id"]] = it["xp"]
        for i, s in enumerate(c.get("side_quests", [])):
            s["id"] = f"s{i}"
            s["xp"] = _int(s.get("xp"), 25)
            xp_map[s["id"]] = s["xp"]
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
        lvl = _lab("level", p.get("level"))
        base = [
            ("The Fast Track", "Maximum momentum, minimum dithering.",
             f"Front-load daily practice on {g} with a tight feedback loop and a hard deadline.",
             "10-15 hrs/week", "6-10 weeks to first milestone", "Hard"),
            ("The Steady Climb", "Small daily wins that compound.",
             f"A sustainable weekly rhythm for {g} that fits around real life and avoids burnout.",
             "4-6 hrs/week", "3-4 months to first milestone", "Moderate"),
            ("The Guild Route", "Learn with people who have already done it.",
             f"Join a club, coach, or course for {g} so accountability and expert feedback do the heavy lifting.",
             "5-8 hrs/week", "3 months to first milestone", "Moderate"),
        ]
        return [
            {
                "title": t, "tagline": tag, "approach": appr,
                "summary": f"{appr} Calibrated for a {lvl} starting point and a {_lab('budget', p.get('budget')).lower()} budget.",
                "highlights": ["Clear weekly targets", "Measurable milestones", "Built-in review checkpoints"],
                "cost_estimate": _cost(p), "time_commitment": tm, "timeline": tl, "difficulty": diff,
                "why_it_fits": f"Matches your {_lab('time_investment', p.get('time_investment')).lower()} pace and {lvl.lower()} level.",
                "tradeoffs": "Offline demo mode: no live web research, so verify specific costs and providers yourself.",
                "sources": [],
            }
            for t, tag, appr, tm, tl, diff in base
        ]
    r = p.get("recreation", "an activity")
    n = p.get("group_size", 1)
    base = [
        ("Budget Crew Day", "Max fun per dollar.", f"A no-frills {r} session for {n} using off-peak pricing and group deals.", "$", "Easy"),
        ("The Classic Outing", "The well-trodden favorite.", f"A well-rated local {r} experience with food and downtime built around it for {n}.", "$$", "Easy"),
        ("The VIP Experience", "Go big, make it a story.", f"A premium {r} package for {n} with guides/extras and a celebratory finish.", "$$$", "Moderate"),
    ]
    return [
        {
            "title": t, "tagline": tag, "approach": appr, "summary": appr,
            "highlights": ["Group-friendly", "Clear booking steps", "Weather backup included"],
            "cost_estimate": f"{price} per person", "time_commitment": "Half day to full day",
            "timeline": "Book 1-2 weeks ahead", "difficulty": diff,
            "why_it_fits": f"Within {p.get('distance_miles', 'your')} miles, {_lab('location', p.get('location')).lower()}, for {n} people.",
            "tradeoffs": "Offline demo mode: no live venue search, so verify venues, prices and availability.",
            "sources": [],
        }
        for t, tag, appr, price, diff in base
    ]


def offline_artifact(kind, p, plan):
    if kind == "goal":
        g = p.get("goal", "your goal")
        names = [
            ("Base Camp", "Learn the lay of the land.", [
                ("Define what 'done' looks like", "Write one sentence describing the finish line and a target date.", "learn", 15, "30 min"),
                ("Gather your gear and resources", f"List what you need to start {g}; pick one primary learning resource.", "learn", 20, "1 hr"),
                ("Schedule your first 4 weeks", "Block recurring time on your calendar and tell one person your plan.", "practice", 25, "30 min"),
            ]),
            ("First Blood", "Get your first real reps in.", [
                ("Complete your first practice session", "Do a deliberately easy first session and note what felt hard.", "practice", 30, "1 hr"),
                ("Learn the core fundamentals", f"Work through the core fundamentals of {g}.", "learn", 35, "4 hrs"),
                ("Find a feedback source", "Join a community, find a coach, or share progress weekly with a friend.", "practice", 30, "1 hr"),
            ]),
            ("Rising Challenger", "Stretch beyond comfortable.", [
                ("Hit a 2-week streak", "Show up on schedule 10 times out of 14 days.", "practice", 50, "2 weeks"),
                ("Do a real-world attempt", f"Test your {g} skills in a real situation, however small.", "milestone", 60, "2 hrs"),
                ("Review and adjust", "Look at what's working and re-plan the next month.", "learn", 30, "1 hr"),
            ]),
            ("Boss Fight", "Prove it.", [
                ("Prepare for the final test", f"Do a full dress rehearsal of your {g} milestone.", "practice", 60, "3 hrs"),
                ("Defeat the boss", f"Complete the main milestone of {g}.", "boss", 100, "1 day"),
            ]),
        ]
        c = {
            "title": f"{plan.get('title', 'Your plan')}: {g}",
            "hero_class": "Rising Adventurer",
            "intro": "Offline demo mode: this is a template quest line. Add an ANTHROPIC_API_KEY for a researched, personalized one.",
            "levels": [
                {"name": f"Level {i}: {n}", "description": d, "boss": "Finish every quest to clear the level.",
                 "quests": [{"title": t, "description": desc, "type": ty, "xp": xp, "est_time": et, "resources": []}
                            for t, desc, ty, xp, et in qs]}
                for i, (n, d, qs) in enumerate(names, 1)
            ],
            "achievements": [
                {"name": "First Step", "description": "Complete your first quest.", "icon": "🏁"},
                {"name": "On a Roll", "description": "Clear two levels.", "icon": "🔥"},
                {"name": "Boss Slayer", "description": "Defeat the final boss.", "icon": "🏆"},
            ],
            "weekly_rhythm": ["Mon: plan the week", "Wed: main practice block", "Sat: longer session", "Sun: review"],
            "budget_breakdown": [{"label": "Estimated total", "cost": plan.get("cost_estimate", "varies")}],
            "tips": ["Start smaller than feels necessary.", "Track streaks, not perfection."],
        }
        return finalize_artifact("goal", c)
    r = p.get("recreation", "the activity")
    c = {
        "title": f"{plan.get('title', 'Your outing')}: {r}",
        "intro": "Offline demo mode: template outing. Add an ANTHROPIC_API_KEY for real venues and live prices.",
        "best_time": "Weekday mornings are usually cheapest and quietest.",
        "venues": [],
        "itinerary": [
            {"time": "09:30", "title": "Meet up", "details": "Gather the group and confirm everyone has what they need."},
            {"time": "10:00", "title": f"Start {r}", "details": "Check-in, safety briefing, gear up."},
            {"time": "12:30", "title": "Lunch break", "details": "Refuel and swap highlights."},
            {"time": "14:00", "title": "Second session", "details": "Run it back, now that everyone's warmed up."},
            {"time": "16:00", "title": "Wrap up", "details": "Photos, split costs, plan the rematch."},
        ],
        "budget": [{"label": "Activity (per person)", "cost": plan.get("cost_estimate", "varies")}, {"label": "Food & drinks", "cost": "$15-$30 pp"}],
        "budget_total": "varies",
        "before_you_go": ["Confirm venue hours and availability", "Book for your group size", "Check age/waiver requirements", "Share the plan and meetup point"],
        "packing": ["Water", "Weather-appropriate clothes", "Closed-toe shoes", "Phone charger", "Cash/card"],
        "safety": ["Follow the venue's safety briefing", "Use all required protective gear", "Check minimum age and health restrictions"],
        "group_tips": ["Pick one organizer for bookings", "Agree on a cost split up front"],
        "backup_plan": "If weather or availability fails, move to an indoor alternative nearby.",
        "side_quests": [{"title": "Group photo at the start and end", "xp": 15}, {"title": "Try something nobody has done before", "xp": 30}],
    }
    return finalize_artifact("activity", c)


# ------------------------------------------------------------------ memory note
def memory_for_choice(kind, params, plan):
    if kind == "goal":
        return f"Chose the plan '{plan.get('title')}' for the goal '{params.get('goal')}' ({params.get('level', '?')} level, {params.get('budget', '?')} budget)."
    return f"Chose the plan '{plan.get('title')}' for {params.get('recreation')} with a group of {params.get('group_size', 1)}."
