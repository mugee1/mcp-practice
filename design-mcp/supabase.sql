-- design MCP 상태 저장소 — 새 Supabase 프로젝트의 SQL Editor 에 통째로 붙여 넣고 Run.
-- 2차 프로젝트에서도 이 파일을 그대로 쓰고, 맨 아래 「처음 화면 목록」만 바꾸세요.

-- 1) 화면 상태 표
create table if not exists public.design_screens (
  name        text primary key,
  status      text not null check (status in ('기획 중','진행 중','완료','수정 필요')),
  handoff     text not null default '대기' check (handoff in ('넘김','대기')),
  owner       text not null default '디자인',
  components  text not null default '',
  tokens      text not null default '',
  memo        text not null default '',
  updated_at  timestamptz not null default now(),
  updated_by  text not null default ''
);

-- 2) 변경 기록 (누가 · 언제 · 무엇을)
create table if not exists public.design_screen_history (
  id          bigint generated always as identity primary key,
  screen      text not null references public.design_screens(name) on update cascade,
  field       text not null,
  old_value   text,
  new_value   text,
  changed_by  text not null,
  note        text not null default '',
  changed_at  timestamptz not null default now()
);

-- 3) 공개 키(anon · publishable)로는 못 읽고 못 쓰게: RLS 켜고 정책 없음 → 서버 비밀 키로만 접근
alter table public.design_screens enable row level security;
alter table public.design_screen_history enable row level security;
revoke all on public.design_screens, public.design_screen_history from anon, authenticated;

-- 4) 상태 바꾸기 + 기록 남기기를 한 번에 (중간에 실패하면 둘 다 안 바뀜)
create or replace function public.design_update_screen(
  p_name text, p_by text,
  p_status text default null, p_handoff text default null, p_memo text default null, p_note text default ''
) returns public.design_screens
language plpgsql
set search_path = public
as $$
declare
  old public.design_screens;
  new_row public.design_screens;
begin
  select * into old from design_screens where name = p_name for update;
  if not found then
    raise exception '화면 「%」 이(가) 없어요', p_name using errcode = 'P0002';
  end if;

  update design_screens set
    status     = coalesce(p_status, status),
    handoff    = coalesce(p_handoff, handoff),
    memo       = coalesce(p_memo, memo),
    updated_at = now(),
    updated_by = p_by
  where name = p_name
  returning * into new_row;

  if p_status is not null and p_status is distinct from old.status then
    insert into design_screen_history(screen, field, old_value, new_value, changed_by, note)
    values (p_name, '디자인 상태', old.status, new_row.status, p_by, p_note);
  end if;
  if p_handoff is not null and p_handoff is distinct from old.handoff then
    insert into design_screen_history(screen, field, old_value, new_value, changed_by, note)
    values (p_name, '개발 넘김', old.handoff, new_row.handoff, p_by, p_note);
  end if;
  if p_memo is not null and p_memo is distinct from old.memo then
    insert into design_screen_history(screen, field, old_value, new_value, changed_by, note)
    values (p_name, '메모', old.memo, new_row.memo, p_by, p_note);
  end if;
  return new_row;
end $$;

revoke all on function public.design_update_screen(text,text,text,text,text,text) from public, anon, authenticated;

-- 5) 처음 화면 목록 (지금 screens.csv 내용 — 2차 프로젝트에서는 이 부분만 바꾸세요)
insert into public.design_screens (name, status, handoff, owner, components, tokens, memo, updated_by) values
('요약 바','수정 필요','넘김','디자인','카드','positive.primary · brand.primary · negative.strong · neutral.tertiary · background.neutral.secondary','「사용가능」 초록 숫자가 요약 카드 배경에서 대비 미달 - 글자색 교체 검토','screens.csv'),
('지금 사용중 목록','완료','넘김','디자인','카드 · 상태 배지 · 버튼','brand.primary · negative.strong · line.negative.primary · line.neutral.primary','','screens.csv'),
('전체 차량 목록','수정 필요','넘김','디자인','검색창 · 필터 · 상태 배지 · 버튼','brand.primary · positive.primary · neutral.tertiary · line.neutral.secondary','빈 상태 안내 문구가 neutral.tertiary라 본문 대비 미달','screens.csv'),
('빌리기 창','완료','넘김','디자인','팝업 창 · 입력창 · 안내 메시지','brand.primary · negative.strong','','screens.csv'),
('반납 창','완료','넘김','디자인','팝업 창 · 입력창','brand.primary · negative.strong','','screens.csv'),
('앱 아이콘 (PWA)','완료','넘김','디자인','-','brand.primary · positive.primary','11/17 작업 - 안드로이드 · iOS · 파비콘','screens.csv'),
('다크 모드 점검','진행 중','대기','디자인','전체','다크 값 전체','[연습용 가짜 항목] 다크 모드 대비 확인 중','screens.csv'),
('차량 예약 화면','기획 중','대기','디자인','미정','미정','[연습용 가짜 항목] 미리 예약 기능 - PRD 확정 전','screens.csv')
on conflict (name) do nothing;
