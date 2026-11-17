# design MCP — 디자인 규칙 + 화면 진행 현황 (읽기 전용)

Claude 에게 **우리 팀 디자인 규칙**(색 · 글자 · 컴포넌트 · 상태 · 문구)과 **화면 진행 상황**을 꺼내 주는 MCP 예요.
지금 자료는 **차량 배차판**(`carsystem`) 기준이에요. 2차 프로젝트에서는 자료 파일만 바꾸면 그대로 써요.

## 도구 5개

| 묶음 | 도구 (이름 / 제목) | 물어보는 말 예시 |
|---|---|---|
| 규칙 | `find_tokens` / 토큰 찾기 | 「경고 색 토큰 알려 줘」 「요약 카드 배경은?」 |
| 규칙 | `read_guide` / 가이드 보기 | 「버튼 언제 써?」 「반납 지연은 어떻게 보여 줘?」 「오류 문구 규칙」 |
| 규칙 | `check_contrast` / 색 대비 검사 | 「positive.primary 글자를 요약 카드 배경에 써도 잘 보여?」 |
| 현황 | `list_screens` / 화면 보기 | 「수정 필요한 화면은?」 「개발 넘김 대기 중인 화면은?」 |
| 현황 | `design_progress` / 디자인 진행률 | 「디자인 몇 % 됐어?」 |

> 도구 이름이 영어인 이유: Claude 의 도구 이름 규칙(영문 · 숫자 · `_` · `-`)에 맞추려고요. 제목과 설명은 한국어라 AI 가 보고 골라요.

**만들지 않은 도구**: 토큰 수정 · 화면 상태 변경 · 문서 쓰기 — 디자인 규칙은 사람이 정하고, 바꾼 기록이 PR 로 남아야 해서예요.

## 자료 파일 (여기만 고치면 돼요)

| 파일 | 내용 | 칸 |
|---|---|---|
| `design_tokens.csv` | 디자인 토큰 | 이름 · 종류 · 라이트 · 다크 · 쓰는 곳 · 규칙 |
| `screens.csv` | 화면 목록 · 진행 상황 | 화면 · 디자인 상태 · 개발 넘김 · 담당 · 쓰는 컴포넌트 · 쓰는 토큰 · 메모 |
| `docs/상태표현.md` | 상태별 이름 · 색 · 표현 | |
| `docs/문구.md` | 말투 · 용어 · 오류/빈 상태 문구 | |
| `docs/components/*.md` | 컴포넌트별 규칙 | 파일 하나 = 컴포넌트 하나 |

- 디자인 상태는 `기획 중 · 진행 중 · 완료 · 수정 필요`, 개발 넘김은 `넘김 · 대기` 만 써요.
- CSV 는 **UTF-8** 로 저장해요 (엑셀은 「CSV UTF-8」). 칸 안에 쉼표 대신 ` · ` 를 써요.
- `screens.csv` 의 「다크 모드 점검」 「차량 예약 화면」은 **연습용 가짜 항목**이에요.
- 파일을 고친 뒤에는 Claude Code 를 껐다 켜지 않아도 돼요 — 도구가 물어볼 때마다 파일을 새로 읽어요.

## 팀원 설치 (원격 — 설치할 것 없음)

서버는 Vercel 에 올라가 있어요. 주소: `https://design-mcp-tau.vercel.app/mcp` (공개 · 읽기 전용)

**Claude Code** — 아무 폴더에서 한 줄:
```
claude mcp add --transport http --scope user design https://design-mcp-tau.vercel.app/mcp
/mcp        # design 이 connected 면 성공
```

**claude.ai 웹 · 데스크톱 앱** — 설정 → 커넥터 → 「사용자 지정 커넥터 추가」 → 이름 `design`, 주소에 위 URL 붙여 넣기.

> 자료(CSV · docs)를 고쳐 main 에 푸시하면 Vercel 이 자동으로 다시 배포해서 모두에게 바로 반영돼요.

### 운영 메모 (담당자용)
- 지금은 누구나 읽을 수 있어요. 공개하면 안 되는 자료를 넣게 되면 Vercel 프로젝트 `design-mcp` 에 환경 변수 `DESIGN_MCP_KEY` 를 넣고 다시 배포하세요 → 주소 뒤에 `?key=키` 를 붙인 사람만 쓸 수 있어요.
- 내 컴퓨터에서 원격 방식 시험: `python design-mcp/design_server.py --http` → `http://127.0.0.1:8000/mcp`

## 연결 · 실행 (로컬 — 레포를 내려받아 쓸 때)

```
pip install mcp                       # 처음 한 번 (mcp 2.x)
claude                                # 수업 폴더 맨 위에서 실행 → 「design MCP 서버를 쓸까요?」 허용
/mcp                                  # design 이 connected 인지 확인
```

연결 설정은 수업 폴더 맨 위 `.mcp.json` 에 있어요.

직접 시험해 보기 (브라우저 화면에서 도구를 눌러 볼 수 있어요):
```
npx @modelcontextprotocol/inspector python design-mcp/design_server.py
```
`python design-mcp/design_server.py` 를 그냥 실행하면 멈춰 있는 게 정상이에요 (Claude 를 기다리는 중) — Ctrl+C 로 끄세요.

## 다른 MCP 와 엮어 쓰기

| 누가 | Claude 에게 |
|---|---|
| 디자이너 | `design 으로 수정 필요한 화면과 이유, 관련 토큰 대비를 보여 줘` |
| 디자이너 | `수정 필요한 화면마다 github 이슈 초안을 만들어 줘. 먼저 보여 줘.` |
| 개발자 | `개발에 넘어온 화면과 각 화면의 컴포넌트 규칙을 정리해 줘` |
| PO | `design 진행률로 notion 「주간 진행」 에 디자인 파트를 정리해 줘. 먼저 보여 줘.` |
| 리뷰 | `github 로 PR 을 읽고 토큰에 없는 색 · 대비 부족 · 문구 규칙 위반을 찾아 리뷰 댓글 초안 보여 줘` |

## 지금 자료로 찾은 개선점

| 조합 (라이트) | 대비 | 판정 |
|---|---|---|
| positive.primary 글자 / 요약 카드 배경 | 2.3:1 | 미달 → 「요약 바」 수정 필요 |
| neutral.tertiary 글자 / 흰 배경 | 3.67:1 | 본문 미달 → 「전체 차량 목록」 빈 상태 문구 |
| atomic.green-30 글자 / 흰 배경 | 6.45:1 | 통과 → 초록 글자 대체 후보 |
| 흰 글자 / brand.primary 버튼 | 4.83:1 | 통과 |

## 2차 프로젝트로 옮길 때
1. `design-mcp/` 폴더를 팀 레포로 복사
2. `screens.csv` → 새 서비스 화면 목록, `design_tokens.csv` · `docs/` → 새 디자인 시스템으로 교체
3. `design_server.py` 는 그대로 (서비스 이름이 코드에 없어요)
4. 팀 레포 `.mcp.json` 에 `"design": { "command": "python", "args": ["design-mcp/design_server.py"] }` 추가
