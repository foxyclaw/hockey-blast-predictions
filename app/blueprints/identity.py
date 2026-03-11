"""
Identity blueprint — link a PredUser to their hockey_blast human profile.

Routes:
    GET  /api/identity/candidates  — search for matching humans in hockey_blast
    POST /api/identity/confirm     — confirm or skip identity linking
"""

from flask import Blueprint, g, jsonify, request
from sqlalchemy import select, func, distinct

from app.auth.jwt_validator import require_auth
from app.db import HBSession, PredSession
from app.utils.response import error_response

identity_bp = Blueprint("identity", __name__)


def _get_hb_models():
    """Import hockey_blast ORM models. Returns (Human, GameRoster, Game, Organization) or raises."""
    try:
        from hockey_blast_common_lib.models import Human, GameRoster, Game, Organization
        return Human, GameRoster, Game, Organization
    except ImportError as exc:
        raise RuntimeError("hockey_blast_common_lib not available") from exc


@identity_bp.route("/candidates", methods=["GET"])
@require_auth
def get_candidates():
    """
    GET /api/identity/candidates

    Search for hockey_blast human profiles that might match the current user.

    Extracts first/last name from g.pred_user.display_name (split on first space).
    Optional query param: ?name=Pavel+Kletskov to override the search name.

    Returns:
        { "candidates": [ { id, first_name, last_name, skill_value, orgs, last_game_date } ] }
    """
    user = g.pred_user

    # Determine search name
    name_override = request.args.get("name", "").strip()
    if name_override:
        parts = name_override.split(None, 1)
    else:
        parts = (user.display_name or "").split(None, 1)

    first = parts[0] if len(parts) > 0 else ""
    last = parts[1] if len(parts) > 1 else ""

    if not first and not last:
        return jsonify({"candidates": []})

    try:
        Human, GameRoster, Game, Organization = _get_hb_models()
    except RuntimeError as exc:
        return error_response("SERVICE_UNAVAILABLE", str(exc), 503)

    hb_session = HBSession()

    try:
        # Build the query using SQLAlchemy ORM/select()
        # We need: humans who match first+last name, with their orgs and last game date
        stmt = (
            select(
                Human.id,
                Human.first_name,
                Human.last_name,
                Human.skater_skill_value,
                func.array_agg(distinct(Organization.name)).label("orgs"),
                func.max(Game.date).label("last_game_date"),
            )
            .join(GameRoster, GameRoster.human_id == Human.id)
            .join(Game, Game.id == GameRoster.game_id)
            .join(Organization, Organization.id == Game.org_id)
            .where(
                Human.first_name.ilike(f"%{first}%") if first else True,
                Human.last_name.ilike(f"%{last}%") if last else True,
            )
            .group_by(Human.id, Human.first_name, Human.last_name, Human.skater_skill_value)
            .order_by(func.max(Game.date).desc())
            .limit(10)
        )

        rows = hb_session.execute(stmt).all()

        candidates = []
        for row in rows:
            candidates.append({
                "id": row.id,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "skill_value": float(row.skater_skill_value) if row.skater_skill_value is not None else None,
                "orgs": list(row.orgs) if row.orgs else [],
                "last_game_date": row.last_game_date.isoformat() if row.last_game_date else None,
            })

        return jsonify({"candidates": candidates})

    except Exception as exc:
        return error_response("INTERNAL_ERROR", f"Query failed: {exc}", 500)


@identity_bp.route("/confirm", methods=["POST"])
@require_auth
def confirm_identity():
    """
    POST /api/identity/confirm

    Body: { "hb_human_id": 12345 }           — claim one identity
       or { "hb_human_id": [123, 456] }       — claim multiple at once
       or { "skip": true }                     — decline to link for now

    All claims are appended to pred_user_hb_claims (never overwritten).
    The first claim (or only claim) also sets pred_users.hb_human_id as primary.
    Two users can claim the same hb_human_id — conflicts resolved by nightly job.

    Returns: { "linked": bool, "claims": [ {hb_human_id, is_primary} ] }
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.models.pred_user_hb_claim import PredUserHbClaim

    user = g.pred_user
    data = request.get_json(force=True, silent=True) or {}
    pred_session = PredSession()

    if data.get("skip"):
        return jsonify({"linked": False, "claims": []})

    # Accept single int or list of ints
    raw = data.get("hb_human_id")
    if raw is None:
        return error_response("VALIDATION_ERROR", "Must provide 'hb_human_id' or 'skip: true'", 400)
    ids_to_claim = raw if isinstance(raw, list) else [raw]

    if not all(isinstance(i, int) and i > 0 for i in ids_to_claim):
        return error_response("VALIDATION_ERROR", "hb_human_id must be positive integer(s)", 400)

    # Verify all humans exist in hockey_blast
    try:
        Human, _, _, _ = _get_hb_models()
        hb_session = HBSession()
        for hid in ids_to_claim:
            if hb_session.get(Human, hid) is None:
                return error_response("NOT_FOUND", f"No human found with id={hid}", 404)
    except RuntimeError as exc:
        return error_response("SERVICE_UNAVAILABLE", str(exc), 503)

    # Fetch existing claims to determine is_primary
    existing = pred_session.execute(
        select(PredUserHbClaim).where(PredUserHbClaim.user_id == user.id)
    ).scalars().all()
    existing_ids = {c.hb_human_id for c in existing}
    has_primary = any(c.is_primary for c in existing)

    new_claims = []
    for idx, hid in enumerate(ids_to_claim):
        if hid in existing_ids:
            continue  # already claimed, skip (upsert would also work)
        is_primary = not has_primary and idx == 0
        claim = PredUserHbClaim(
            user_id=user.id,
            hb_human_id=hid,
            source="self_reported",
            is_primary=is_primary,
        )
        pred_session.add(claim)
        new_claims.append({"hb_human_id": hid, "is_primary": is_primary})
        if is_primary:
            has_primary = True

    # Keep pred_users.hb_human_id as the primary for quick lookups
    if new_claims and any(c["is_primary"] for c in new_claims):
        user.hb_human_id = new_claims[0]["hb_human_id"]

    pred_session.commit()

    all_claims = [
        {"hb_human_id": c.hb_human_id, "is_primary": c.is_primary}
        for c in pred_session.execute(
            select(PredUserHbClaim).where(PredUserHbClaim.user_id == user.id)
        ).scalars().all()
    ]

    return jsonify({"linked": True, "claims": all_claims})
