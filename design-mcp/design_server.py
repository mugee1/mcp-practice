"""디자인 MCP 서버 (읽기 전용)

디자인 규칙(토큰 · 컴포넌트 · 상태 · 문구)과 화면 진행 상황을 Claude 가 찾아 쓰게 해 주는 MCP 예요.
- 자료: 이 파일과 같은 폴더의 design_tokens.csv · screens.csv · docs/**/*.md
- 도구 5개: 규칙 3개(토큰 찾기 · 가이드 보기 · 색 대비 검사) + 현황 2개(화면 보기 · 디자인 진행률)
- 쓰기 · 지우기 · 파일 저장 기능은 일부러 없어요. 자료를 바꾸려면 사람이 파일을 고쳐 PR 로 올려요.
- 실행: python design_server.py  (stdio 방식 — 실행하면 멈춰 있는 게 정상, Ctrl+C 로 종료)
- 설치한 mcp 버전: 2.x (2.x 에서는 FastMCP 대신 MCPServer 를 써요)
"""

import csv  # CSV(표) 파일 읽기
import re  # 색 값 모양 검사
from pathlib import Path  # 파일 경로 다루기
from typing import Annotated  # 도구 입력값에 설명 붙이기

from pydantic import Field  # 입력값 설명 (AI 가 읽어요)
from mcp.server.mcpserver import MCPServer  # MCP 서버 본체 (mcp 2.x)
from mcp.types import ToolAnnotations  # 「읽기 전용」 표시

# ── 경로: 어디서 실행하든 이 파이썬 파일 위치를 기준으로 찾아요 ──────────────
BASE = Path(__file__).resolve().parent
TOKENS_CSV = BASE / "design_tokens.csv"
SCREENS_CSV = BASE / "screens.csv"
DOCS_DIR = BASE / "docs"

# 모든 도구에 붙일 표시: 읽기만 하고, 아무것도 바꾸지 않고, 바깥 인터넷도 안 씀
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

# 화면 상태는 이 네 가지만 써요 (진행률 순서대로)
STATUS_ORDER = ["기획 중", "진행 중", "완료", "수정 필요"]

mcp = MCPServer(
    name="design",
    instructions=(
        "디자인 규칙과 화면 진행 상황을 알려 주는 읽기 전용 도구예요. "
        "색 · 글자 · 간격은 find_tokens, 컴포넌트 · 상태 · 문구 규칙은 read_guide, "
        "글자색이 잘 보이는지는 check_contrast, 화면별 진행은 list_screens · design_progress 를 쓰세요. "
        "자료에 없는 내용은 지어내지 말고 없다고 답하세요."
    ),
)


# ── 공통 도우미 ────────────────────────────────────────────────────────────
def read_csv(path: Path) -> list[dict]:
    """CSV 를 읽어 줄마다 {칸 이름: 값} 으로 돌려줘요. 엑셀 저장 파일도 되게 utf-8-sig 로 읽어요."""
    if not path.exists():  # 파일이 없으면 빈 목록 (에러로 죽지 않게)
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(f)]


def squash(text: str) -> str:
    """띄어쓰기를 지우고 소문자로 — 「반납지연」 「반납 지연」을 같은 말로 보기 위해."""
    return re.sub(r"\s+", "", text).lower()


# ── 규칙 도구 1: 토큰 찾기 ──────────────────────────────────────────────────
@mcp.tool(name="find_tokens", title="토큰 찾기", annotations=READ_ONLY)
def find_tokens(
    keyword: Annotated[str, Field(description="찾을 말. 토큰 이름(brand.primary) · 용도(경고, 보조 글자, 카드) · 종류(색, 간격, 글자) 모두 돼요. 비우면 전체")] = "",
) -> dict:
    """디자인 토큰(색 · 글자 · 간격 · 모서리 · 선)을 찾아요.

    design_tokens.csv 의 모든 칸(이름 · 종류 · 값 · 쓰는 곳 · 규칙)에서 키워드를 찾아
    토큰 이름, 라이트 · 다크 값, 쓰는 곳, 지켜야 할 규칙을 돌려줘요.
    「경고 색이 뭐야?」 「요약 카드 배경은?」 「간격 규칙」 같은 질문에 쓰세요.
    """
    rows = read_csv(TOKENS_CSV)
    q = squash(keyword)
    found = [r for r in rows if not q or q in squash(" ".join(r.values()))]  # 어느 칸에든 있으면 찾음
    return {"키워드": keyword or "(전체)", "개수": len(found), "토큰": found}


