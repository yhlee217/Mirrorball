#!/usr/bin/env bash
# RLS 격리 회귀 테스트 (코드리뷰 C1) — 임시 Postgres 클러스터에 Supabase auth 를 스텁해
# 0001 스키마를 적용하고, '멤버십 self-insert 로 남의 테넌트 가입' 취약점이
#   · 0007 적용 前: 허용됨(취약점 실재 증명)
#   · 0007 적용 後: 차단됨(수정 증명)
# 임을 단언한다. Supabase 특화(auth.uid()/역할/GRANT)를 최소 재현.
#
# 사용: bash tests/rls/run_rls_test.sh   (psql/initdb 필요)
set -euo pipefail

# initdb/pg_ctl 은 데비안에서 PATH 밖(/usr/lib/postgresql/<ver>/bin)에 있음 → 최신 버전 bin 추가
PGBIN=""
for d in /usr/lib/postgresql/*/bin; do [ -d "$d" ] && PGBIN="$d"; done
[ -n "$PGBIN" ] && PATH="$PGBIN:$PATH"
export PATH

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MIG="$ROOT/supabase/migrations"
WORK="$(mktemp -d)"
export PGDATA="$WORK/pgdata"
export PGHOST="$WORK"          # unix 소켓 디렉터리(포트 충돌 회피)
export PGDATABASE=postgres
export PGUSER=postgres

# Postgres 는 root 로 실행 불가 → 비권한 사용자 필요. 있으면 재사용, 없으면 생성(root 일 때만).
PGRUN="${SUDO_USER:-postgres_test}"
if [ "$(id -u)" = "0" ]; then
  id "$PGRUN" >/dev/null 2>&1 || useradd -m "$PGRUN" >/dev/null 2>&1 || true
  chown -R "$PGRUN" "$WORK"
  RUN() { su -s /bin/bash "$PGRUN" -c "export PATH='$PATH'; $1"; }
else
  RUN() { bash -c "$1"; }        # 이미 비권한 사용자면 그대로
fi

cleanup() { RUN "pg_ctl -D '$PGDATA' -m immediate stop" >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT

echo "▶ 임시 클러스터 초기화…"
RUN "initdb -U postgres --auth=trust -D '$PGDATA'" >/dev/null
# TCP 끄고 유닉스 소켓만(격리)
RUN "pg_ctl -D '$PGDATA' -o \"-c listen_addresses='' -c unix_socket_directories='$WORK'\" -w start" >/dev/null

PSQL="psql -v ON_ERROR_STOP=1 -q -h $WORK -U postgres -d postgres"

echo "▶ Supabase 환경 스텁(auth 스키마·역할·GRANT)…"
$PSQL >/dev/null <<'SQL'
create extension if not exists pgcrypto;
-- 역할(Supabase: anon/authenticated/service_role)
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
-- auth 스키마 + uid() 스텁(세션 GUC test.uid 로 '로그인 사용자' 지정)
create schema auth;
create table auth.users(id uuid primary key);
create or replace function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('test.uid', true), '')::uuid
$$;
SQL

apply() { echo "  · 적용: $(basename "$1")"; $PSQL -f "$1" >/dev/null; }
apply "$MIG/0001_init.sql"
# Supabase 는 public 테이블을 anon/authenticated 에 GRANT(권한 게이트는 RLS). 그대로 재현.
$PSQL >/dev/null <<'SQL'
grant usage on schema public to anon, authenticated;
grant all on all tables in schema public to anon, authenticated;
SQL

echo "▶ 픽스처: 피해자 테넌트 V, 공격자 U_a(테넌트 A 소속)…"
$PSQL >/dev/null <<'SQL'
insert into auth.users(id) values
  ('00000000-0000-0000-0000-0000000000a1'),   -- 공격자
  ('00000000-0000-0000-0000-0000000000f1');   -- 피해자
insert into tenants(id, slug, salon_name) values
  ('aaaaaaaa-0000-0000-0000-00000000000a','attacker','A살롱'),
  ('bbbbbbbb-0000-0000-0000-0000000000bb','victim','V살롱');
insert into memberships(tenant_id, user_id, role) values
  ('aaaaaaaa-0000-0000-0000-00000000000a','00000000-0000-0000-0000-0000000000a1','owner'),
  ('bbbbbbbb-0000-0000-0000-0000000000bb','00000000-0000-0000-0000-0000000000f1','owner');
-- 피해자 테넌트에 고객 1명(장악 시 노출 대상)
insert into customers(tenant_id, ext_id, visit_count) values
  ('bbbbbbbb-0000-0000-0000-0000000000bb','c-secret',9);
SQL

# 공격자 세션으로 'V 에 self-insert' 시도 → 성공 여부를 boolean 으로 반환
attack_inserts() {
$PSQL -t -A <<'SQL'
set role authenticated;
set test.uid = '00000000-0000-0000-0000-0000000000a1';
do $$
declare inserted boolean := false;
begin
  begin
    insert into memberships(tenant_id, user_id, role)
      values ('bbbbbbbb-0000-0000-0000-0000000000bb','00000000-0000-0000-0000-0000000000a1','owner');
    inserted := true;
  exception when insufficient_privilege then
    inserted := false;   -- RLS(WITH CHECK) 차단
  end;
  raise notice 'ATTACK_INSERTED=%', inserted;
  -- 흔적 정리(성공했다면 롤백 대신 삭제는 못 하므로 예외 무시)
  begin delete from memberships where tenant_id='bbbbbbbb-0000-0000-0000-0000000000bb' and user_id='00000000-0000-0000-0000-0000000000a1'; exception when others then null; end;
end $$;
reset role;
SQL
}

echo
echo "▶ [0007 적용 前] 취약점 실재 확인 — self-insert 가 성공해야(취약)…"
BEFORE="$(attack_inserts 2>&1 | grep -o 'ATTACK_INSERTED=[a-z]*' | tail -1)"
echo "   결과: $BEFORE"

echo "▶ 0007 적용(수정)…"
# 공격자가 남긴 멤버십이 있으면 제거(소유자 권한)
$PSQL >/dev/null -c "delete from memberships where tenant_id='bbbbbbbb-0000-0000-0000-0000000000bb' and user_id='00000000-0000-0000-0000-0000000000a1';"
apply "$MIG/0007_fix_rls_membership.sql"

echo "▶ [0007 적용 後] self-insert 가 차단돼야(수정)…"
AFTER="$(attack_inserts 2>&1 | grep -o 'ATTACK_INSERTED=[a-z]*' | tail -1)"
echo "   결과: $AFTER"

# 합법 경로 회귀: 공격자는 여전히 '자기 멤버십'은 조회 가능해야
LEGIT="$($PSQL -t -A <<'SQL'
set role authenticated;
set test.uid = '00000000-0000-0000-0000-0000000000a1';
select count(*) from memberships;   -- 자기(A) 1건만 보여야
reset role;
SQL
)"
echo "▶ 합법 조회(공격자 자기 멤버십): $LEGIT 건(기대 1)"

echo
FAIL=0
[ "$BEFORE" = "ATTACK_INSERTED=t" ]  || { echo "✗ 사전조건 실패: 취약점 재현 안 됨($BEFORE)"; FAIL=1; }
[ "$AFTER"  = "ATTACK_INSERTED=f" ] || { echo "✗ 수정 실패: 0007 후에도 self-insert 성공($AFTER)"; FAIL=1; }
[ "$LEGIT" = "1" ]                      || { echo "✗ 회귀: 자기 멤버십 조회 깨짐($LEGIT)"; FAIL=1; }
if [ "$FAIL" = "0" ]; then
  echo "✓ PASS — 취약점 존재→0007 이 차단, 합법 조회 유지"
else
  echo "✗ FAIL"; exit 1
fi
