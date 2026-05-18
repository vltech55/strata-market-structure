"""Chat router — sessions and grounded Q&A."""
from __future__ import annotations

from asgiref.sync import sync_to_async
from ninja import Router
from ninja.errors import HttpError

from apps.auth_jwt.dependencies import JWTAuth
from apps.chat.models import ChatMessage, ChatRole, ChatSession
from apps.chat.schemas import ChatAskIn, ChatMessageOut, ChatSessionCreateIn, ChatSessionOut
from apps.chat.services import answer as chat_answer
from apps.stock.models import Symbol

router = Router(auth=JWTAuth())


@router.get("/sessions", response=list[ChatSessionOut], summary="List my sessions")
async def list_sessions(request):
    principal = request.auth

    @sync_to_async
    def _q():
        return list(
            ChatSession.objects.filter(user_id=principal.user_id)
            .select_related("symbol")
            .values("id", "interval", "title", "updated_at", "symbol__code")
        )

    rows = await _q()
    return [
        ChatSessionOut(id=r["id"], interval=r["interval"], title=r["title"],
                       updated_at=r["updated_at"], symbol=r["symbol__code"])
        for r in rows
    ]


@router.post("/sessions", response={201: ChatSessionOut}, summary="Create a session")
async def create_session(request, payload: ChatSessionCreateIn):
    principal = request.auth

    @sync_to_async
    def _create():
        symbol = Symbol.objects.filter(code=payload.symbol).first() if payload.symbol else None
        s = ChatSession.objects.create(
            user_id=principal.user_id, symbol=symbol,
            interval=payload.interval, title=payload.title or (payload.symbol or "Untitled"),
        )
        return s

    s = await _create()
    return 201, ChatSessionOut(id=s.id, interval=s.interval, title=s.title,
                                updated_at=s.updated_at, symbol=s.symbol.code if s.symbol else None)


@router.get("/sessions/{session_id}/messages", response=list[ChatMessageOut])
async def session_messages(request, session_id: str):
    @sync_to_async
    def _q():
        return list(ChatMessage.objects.filter(session_id=session_id).order_by("created_at")
                    .values("id", "role", "content", "created_at"))
    return await _q()


@router.post("/ask", response=ChatMessageOut, summary="Ask a grounded question")
async def ask(request, payload: ChatAskIn, session_id: str | None = None):
    principal = request.auth

    @sync_to_async
    def _ensure_session():
        if session_id:
            return ChatSession.objects.get(id=session_id, user_id=principal.user_id)
        symbol = Symbol.objects.filter(code=payload.symbol).first() if payload.symbol else None
        return ChatSession.objects.create(
            user_id=principal.user_id, symbol=symbol, interval=payload.interval or "1h",
            title=payload.symbol or "Q&A",
        )

    session = await _ensure_session()
    interval = payload.interval or session.interval
    symbol = payload.symbol or (session.symbol.code if session.symbol else None)

    text = await chat_answer(payload.question, symbol_code=symbol, interval=interval)

    @sync_to_async
    def _persist():
        ChatMessage.objects.create(session=session, role=ChatRole.USER, content=payload.question)
        m = ChatMessage.objects.create(session=session, role=ChatRole.ASSISTANT, content=text)
        session.save(update_fields=["updated_at"])  # bumps updated_at
        return m

    msg = await _persist()
    return ChatMessageOut(id=msg.id, role=msg.role, content=msg.content, created_at=msg.created_at)