# ── 규칙 도구 2: 가이드 보기 ────────────────────────────────────────────────
def split_sections(text: str) -> list[tuple[str, str]]:
    """md 문서를 제목(#, ##) 단위로 잘라 (제목, 내용) 목록으로 만들어요."""
    sections, title, lines = [], "", []
    for line in text.splitlines():
        if re.match(r"^#{1,2}\s", line):  # 새 제목이 나오면 앞 덩어리를 저장
            if title or any(l.strip() for l in lines):
                sections.append((title, "\n".join(lines).strip()))
            title, lines = line.lstrip("#").strip(), []
        else:
            lines.append(line)
    sections.append((title, "\n".join(lines).strip()))
    return sections


@mcp.tool(name="read_guide", title="가이드 보기", annotations=READ_ONLY)
def read_guide(
    topic: Annotated[str, Field(description="알고 싶은 주제. 컴포넌트(버튼, 상태배지, 팝업창, 입력창, 카드) · 상태(반납 지연, 정비중) · 문구(오류 문구, 빈 상태, 용어) 등")],
) -> dict:
    """컴포넌트 · 상태 표현 · 문구 규칙 문서에서 주제에 맞는 부분을 찾아 보여 줘요.

    docs/ 아래 md 문서를 읽어요.
    - 파일 이름이 주제와 같으면(예: 「버튼」) 그 문서 전체를 돌려줘요.
    - 아니면 제목이나 내용에 주제가 들어 있는 부분(섹션)만 최대 8개 돌려줘요.
    「버튼 언제 써?」 「반납 지연은 어떻게 보여 줘?」 「오류 문구 규칙」 같은 질문에 쓰세요.
    """
    q = squash(topic)
    if not q:
        return {"주제": topic, "안내": "주제를 적어 주세요.", "문서 목록": doc_list()}

    files = sorted(DOCS_DIR.rglob("*.md")) if DOCS_DIR.exists() else []

    # 1) 파일 이름이 주제와 같으면 문서 통째로
    for path in files:
        if q in squash(path.stem):
            return {"주제": topic, "문서": [{"파일": rel(path), "내용": path.read_text(encoding="utf-8")}]}

    # 2) 아니면 주제가 들어 있는 섹션만
    hits = []
    for path in files:
        for title, body in split_sections(path.read_text(encoding="utf-8")):
            if q in squash(title) or q in squash(body):
                hits.append({"파일": rel(path), "제목": title, "내용": body})
    if not hits:
        return {"주제": topic, "안내": "가이드에 이 주제가 없어요.", "문서 목록": doc_list()}
    return {"주제": topic, "개수": len(hits), "문서": hits[:8]}


def rel(path: Path) -> str:
    """사람이 읽기 쉬운 짧은 경로 (예: docs/components/버튼.md)"""
    return path.relative_to(BASE).as_posix()


def doc_list() -> list[str]:
    """찾을 문서가 없을 때 어떤 문서가 있는지 알려 주기용."""
    return [rel(p) for p in sorted(DOCS_DIR.rglob("*.md"))] if DOCS_DIR.exists() else []


# ── 규칙 도구 3: 색 대비 검사 ───────────────────────────────────────────────
HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def to_rgba(value: str, mode: str) -> tuple[tuple[float, float, float, float], str] | None:
    """색 값(#0066FF · #RGB · #RRGGBBAA) 또는 토큰 이름을 (빨, 초, 파, 투명도) 로 바꿔요. 모르면 None."""
    value = value.strip()
    source = value
    if not HEX.match(value):  # 색 값이 아니면 토큰 이름으로 찾기
        token = next((r for r in read_csv(TOKENS_CSV) if r.get("이름", "").lower() == value.lower()), None)
        if not token:
            return None
        value = token.get("다크" if mode == "다크" else "라이트", "")
        source = f"{token['이름']} ({value})"
        if not HEX.match(value):  # 색이 아닌 토큰(간격 등)
            return None
    h = value.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    return (r, g, b, a), source


