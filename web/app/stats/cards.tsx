import Link from 'next/link';
import { man, manRange, price } from '@/lib/format';
import { BANDS, DOW_MON, type Cohort, type SvcRow, type weekHeat } from '@/lib/trends';
import { MIN_WORKED, type Forecast } from '@/lib/forecast';
import { Empty } from '@/components/empty';
import { Help } from '@/components/help';
import type { Hit } from '@/lib/recommend';
import { HELLO_SINCE, type Effect } from '@/lib/effect';
import { shortDate } from '@/lib/week';

/**
 * 통계 화면의 카드들. 계산은 page.tsx · lib/trends.ts · lib/forecast.ts, 이 파일은 표시만.
 * 카드마다 답 한 줄을 먼저, 차트는 그 아래, 계산 방법·근거는 ? 안에(UX 계획 v3).
 * 색은 한 가지(세이지)의 진하기로만 쓴다 — 값이 많고 적음이지 종류가 아니다.
 * 차트마다 값을 읽는 다른 길(문장·표)을 함께 둔다. 색이나 마우스 올리기에만 기대지 않는다.
 */

/** 카드 제목 — 이름 + 옅은 기간·단위. 줄마다 쓰던 인라인 스타일을 한 곳으로. */
function Title({ name, n }: { name: string; n?: string }) {
  return (
    <div className="ch" style={{ padding: 0, marginBottom: 8 }}>
      {name}
      {n ? <span className="ch-n"> ({n})</span> : null}
    </div>
  );
}

/** 숫자 하나 — 라벨이 위, 숫자가 크게, 그 아래 증감이나 곁말(홈 숫자 띠와 같은 모양). */
function Num({ label, v, sub, dir }: { label: string; v: string; sub?: string; dir?: 'up' | 'down' }) {
  return (
    <div className="num">
      <span>{label}</span>
      <b>{v}</b>
      <span className={dir}>{sub ?? ''}</span>
    </div>
  );
}

const arrow = (d: number) => (d > 0 ? '▲' : '▼');

/**
 * 맨 위 요약 — '이번 달 잘 되고 있나'에 답하는 숫자를 한 카드에. 이번 달(매출·방문·마감 예상)과
 * 지금 손님 기반(활성 고객·선불 잔액), 그리고 할 일. 견주는 법·추정의 근거는 ? 안에.
 */
