#!/usr/bin/env python3
"""
End-to-end API test — runs against the live local Flask app + DBs.

Uses Flask test client with auth monkeypatched to inject the real
PredUser (foxyclaw) already in the DB, so all business logic runs for real.

Usage:
    cd hockey-blast-predictions
    source .venv/bin/activate
    python scripts/e2e_test.py
"""

import os
import sys

# Ensure we're running from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("FLASK_ENV", "development")

from unittest.mock import patch

from flask import g
from sqlalchemy import select

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

PASS = "✅"
FAIL = "❌"
results = []

def check(label: str, condition: bool, detail: str = ""):
    icon = PASS if condition else FAIL
    msg = f"  {icon} {label}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    results.append((label, condition))
    return condition


def print_json(data, indent=4):
    import json
    print(json.dumps(data, indent=indent, default=str))


# ──────────────────────────────────────────────────────────────────────────────
# App + auth setup
# ──────────────────────────────────────────────────────────────────────────────

from app import create_app

app = create_app()

# Grab the foxyclaw test user from the predictions DB
with app.app_context():
    from app.db import PredSession, HBSession
    from app.models.pred_user import PredUser
    session = PredSession()
    test_user = session.execute(
        select(PredUser).where(PredUser.email == "foxyclawpower@gmail.com")
    ).scalar_one_or_none()

    if test_user is None:
        print("❌ No test user found (foxyclawpower@gmail.com) — run the auth flow first")
        sys.exit(1)

    print(f"\n🦊 Running as: {test_user.display_name} (id={test_user.id})\n")


FAKE_TOKEN = "Bearer test-token"