def over(top: tuple, bottom: tuple) -> tuple:
    """반투명 색(top)을 아래 색(bottom) 위에 올렸을 때 눈에 보이는 색."""
    a = top[3]
    return tuple(top[i] * a + bottom[i] * (1 - a) for i in range(3)) + (1.0,)


def luminance(c: tuple) -> float:
    """WCAG 상대 밝기 (0 = 검정, 1 = 흰색)"""
    def ch(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


@mcp.tool(name="check_contrast", title="색 대비 검사", annotations=READ_ONLY)
def check_contrast(
    text_color: Annotated[str, Field(description="글자색. 색 값(#00BF40) 또는 토큰 이름(positive.primary)")],
    background: Annotated[str, Field(description="배경색. 색 값 또는 토큰 이름. 비우면 페이지 기본 배경")] = "",
    mode: Annotated[str, Field(description="「라이트」 또는 「다크」. 토큰 이름을 쓸 때 어느 값을 쓸지 정해요")] = "라이트",
) -> dict:
    """글자색이 배경 위에서 잘 보이는지 WCAG 2.1 대비 기준으로 검사해요.

    색 값이나 토큰 이름을 받아 대비 수치를 계산하고, 기준 통과 여부를 알려 줘요.
    - 일반 글자 AA: 4.5 이상 / 큰 글자(약 24px 이상, 또는 19px 이상 굵게) AA: 3.0 이상 / AAA: 7.0 이상
    - 반투명 색(#RRGGBBAA)은 배경과 섞인 실제 색으로 계산해요.
    「이 초록 글자 잘 보여?」 「흰 글자를 파란 버튼에 써도 돼?」 같은 질문에 쓰세요.
    """
    mode = "다크" if "다크" in mode or "dark" in mode.lower() else "라이트"
    page = (0x1B, 0x1C, 0x1E, 1.0) if mode == "다크" else (255, 255, 255, 1.0)  # 페이지 기본 배경

    fg = to_rgba(text_color, mode)
    bg = to_rgba(background, mode) if background.strip() else (page, f"페이지 기본 배경 ({mode})")
    if fg is None or bg is None:
        wrong = text_color if fg is None else background
        return {"오류": f"「{wrong}」은(는) 색 값도, 색 토큰 이름도 아니에요. 예: #0066FF 또는 brand.primary"}

    bg_rgb = over(bg[0], page)  # 배경이 반투명이면 페이지 배경 위에 올린 색
    fg_rgb = over(fg[0], bg_rgb)  # 글자가 반투명이면 배경 위에 올린 색
    l1, l2 = sorted((luminance(fg_rgb), luminance(bg_rgb)), reverse=True)
    ratio = round((l1 + 0.05) / (l2 + 0.05), 2)

    normal, large, aaa = ratio >= 4.5, ratio >= 3.0, ratio >= 7.0
    if normal:
        verdict = "통과 — 본문 글자로 써도 돼요."
    elif large:
        verdict = "본문 글자는 미달 — 큰 글자(약 24px 이상 또는 19px 이상 굵게)에만 쓰세요."
    else:
        verdict = "미달 — 글자로 쓰기엔 너무 흐려요. 더 진한 색을 쓰거나 배경을 바꾸세요."

    return {
        "글자색": fg[1],
        "배경색": bg[1],
        "모드": mode,
        "대비": f"{ratio}:1",
        "일반 글자 AA (4.5)": "통과" if normal else "미달",
        "큰 글자 AA (3.0)": "통과" if large else "미달",
        "AAA (7.0)": "통과" if aaa else "미달",
        "판정": verdict,
    }


# ── 현황 도구 1: 화면 보기 ──────────────────────────────────────────────────
@mcp.tool(name="list_screens", title="화면 보기", annotations=READ_ONLY)
def list_screens(
    status: Annotated[str, Field(description="디자인 상태로 거르기: 기획 중 · 진행 중 · 완료 · 수정 필요. 비우면 전체")] = "",
    handoff: Annotated[str, Field(description="개발 넘김 여부로 거르기: 넘김 · 대기. 비우면 전체")] = "",
) -> dict:
    """화면 목록과 화면별 디자인 상태 · 개발 넘김 여부 · 쓰는 컴포넌트와 토큰 · 메모를 보여 줘요.

    screens.csv 를 읽어요. 두 조건 모두 비우면 전체 화면이 나와요.
    없는 상태를 넣으면 빈 목록이 나와요.
    「수정 필요한 화면은?」 「개발이 가져갈 수 있는 화면(넘김)은?」 「차량 예약 화면 어디까지 됐어?」 같은 질문에 쓰세요.
    """
    rows = read_csv(SCREENS_CSV)
    s, h = squash(status), squash(handoff)
    found = [
        r for r in rows
        if (not s or squash(r.get("디자인 상태", "")) == s) and (not h or squash(r.get("개발 넘김", "")) == h)
    ]
    return {"조건": {"디자인 상태": status or "(전체)", "개발 넘김": handoff or "(전체)"}, "개수": len(found), "화면": found}


# ── 현황 도구 2: 디자인 진행률 ──────────────────────────────────────────────
@mcp.tool(name="design_progress", title="디자인 진행률", annotations=READ_ONLY)
def design_progress() -> dict:
    """디자인이 전체적으로 어디까지 됐는지 숫자로 보여 줘요.

    screens.csv 의 전체 화면 수, 상태별(기획 중 · 진행 중 · 완료 · 수정 필요) 개수,
    완료율(완료 ÷ 전체), 개발 넘김 비율, 그리고 손봐야 할 화면(수정 필요 · 진행 중) 목록을 돌려줘요.
    「디자인 몇 % 됐어?」 「주간 보고용 디자인 현황」 같은 질문에 쓰세요.
    """
    rows = read_csv(SCREENS_CSV)
    total = len(rows)
    if total == 0:
        return {"안내": "screens.csv 에 화면이 없어요."}

    counts = {st: 0 for st in STATUS_ORDER}
    for r in rows:
        st = r.get("디자인 상태", "") or "(빈 칸)"
        counts[st] = counts.get(st, 0) + 1  # 정해진 네 가지 밖의 상태도 세어 둬요

    done = counts.get("완료", 0)
    handed = sum(1 for r in rows if r.get("개발 넘김") == "넘김")
    pct = lambda n: f"{round(n / total * 100)}%"

    return {
        "전체 화면": total,
        "상태별": counts,
        "완료율": f"{pct(done)} ({done}/{total})",
        "개발 넘김": f"{pct(handed)} ({handed}/{total})",
        "손봐야 할 화면": [
            {"화면": r["화면"], "상태": r["디자인 상태"], "메모": r.get("메모", "")}
            for r in rows if r.get("디자인 상태") in ("수정 필요", "진행 중")
        ],
    }


# ── 대시보드: 같은 자료로 진행 현황 · 대비 점검을 한 화면에 ─────────────────────
def dashboard_page(mcp_url: str) -> str:
    """dashboard.html 에 지금 자료로 계산한 숫자를 채워 돌려줘요. 열 때마다 CSV 를 새로 읽어요."""
    import json
    from datetime import datetime, timedelta, timezone

    tokens = read_csv(TOKENS_CSV)
    text_tokens = [t for t in tokens if t.get("종류") in ("색", "글자색", "참고 팔레트")]
    backgrounds = [("기본 배경", "background.neutral.primary"), ("요약 카드", "background.neutral.secondary")]
    columns, contrast = [], []
    for mode in ("라이트", "다크"):
        for label, _ in backgrounds:
            columns.append(f"{mode} · {label}")
    for t in text_tokens:
        cells = []
        for mode in ("라이트", "다크"):
            for _, bg in backgrounds:
                r = check_contrast(t["이름"], bg, mode)
                cells.append({"ratio": r["대비"].split(":")[0]} if "대비" in r else None)
        contrast.append({"name": t["이름"], "use": t.get("쓰는 곳", ""), "light": t.get("라이트", ""), "cells": cells})

    # 컬러 시스템: 색 값(#RRGGBB · #RRGGBBAA)이 들어 있는 토큰 전부
    colors = [
        {"name": t["이름"], "kind": t.get("종류", ""), "light": t["라이트"], "dark": t.get("다크", ""),
         "use": t.get("쓰는 곳", ""), "rule": t.get("규칙", "")}
        for t in tokens
        if HEX.match(t.get("라이트", "")) and HEX.match(t.get("다크", ""))
    ]

    data = {
        "colors": colors,
        "generated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M (KST)"),
        "progress": design_progress(),
        "screens": read_csv(SCREENS_CSV),
        "contrast_columns": columns,
        "contrast": contrast,
    }
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")  # <script> 안에 안전하게 넣기
    page = (BASE / "dashboard.html").read_text(encoding="utf-8")
    return page.replace("__DATA__", blob).replace("__MCP_URL__", mcp_url)