export function SummaryCard({
  span,
  work,
  rev,
  revDelta,
  visits,
  prevVisits,
  fc,
  bkLeft,
  active,
  prepaid,
  careCount,
  unknownGender,
}: {
  span: string; // '1–11일' — 이달 1일부터 마지막 수집일까지
  work: { now: number; prev: number } | null; // 영업한 날 — 휴무를 정했거나 지난달과 다를 때만
  rev: number;
  revDelta: number | null; // 지난달 같은 기간 대비 %(영업한 날 하루 평균으로)
  visits: number;
  prevVisits: number;
  fc: Forecast;
  bkLeft: number; // 남은 기간 잡힌 예약 — 금액에 섞지 않고 곁에만
  active: { label: string; count: number }[]; // 활성 고객 추이(lib/trends activeTrend)
  prepaid: { sum: number; n: number };
  careCount: number;
  unknownGender: number;
}) {
  const first = active[0];
  const last = active[active.length - 1];
  const aDelta = last.count - first.count;
  const differ = !!work && work.now !== work.prev;
  return (
    <div className="card strip">
      <div className="strip-h">
        이번 달 <span className="sect-n">{span}{work ? ` · 영업 ${work.now}일 (지난달 ${work.prev}일)` : ''}</span>
      </div>
      <Help>
        {span}은 이달 1일부터 마지막 수집일까지예요. 매출 ▲▼는 지난달 같은 날짜까지와 견준 값이에요
        {differ ? ' — 쉰 날이 달라 영업한 날 하루 평균으로 견줬어요' : ''}.{' '}
        {fc.show ? (
          <>
            마감 예상은 영업한 날 하루 평균(선불 충전 제외)에 남은 영업일을 곱하고 충전은 들어온 만큼만 더한 값이에요.
            {fc.low !== null
              ? ` 범위는 지난 ${fc.months}개월 같은 날짜에 이렇게 예상했을 때 실제와 어긋난 폭이에요.`
              : ' 범위는 지난 기록이 3개월 이상 쌓이면 보여요.'}
            {' '}예약은 수집 때까지 잡힌 것뿐이라 금액에 섞지 않았어요.
          </>
        ) : (
          <>마감 예상은 이번 달 영업일이 {MIN_WORKED}일 지나면 보여요{fc.worked ? `(지금 ${fc.worked}일)` : ''}.</>
        )}{' '}
        활성 고객은 최근 90일 안에 다녀가신 손님 수예요.
        {prepaid.n > 0 ? ' 선불 잔액은 손님별 남은 잔액의 합인데, 결제수단이 기록되지 않아 추정이에요.' : ''}
      </Help>
      <div className="strip-r">
        <Num label="매출" v={man(rev)}
          sub={revDelta === null ? '' : revDelta ? `${arrow(revDelta)}${Math.abs(revDelta)}%` : '지난달과 같음'}
          dir={revDelta ? (revDelta > 0 ? 'up' : 'down') : undefined} />
        <Num label="방문" v={visits.toLocaleString()} sub={`지난달 ${prevVisits.toLocaleString()}`} />
        <Num label="마감 예상" v={fc.show ? `약 ${man(fc.center)}` : '-'}
          sub={fc.show ? (fc.low !== null && fc.high !== null ? manRange(fc.low, fc.high) : '') : `영업 ${MIN_WORKED}일부터`} />
      </div>
      {fc.show ? (
        <div className="sum-s">
          지난달 {man(fc.lastMonth)} · 남은 영업 {fc.remaining}일{bkLeft ? ` · 예약 ${bkLeft.toLocaleString()}건` : ''}
        </div>
      ) : null}
      <div className="strip-r sum-2">
        <Num label="활성 고객" v={last.count.toLocaleString()}
          sub={aDelta ? `${arrow(aDelta)}${Math.abs(aDelta).toLocaleString()} · ${first.label} 말보다` : `${first.label} 말과 같음`}
          dir={aDelta > 0 ? 'up' : aDelta < 0 ? 'down' : undefined} />
        {prepaid.n > 0 ? <Num label="선불 잔액" v={`약 ${man(prepaid.sum)}`} sub={`${prepaid.n.toLocaleString()}명`} /> : null}
      </div>
      {/* 할 일 — 통계를 보고 '그래서 뭘 하지'로 바로 건너가게. 숫자는 홈·챙길 고객과 같은 기준 */}
      {careCount > 0 || unknownGender > 0 ? (
        <div className="strip-l">
          {careCount > 0 ? <Link href="/alerts" className="pill main">챙길 고객 <b>{careCount.toLocaleString()}</b></Link> : null}
          {unknownGender > 0 ? (
            <Link href="/customers?filter=nogender" className="pill">성별 미상 <b>{unknownGender.toLocaleString()}</b></Link>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/**
 * 신규 재방문(D2) — 첫 방문 달마다 'N명 중 M명이 90일 안에 다시'.
 * 한 달 신규가 열댓 명이라 %는 한두 명에 흔들린다 → 사람 수로 쓴다. 막대는 그 비율의 모양만.
 */
export function CohortCard({
  cohorts,
  medianDays,
  repeat,
  total,
  vacation,
}: {
  cohorts: Cohort[];
  medianDays: number | null;
  repeat: number; // 평생 두 번 이상 오신 고객(예전 '재방문율'의 분자)
  total: number;
  vacation: boolean; // 휴가를 정했나 — 90일을 그만큼 늘려 셌다고 밝힌다
}) {
  const closed = cohorts.filter((c) => !c.open && c.total > 0);
  const cN = closed.reduce((s, c) => s + c.total, 0);
  const cM = closed.reduce((s, c) => s + c.back, 0);
  const range = closed.length ? `${closed[0].label.replace('월', '')}–${closed[closed.length - 1].label}` : '';
  return (
    <div className="card" style={{ padding: '14px 15px' }}>
      <Title name="신규 재방문" n="90일" />
      <Help>
        첫 방문 달마다, 그 뒤 90일 안에 다시 오신 분 수예요.
        {medianDays !== null ? <> 다시 오신 분은 보통 <b>{medianDays}일</b> 만에 오셨어요.</> : null}
        {' '}90일이 아직 안 지난 달은 &lsquo;진행 중&rsquo;이라 더 늘 수 있어요.
        {vacation ? ' 사이에 휴가가 끼면 그만큼 기간을 늘려서 셌어요.' : ''}
        {total ? ` 전체로 보면 고객 ${total.toLocaleString()}명 중 ${repeat.toLocaleString()}명(${Math.round((repeat / total) * 100)}%)이 두 번 이상 오셨어요.` : ''}
      </Help>
      {cN > 0 ? (
        <div className="coh-h">
          {closed.length > 1 ? range : closed[0].label} 신규 <b>{cN.toLocaleString()}명</b> 중 <b>{cM.toLocaleString()}명</b> 재방문
        </div>
      ) : null}
      {cohorts.map((c) => (
        <div className="coh" key={c.month}>
          <div className="coh-m">{c.label}</div>
          <div className="coh-b" title={`${c.label} 첫 방문 ${c.total}명 중 ${c.back}명이 90일 안에 다시`}>
            <div className="coh-f" style={{ width: c.total ? `${(c.back / c.total) * 100}%` : 0 }} />
          </div>
          <div className="coh-n">
            {c.total ? `${c.total}명 중 ${c.back}명` : '신규 없음'}
            {c.open && c.total ? <span className="coh-o">진행 중</span> : null}
          </div>
        </div>
      ))}
    </div>
  );
}

/** 칸의 진하기 — 가장 붐비는 칸을 5로 놓고 다섯 단계. 0은 칠하지 않는다. */
const level = (n: number, max: number) => (n <= 0 || max <= 0 ? 0 : Math.min(5, Math.ceil((n / max) * 5)));
/** 하루 평균 — 소수 한 자리('1.5'). */
const avg1 = (n: number) => (Math.round(n * 10) / 10).toFixed(1);

/**
 * 바쁜 시간(D4) — 요일 × 시간대, 그 요일에 영업한 날 하루 평균 방문.
 * 휴가 간 주가 끼어도 그 요일이 한산한 요일로 꼽히지 않게 평균으로 본다(lib/trends weekHeat).
 * 정기 휴무 요일은 '휴무'로 따로 칠한다 — 방문이 없는 칸(테두리만)과 뜻이 다르다.
 * 답(가장 붐비는 때 · 가장 한산한 요일)을 먼저 한 줄로, 가장 붐비는 칸에만 숫자, 나머지는 진하기·표로.
 */
export function HeatCard({ heat, hasOff }: { heat: ReturnType<typeof weekHeat>; hasOff: boolean }) {
  let peak = { b: -1, d: -1, v: 0 };
  heat.avg.forEach((row, b) => row.forEach((v, d) => { if (v > peak.v) peak = { b, d, v }; }));
  const dayAvg = DOW_MON.map((_, d) => heat.avg.reduce((s, row) => s + row[d], 0));
  const worked = DOW_MON.map((_, d) => d).filter((d) => heat.days[d] > 0);
  const quiet = worked.length > 1 ? worked.reduce((a, b) => (dayAvg[b] < dayAvg[a] ? b : a)) : null;
  const offDays = DOW_MON.filter((_, d) => heat.off[d]);
  const empty = DOW_MON.filter((_, d) => !heat.off[d] && dayAvg[d] === 0);
  return (
    <div className="card" style={{ padding: '14px 15px' }}>
      <Title name="바쁜 시간" n="6개월" />
      {heat.total ? (
        <>
          <Help>
            칸이 진할수록 그 요일 그 시간에 손님이 많았다는 뜻이에요 — 영업한 날 하루 평균 방문이고, 가장 붐비는 칸에만
            숫자를 적었어요(하루 평균 {avg1(peak.v)}회). 방문 {heat.total.toLocaleString()}회 기준
            {hasOff ? ' · 정기 휴무·휴가는 빼고 영업한 날로 나눴어요' : ''}
            {empty.length ? ` · 방문이 없는 요일 ${empty.join('·')}` : ''}
            {heat.noTime ? ` · 시각이 없는 ${heat.noTime.toLocaleString()}회는 뺐어요` : ''}.
            {' '}한산한 때로 예약을 옮겨드릴 수 있는 분이 있는지 살펴보세요.
          </Help>
          <div className="coh-h">
            <b>{DOW_MON[peak.d]} {BANDS[peak.b]}</b> 가장 붐빔
            {quiet !== null ? <> · <b>{DOW_MON[quiet]}요일</b> 가장 한산</> : null}
          </div>
          <div className="hm" role="img" aria-label="요일과 시간대별 하루 평균 방문. 아래 '표로 보기'에서 숫자로 볼 수 있어요.">
            <div />
            {DOW_MON.map((d) => <div className="hm-h" key={d}>{d}</div>)}
            {BANDS.map((band, b) => [
              <div className="hm-r" key={band}>{band}</div>,
              ...DOW_MON.map((d, di) => {
                const v = heat.avg[b][di];
                if (heat.off[di]) return <div key={band + d} className="hm-c off" title={`${d} · 정기 휴무`} />;
                return (
                  <div key={band + d} className={`hm-c l${level(v, heat.max)}`} title={`${d} ${band} · 하루 평균 ${avg1(v)}회`}>
                    {b === peak.b && di === peak.d ? avg1(v) : null}
                  </div>
                );
              }),
            ])}
          </div>
          <div className="hm-leg">
            <span>적음</span>
            {[1, 2, 3, 4, 5].map((l) => <i key={l} className={`hm-c l${l}`} />)}
            <span>많음</span>
            <i className="hm-c l0" style={{ marginLeft: 8 }} />
            <span>없음</span>
            {offDays.length ? (
              <>
                <i className="hm-c off" style={{ marginLeft: 8 }} />
                <span>휴무</span>
              </>
            ) : null}
          </div>
          <details className="moreh">
            <summary>표로 보기</summary>
            <div className="tablewrap">
              <table className="gtab hm-tab">
                <thead>
                  <tr><th />{DOW_MON.map((d) => <th key={d}>{d}</th>)}</tr>
                </thead>
                <tbody>
                  {BANDS.map((band, b) => (
                    <tr key={band}>
                      <td>{band}</td>
                      {heat.avg[b].map((v, di) => <td key={di}>{heat.off[di] ? '휴' : avg1(v)}</td>)}
                    </tr>
                  ))}
                  <tr>
                    <td>영업일</td>
                    {heat.days.map((n, di) => <td key={di}>{n}</td>)}
                  </tr>
                </tbody>
              </table>
            </div>
          </details>
        </>
      ) : (
        <Empty title="시각이 적힌 방문이 없어요" hint="최근 6개월 방문이 들어오면 채워져요." />
      )}
    </div>
  );
}

/**
 * 월별 매출(최근 6개월) — 진행 중인 달은 점선으로(마지막 며칠이 빠져 '꺾였다'로 읽히지 않게).
 * 휴무를 정했으면 달 이름 아래에 그달 영업한 날.
 */
export function MonthCard({
  months,
  work,
  syncLabel,
}: {
  months: { key: string; label: string; rev: number; partial: boolean }[];
  work: number[] | null; // 달마다 영업한 날 — 휴무를 정했을 때만
  syncLabel: string | null; // '10.11' — 진행 중인 달이 어디까지인지
}) {
  const max = Math.max(1, ...months.map((m) => m.rev));
  return (
    <div className="card" style={{ padding: '14px 15px' }}>
      <Title name="월별 매출" n="만원" />
      <Help>
        * 이번 달은 아직 진행 중이고 {syncLabel ? `${syncLabel} 수집` : '수집 시점'} 기준이라 마지막 며칠이 빠져 있어요 — 다른 달과
        바로 견주지 마세요.{work ? ' 달 이름 아래 숫자는 그달 영업한 날이에요(휴무·휴가 제외).' : ''}
      </Help>
      <div className="bars">
        {months.map((m, i) => (
          <div className="b" key={m.key}>
            <div className="bv">{Math.round(m.rev / 10000).toLocaleString()}</div>
            <div className={`bar2${m.partial ? ' partial' : ''}`} style={{ height: `${Math.round((m.rev / max) * 80) + 3}px` }} />
            <div className="bl">{m.label}{m.partial ? '*' : ''}</div>
            {work ? <div className="bw">{work[i]}일</div> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * 시술별(D5) — 건수·객단가·90일 안에 다시 오신 비율. 단위가 다른 셋이라 차트 하나에 겹치지 않고
 * 표로 둔다. 분모가 작으면 %가 흔들려 10건 미만은 '-'.
 */
export function ServiceCard({ rows, vacation }: { rows: SvcRow[]; vacation: boolean }) {
  return (
    <div className="card" style={{ padding: '14px 15px' }}>
      <Title name="시술별" n="1년" />
      {rows.length ? (
        <>
          <Help>
            다시 옴 = 그 시술 뒤 90일 안에 다시 오신 비율이에요. 최근 90일 시술은 아직 돌아올 시간이 안 돼 빼고,
            10건이 안 되면 비율이 흔들려 &lsquo;-&rsquo;로 둬요. 객단가는 받은 금액 그대로예요(선불 차감 포함).
            {vacation ? ' 사이에 휴가가 끼면 그만큼 90일을 늘려서 셌어요.' : ''}
          </Help>
          <div className="tablewrap">
            <table className="gtab svc-tab">
              <thead>
                <tr><th>시술</th><th>건수</th><th>객단가</th><th>다시 옴</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.service}>
                    <td>{r.service}</td>
                    <td>{r.count.toLocaleString()}</td>
                    <td>{price(r.avg)}</td>
                    <td>
                      {r.base >= 10 ? `${Math.round((r.back / r.base) * 100)}%` : '-'}
                      <span className="sub2">{r.base.toLocaleString()}건 중</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <Empty title="최근 1년 시술 기록 없음" hint="첫 수집이 끝나면 채워져요." />
      )}
    </div>
  );
}

export type GenderStat = {
  M: { n: number; perVisit: number; cycle: number; share: number };
  F: { n: number; perVisit: number; cycle: number; share: number };
  unknown: number; // 미상 = noClue + proxy
  noClue: number; // 성별이 적힌 시술을 받은 적이 없는 고객
  proxy: number; // 남·여가 섞여 대신 결제로 보이는 고객
  manual: number; // 디자이너가 직접 지정한 고객
  rate: number; // 판정률 %
  kids: number;
  total: number;
};

/**
 * 성별(시술명 추정) — 판정된 고객끼리만 견준다. 미상을 0으로 섞으면 평균이 무너지므로 분모에서 빼고,
 * 추정이라 '미상'을 같은 막대에 남겨 판정률이 눈에 보이게 한다.
 */
export function GenderCard({ g }: { g: GenderStat }) {
  const w = (n: number) => `${Math.round((n / g.total) * 100)}%`;
  return (
    <div className="card" style={{ padding: '14px 15px' }}>
      <Title name="성별" n={`시술명 추정 · ${g.rate}% 판정`} />
      <Help>
        메뉴에 성별이 적힌 시술(남자컷·여자컷 등)로 추정했어요
        {g.manual > 0 ? <> — 그중 <b>{g.manual.toLocaleString()}명</b>은 직접 지정</> : null}. 미상
        {' '}{g.unknown.toLocaleString()}명은 성별이 적힌 시술을 받은 적이 없는 고객 {g.noClue.toLocaleString()}명(다운펌·앞머리컷·
        뿌리염색처럼 메뉴에 성별이 없는 시술만 받은 경우)과, 남·여가 섞여 대신 결제로 보이는 고객 {g.proxy.toLocaleString()}명이에요.
        둘 다 아래 비교에서 뺐어요. 카르테에서 성별을 직접 지정하면 바로 반영돼요.
      </Help>
      <div className="gbar">
        <div className="gm" style={{ width: w(g.M.n) }} />
        <div className="gf" style={{ width: w(g.F.n) }} />
        <div className="gu" style={{ width: w(g.unknown) }} />
      </div>
      <div className="glegend">
        <span><i className="gm" />남성 {g.M.n.toLocaleString()}명</span>
        <span><i className="gf" />여성 {g.F.n.toLocaleString()}명</span>
        <span><i className="gu" />미상 {g.unknown.toLocaleString()}명</span>
      </div>
      <div className="tablewrap" style={{ marginTop: 12 }}>
        <table className="gtab">
          <thead>
            <tr><th></th><th>남성</th><th>여성</th></tr>
          </thead>
          <tbody>
            <tr>
              <td>객단가<span className="sub2">방문 1회당</span></td>
              <td>{price(g.M.perVisit)}</td>
              <td>{price(g.F.perVisit)}</td>
            </tr>
            <tr>
              <td>재방문 주기<span className="sub2">중앙값</span></td>
              <td>{g.M.cycle || '-'}일</td>
              <td>{g.F.cycle || '-'}일</td>
            </tr>
            <tr>
              <td>매출 비중<span className="sub2">판정 고객 중</span></td>
              <td>{g.M.share}%</td>
              <td>{g.F.share}%</td>
            </tr>
          </tbody>
        </table>
      </div>
      {g.kids > 0 ? (
        <div className="set-row" style={{ marginTop: 10 }}>
          아동·학생으로 보이는 고객 <b>{g.kids.toLocaleString()}명</b>
          <span style={{ color: 'var(--muted)' }}> ({Math.round((g.kids / g.total) * 100)}%)</span>
        </div>
      ) : null}
    </div>
  );
}

/**
 * 추천 적중률 — 최근 1년 방문마다, 그 전 기록만으로 권했다면 그날 실제로 받았나(lib/recommend backtest).
 * '찍었을 때'는 아무 근거 없이 같은 것을 골랐을 때 맞을 확률 — 추천이 그보다 높아야 쓸모가 있다.
 */
export function RecommendHitCard({ hits }: { hits: { due: Hit; cross: Hit } }) {
  const rows = [
    { name: '때가 된 시술', h: hits.due },
    { name: '함께 권할 것', h: hits.cross },
  ].filter((r) => r.h.n > 0);
  if (!rows.length) return null;
  const pct = (x: number) => `${Math.round(x * 100)}%`;
  return (
    <div className="card" style={{ padding: '14px 15px' }}>
      <Title name="추천 적중률" n="1년" />
      <Help>
        방문마다 그 전 기록만으로 이렇게 권했다면 그날 실제로 받았는지 셌어요. &lsquo;찍었을 때&rsquo;는 아무 근거 없이
        같은 걸 골랐을 때예요 — 추천이 그보다 높아야 쓸모가 있어요. 추천은 카르테와 홈 예약 줄의 &lsquo;권할 것&rsquo;이에요.
      </Help>
      <div className="tablewrap">
        <table className="gtab svc-tab">
          <thead>
            <tr><th>추천</th><th>맞음</th><th>찍었을 때</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name}>
                <td>{r.name}</td>
                <td>
                  {pct(r.h.hit / r.h.n)}
                  <span className="sub2">{r.h.n.toLocaleString()}번 중</span>
                </td>
                <td>{pct(r.h.base)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/**
 * 연락 효과(개선 계획 v4 P2) — 챙길 고객에서 연락한 분이 그 뒤 오셨나. 연락하던 때 첫 방문 손님이었는지
 * (그 전 방문 1회) 2회 이상이었는지로 나누고, 첫 방문 손님은 안부를 보낸 분과 안 보낸 분을 견준다 —
 * 견줄 상대가 있는 곳은 거기뿐이다. 계산은 lib/effect.
 */
export function ContactEffectCard({
  groups,
  hello,
  since,
}: {
  groups: { first: Effect; repeat: Effect };
  hello: { sent: { n: number; back: number }; unsent: { n: number; back: number } };
  since: string | null; // 연락 기록이 시작된 날
}) {
  const rows = [
    { name: '첫 방문 손님', e: groups.first },
    { name: '2회 이상 손님', e: groups.repeat },
  ];
  const pct = (a: number, n: number) => (n ? `${Math.round((a * 100) / n)}%` : '-');
  return (
    <div className="card" style={{ padding: '14px 15px' }}>
      <Title name="연락 효과" n={since ? `${shortDate(since)}부터` : undefined} />
      <Help>
        챙길 고객에서 문자·전화·복사를 한 분 중 연락한 날 뒤에 다녀가신 분(오심)과, 아직 안 오셨지만 예약이 잡힌
        분(예약)이에요. 같은 분께 여러 번 연락해도 한 번 세고, 연락하던 때 방문이 1회였으면 첫 방문 손님이에요.
        방문은 주 1회 수집이라 최대 한 주 늦게 잡혀요. 아래 첫 방문 비교는 {shortDate(HELLO_SINCE)} 이후 첫 방문한
        분들이라, 첫 방문 뒤 시간이 지나야 결과가 나와요 — 석 달쯤 쌓이면 견줄 만해요.
      </Help>
      {groups.first.contacted + groups.repeat.contacted ? (
        <>
          <div className="tablewrap">
            <table className="gtab svc-tab">
              <thead>
                <tr><th>손님</th><th>연락</th><th>오심</th><th>예약</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.name}>
                    <td>{r.name}</td>
                    <td>{r.e.contacted.toLocaleString()}명</td>
                    <td>
                      {r.e.came.toLocaleString()}명<span className="sub2">{pct(r.e.came, r.e.contacted)}</span>
                    </td>
                    <td>{r.e.booked.toLocaleString()}명</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="coh-h" style={{ marginTop: 10, marginBottom: 0 }}>
            첫 방문 안부 — 보낸 분 {hello.sent.n}명 중 <b>{hello.sent.back}명</b> 다시 오심 · 안 보낸 분 {hello.unsent.n}명 중{' '}
            <b>{hello.unsent.back}명</b>
          </div>
        </>
      ) : (
        <Empty title="연락 기록이 아직 없어요" hint="챙길 고객에서 문자·전화를 하면 여기 쌓여요." />
      )}
    </div>
  );
}

/** 누적 — 보고 나서 할 게 없는 평생 숫자라 '더 보기' 안에. */
export function TotalsCard({ customers, revenue, tx }: { customers: number; revenue: number; tx: number }) {
  return (
    <div className="card strip">
      <div className="strip-h">누적</div>
      <div className="strip-r">
        <Num label="고객" v={customers.toLocaleString()} />
        <Num label="매출" v={man(revenue)} sub={`거래 ${tx.toLocaleString()}건`} />
        <Num label="고객당" v={customers ? man(Math.round(revenue / customers)) : '-'} />
      </div>
    </div>
  );
}
