"""AI router — kick off briefings and read them back."""
from __future__ import annotations

from asgiref.sync import sync_to_async
from ninja import Router
from ninja.errors import HttpError

from apps.ai.models import Briefing
from apps.ai.schemas import BriefingIn, BriefingOut
from apps.ai.services import generate_briefing
from apps.auth_jwt.dependencies import JWTAuth

router = Router(auth=JWTAuth())


@router.post("/briefing", response=BriefingOut, summary="Generate a fresh briefing")
async def make_briefing(request, payload: BriefingIn):
    try:
        return await generate_briefing(
            payload.symbol, payload.interval,
            lookback=payload.lookback, prompt_version=payload.prompt_version,
        )
    except RuntimeError as exc:
        raise HttpError(404, str(exc)) from exc


@router.get("/briefing/{symbol}/{interval}/latest", response=BriefingOut, summary="Most recent briefing")
async def latest_briefing(request, symbol: str, interval: str):
    @sync_to_async
    def _q():
        return Briefing.objects.filter(symbol__code=symbol, interval=interval).select_related("symbol").first()

    b = await _q()
    if not b:
        raise HttpError(404, "no briefing yet — POST /briefing to generate one")
    from apps.ai.schemas import ReviewerJudgment, WyckoffJudgment
    return BriefingOut(
        symbol=symbol, interval=interval, prompt_version=b.prompt_version,
        current_trend="undefined", mtf_score=0.0,
        narrative_markdown=b.markdown,
        wyckoff=WyckoffJudgment(current_phase=b.wyckoff_phase, confidence=b.wyckoff_conf,
                                volume_supports_label=False),
        reviewer=ReviewerJudgment(severity=b.reviewer_sev),
        iterations=b.iterations,
        token_usage=b.token_usage,
    )