# ── 원격(HTTP) 실행: 주소 하나로 여러 사람이 같이 써요 ──────────────────────────
def http_app():
    """인터넷 주소(/mcp)로 접속하는 웹 앱을 만들어요. Vercel 같은 곳에 올릴 때 써요.

    - 환경 변수 DESIGN_MCP_KEY 가 있으면 그 키를 아는 사람만 쓸 수 있어요.
      키는 「Authorization: Bearer 키」 머리글이나 주소 뒤 「?key=키」 로 보내요.
      (claude.ai 커넥터는 머리글을 못 넣어서 ?key= 방식을 써요)
    - 비어 있으면 주소를 아는 누구나 읽을 수 있어요 (읽기 전용이라 바뀌는 건 없어요).
    """
    import hmac
    import os
    from urllib.parse import parse_qs

    # 서버 여러 대가 번갈아 받아도 되게: 대화 기억 없이(stateless) JSON 으로 바로 답해요
    inner = mcp.streamable_http_app(stateless_http=True, json_response=True, host="0.0.0.0")
    key = os.environ.get("DESIGN_MCP_KEY", "").strip()

    async def app(scope, receive, send):
        # 사람이 브라우저로 주소를 열면 → 사용법 안내 페이지 (guide.html) 를 보여 줘요
        if scope["type"] == "http" and scope.get("method") == "GET":
            headers = dict(scope.get("headers") or [])
            accept = headers.get(b"accept", b"").decode().lower()
            query = parse_qs(scope.get("query_string", b"").decode())
            wants_dashboard = scope.get("path", "").rstrip("/").endswith("/dashboard") or query.get("page") == ["dashboard"]
            if wants_dashboard or ("text/html" in accept and "text/event-stream" not in accept):
                host = headers.get(b"host", b"").decode()
                proto = headers.get(b"x-forwarded-proto", b"").decode() or ("http" if host.startswith(("127.", "localhost")) else "https")
                mcp_url = f"{proto}://{host}/mcp"
                if wants_dashboard:  # /dashboard → 디자인 현황판
                    page = dashboard_page(mcp_url)
                else:  # 그 밖에 브라우저로 열면 → 사용법 안내
                    page = (BASE / "guide.html").read_text(encoding="utf-8").replace("__URL__", mcp_url)
                await send({"type": "http.response.start", "status": 200,
                            "headers": [(b"content-type", b"text/html; charset=utf-8")]})
                await send({"type": "http.response.body", "body": page.encode()})
                return

        if key and scope["type"] == "http":
            headers = dict(scope.get("headers") or [])
            auth = headers.get(b"authorization", b"").decode()
            given = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
            if not given:
                given = parse_qs(scope.get("query_string", b"").decode()).get("key", [""])[0]
            if not hmac.compare_digest(given.encode(), key.encode()):
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"application/json; charset=utf-8")]})
                await send({"type": "http.response.body",
                            "body": '{"error": "접속 키가 없거나 틀렸어요."}'.encode()})
                return
        if scope["type"] == "http":
            # Vercel 은 주소를 /api/index 로 바꿔 넘기기도 해요 → 어느 경로든 MCP 입구(/mcp)로 보내요
            scope = {**scope, "path": "/mcp", "raw_path": b"/mcp"}
        await inner(scope, receive, send)  # 키 검사를 통과하면 MCP 서버로 넘겨요

    return app


# ── 실행 ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if "--http" in sys.argv:  # python design_server.py --http → http://127.0.0.1:8000/mcp
        import uvicorn

        uvicorn.run(http_app(), host="127.0.0.1", port=8000)
    else:
        mcp.run()  # 기본 stdio: Claude Code 가 이 프로그램을 켜고 표준 입출력으로 대화해요