def _fake_validate_token(token: str) -> dict:
    """Bypass JWT validation — return a fake payload for the test user."""
    return {
        "sub": test_user.auth0_sub,
        "email": test_user.email,
        "name": test_user.display_name,
        "picture": None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Pick a real game to use
# ──────────────────────────────────────────────────────────────────────────────

with app.app_context():
    from app.db import HBSession
    try:
        from hockey_blast_common_lib.models import Game
        hb = HBSession()
        from datetime import date
        game = hb.execute(
            select(Game)
            .where(Game.status == "Scheduled", Game.date >= date.today())
            .order_by(Game.date.asc(), Game.time.asc())
            .limit(1)
        ).scalar_one_or_none()
    except Exception as e:
        print(f"❌ Could not load game from hockey_blast DB: {e}")
        sys.exit(1)

    if game is None:
        print("❌ No upcoming scheduled games found")
        sys.exit(1)

    TEST_GAME_ID = game.id
    TEST_HOME_TEAM_ID = game.home_team_id
    TEST_VISITOR_TEAM_ID = game.visitor_team_id

    print(f"🏒 Test game: #{TEST_GAME_ID}  "
          f"home={TEST_HOME_TEAM_ID} vs visitor={TEST_VISITOR_TEAM_ID}  "
          f"date={game.date} {game.time}\n")


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

from contextlib import ExitStack
with ExitStack() as stack:
    # Patch validate_token so real require_auth/optional_auth run but skip JWT check
    stack.enter_context(
        patch("app.auth.jwt_validator.validate_token", side_effect=_fake_validate_token)
    )
    client = stack.enter_context(app.test_client())
    # All requests need a fake Authorization header to pass the "Bearer token required" check
    client.environ_base["HTTP_AUTHORIZATION"] = FAKE_TOKEN

    print("── Health ──────────────────────────────────────────────")

    r = client.get("/api/health")
    check("GET /api/health → 200", r.status_code == 200)

    r = client.get("/api/health/db")
    data = r.get_json()
    check("GET /api/health/db → both DBs ok",
          data.get("hb_db") == "ok" and data.get("pred_db") == "ok",
          str(data))

    print("\n── Games ───────────────────────────────────────────────")

    r = client.get("/api/games?per_page=5")
    data = r.get_json()
    check("GET /api/games → 200", r.status_code == 200)
    check("Games list has results", len(data.get("games", [])) > 0,
          f"total={data.get('total')}")

    first_game = data.get("games", [{}])[0]
    check("Game has home_team name", bool(first_game.get("home_team", {}).get("name")))
    check("Game has visitor_team name", bool(first_game.get("visitor_team", {}).get("name")))
    check("Game has scheduled_start", bool(first_game.get("scheduled_start")))
    check("Game is_pickable is bool", isinstance(first_game.get("is_pickable"), bool))
    print(f"  → First game: {first_game.get('home_team',{}).get('name')} vs "
          f"{first_game.get('visitor_team',{}).get('name')}  "
          f"skill: {first_game.get('home_team',{}).get('avg_skill','?'):.1f} vs "
          f"{first_game.get('visitor_team',{}).get('avg_skill','?'):.1f}"
          if isinstance(first_game.get('home_team',{}).get('avg_skill'), float) else
          f"  → First game: {first_game.get('home_team',{}).get('name')} vs {first_game.get('visitor_team',{}).get('name')}")

    r = client.get(f"/api/games/{TEST_GAME_ID}")
    check(f"GET /api/games/{TEST_GAME_ID} → 200", r.status_code == 200)

    print("\n── Leagues ─────────────────────────────────────────────")

    r = client.post("/api/leagues", json={
        "name": "E2E Test League",
        "season_label": "2025-26",
        "scoring_preset": "standard",
    })
    check("POST /api/leagues → 201", r.status_code == 201,
          f"status={r.status_code} body={r.data[:200]}")
    league_data = r.get_json() or {}
    league_id = league_data.get("league_id") or league_data.get("id")
    check("League created with id", bool(league_id), str(league_data))
    print(f"  → League id: {league_id}  name: {league_data.get('name')}")

    print("\n── Picks ───────────────────────────────────────────────")

    r = client.post("/api/picks", json={
        "game_id": TEST_GAME_ID,
        "league_id": league_id,
        "picked_team_id": TEST_HOME_TEAM_ID,
        "confidence": 2,
    })
    check("POST /api/picks → 201", r.status_code == 201,
          f"status={r.status_code} body={r.data[:300]}")
    pick_data = r.get_json() or {}
    pick_id = pick_data.get("pick_id")
    check("Pick created with id", bool(pick_id), str(pick_data))

    if pick_id:
        print(f"  → Pick id: {pick_id}  confidence: {pick_data.get('confidence')}x  "
              f"upset: {pick_data.get('is_upset_pick')}  "
              f"projected: {pick_data.get('projected_points')}")

        r = client.get(f"/api/picks/{pick_id}")
        check(f"GET /api/picks/{pick_id} → 200", r.status_code == 200)

    r = client.get("/api/picks/mine")
    data = r.get_json() or {}
    check("GET /api/picks/mine → 200", r.status_code == 200)
    check("My picks contains the new pick",
          any(p.get("id") == pick_id for p in data.get("picks", [])),
          f"total={data.get('total')}")

    # Re-pick with different confidence (upsert)
    r = client.post("/api/picks", json={
        "game_id": TEST_GAME_ID,
        "league_id": league_id,
        "picked_team_id": TEST_HOME_TEAM_ID,
        "confidence": 3,
    })
    check("POST /api/picks (update confidence) → 200 or 201",
          r.status_code in (200, 201), f"status={r.status_code}")
    updated = r.get_json() or {}
    check("Confidence updated to 3", updated.get("confidence") == 3,
          str(updated.get("confidence")))

    # Delete the pick
    if pick_id:
        r = client.delete(f"/api/picks/{pick_id}")
        check(f"DELETE /api/picks/{pick_id} → 200", r.status_code == 200,
              f"status={r.status_code} body={r.data[:200]}")

    print("\n── Standings ───────────────────────────────────────────")

    if league_id:
        r = client.get(f"/api/standings/{league_id}")
        check(f"GET /api/standings/{league_id} → 200", r.status_code == 200,
              f"status={r.status_code} body={r.data[:200]}")

# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────

passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
total = len(results)

print(f"\n{'─'*55}")
print(f"  Results: {passed}/{total} passed  {'🎉' if failed == 0 else '⚠️  ' + str(failed) + ' failed'}")
print(f"{'─'*55}\n")

if failed:
    print("Failed tests:")
    for label, ok in results:
        if not ok:
            print(f"  ❌ {label}")
    sys.exit(1)
