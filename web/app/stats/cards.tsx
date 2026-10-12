import { price } from '@/lib/format';
import { BANDS, DOW_MON, type Cohort, type SvcRow, type weekHeat } from '@/lib/trends';
import { Empty } from '@/components/empty';

/**
 * 통계를 '변화'로(UX 계획 P2) 바꾼 카드들. 계산은 lib/trends.ts, 이 파일은 표시만.
 * 색은 한 가지(세이지)의 진하기로만 쓴다 — 값이 많고 적음이지 종류가 아니다.
 * 차트마다 값을 읽는 다른 길(문장·표)을 함께 둔다. 색이나 마우스 올리기에만 기대지 않는다.
 */

const muted = { fontWeight: 400, color: 'var(--muted)', fontSize: 10 } as const;

/** 활성 고객 타일(D3) — 지금 숫자 + 처음 점 대비 증감 + 6점 추이. 늘면 좋은 숫자라 늘면 초록. */
export function ActiveTile({ trend }: { trend: { label: string; count: number }[] }) {
  const first = trend[0];
  const last = trend[trend.length - 1];
  const delta = last.count - first.count;
  const dir = delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat';
  return (
    <div className="stat">
      <div className="sn">{last.count.toLocaleString()}명</div>
      <div className="sl">최근 90일 방문 고객</div>
      <div className={'sd ' + dir}>
        {delta === 0 ? `${first.label} 말과 같아요` : `${delta > 0 ? '▲' : '▼'} ${Math.abs(delta).toLocaleString()}명 · ${first.label} 말보다`}
      </div>
      <Spark points={trend} />
    </div>
  );
}

/** 추이 선 — 흐린 선에 마지막 점만 강조. 값은 마우스를 올리거나(제목) 화면 읽기(aria)로 다 읽힌다. */
function Spark({ points }: { points: { label: string; count: number }[] }) {
  const w = 120;
  const h = 30;
  const pad = 5;
  const vs = points.map((p) => p.count);
  const lo = Math.min(...vs);
  const hi = Math.max(...vs);
  const x = (i: number) => pad + (i * (w - 2 * pad)) / Math.max(1, points.length - 1);
  const y = (v: number) => (hi === lo ? h / 2 : pad + (1 - (v - lo) / (hi - lo)) * (h - 2 * pad));
  const said = points.map((p) => `${p.label} ${p.count.toLocaleString()}명`).join(' · ');
  const n = points.length - 1;
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} role="img" aria-label={said}>
      <title>{said}</title>
      <polyline
        points={points.map((p, i) => `${x(i)},${y(p.count)}`).join(' ')}
        fill="none"
        stroke="#B4B2A9"
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      <circle cx={x(n)} cy={y(points[n].count)} r={4} fill="var(--accent)" stroke="var(--soft)" strokeWidth={2} />
    </svg>
  );
}

/**
 * 신규 손님이 다시 오나(D2) — 첫 방문 달마다 'N명 중 M명이 90일 안에 다시'.
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
  const range = closed.length ? `${closed[0].label.replace('월', '')}~${closed[closed.length - 1].label}` : '';
  return (
    <div className="card" style={{ padding: '14px 15px' }}>
      <div className="ch" style={{ padding: 0, marginBottom: 6 }}>
        신규 손님이 다시 오나 <span style={muted}>· 첫 방문 뒤 90일 안에</span>
      </div>
      {cN > 0 ? (
        <div className="coh-h">
          {closed.length > 1 ? range : closed[0].label} 신규 <b>{cN.toLocaleString()}명</b> 중{' '}
          <b>{cM.toLocaleString()}명</b>이 다시 오셨어요
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
      <p className="note">
        {medianDays !== null ? <>다시 오신 분은 첫 방문 뒤 보통 <b>{medianDays}일</b> 만에 오셨어요. </> : null}
        90일이 아직 안 지난 달은 &lsquo;진행 중&rsquo;이라 더 늘 수 있어요.
        {vacation ? ' 사이에 휴가가 끼면 그만큼 기간을 늘려서 셌어요.' : ''}
        {total ? ` 전체로 보면 고객 ${total.toLocaleString()}명 중 ${repeat.toLocaleString()}명(${Math.round((repeat / total) * 100)}%)이 두 번 이상 오셨어요.` : ''}
      </p>
    </div>
  );
}

/** 칸의 진하기 — 가장 붐비는 칸을 5로 놓고 다섯 단계. 0은 칠하지 않는다. */
const level = (n: number, max: number) => (n <= 0 || max <= 0 ? 0 : Math.min(5, Math.ceil((n / max) * 5)));
/** 하루 평균 — 소수 한 자리('1.5'). */
const avg1 = (n: number) => (Math.round(n * 10) / 10).toFixed(1);

/**
 * 언제 바쁘고 언제 한가하지(D4) — 요일 × 시간대, 그 요일에 영업한 날 하루 평균 방문.
 * 휴가 간 주가 끼어도 그 요일이 한산한 요일로 꼽히지 않게 평균으로 본다(lib/trends weekHeat).
 * 정기 휴무 요일은 '휴무'로 따로 칠한다 — 방문이 없는 칸(테두리만)과 뜻이 다르다.
 * 가장 붐비는 칸에만 숫자를 적고 나머지는 진하기·문장·표로 읽는다.
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
      <div className="ch" style={{ padding: 0, marginBottom: 10 }}>
        언제 바쁜가 <span style={muted}>· 최근 6개월 · 하루 평균</span>
      </div>
      {heat.total ? (
        <>
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
          <p className="note">
            가장 붐비는 때는 <b>{DOW_MON[peak.d]} {BANDS[peak.b]}</b>(하루 평균 {avg1(peak.v)}회)
            {quiet !== null ? <>, 가장 한산한 요일은 <b>{DOW_MON[quiet]}요일</b>이에요</> : '예요'}.
            한산한 때로 예약을 옮겨드릴 수 있는 분이 있는지 살펴보세요.
            {' '}방문 {heat.total.toLocaleString()}회 기준
            {hasOff ? ' · 정기 휴무·휴가는 빼고 영업한 날로 나눴어요' : ''}
            {empty.length ? ` · 방문이 없는 요일 ${empty.join('·')}` : ''}
            {heat.noTime ? ` · 시각이 없는 ${heat.noTime.toLocaleString()}회는 뺐어요` : ''}.
          </p>
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
        <Empty title="시각이 적힌 방문이 없어요" hint="최근 6개월 방문 기록이 들어오면 요일·시간대별로 채워져요." />
      )}
    </div>
  );
}

/**
 * 어떤 시술이 남는 장사인가(D5) — 건수·객단가·90일 안에 다시 오신 비율. 단위가 다른 셋이라
 * 차트 하나에 겹치지 않고 표로 둔다. 분모가 작으면 %가 흔들려 10건 미만은 '-'.
 */
export function ServiceCard({ rows, vacation }: { rows: SvcRow[]; vacation: boolean }) {
  return (
    <div className="card" style={{ padding: '14px 15px' }}>
      <div className="ch" style={{ padding: 0, marginBottom: 6 }}>
        시술별 <span style={muted}>· 최근 1년</span>
      </div>
      {rows.length ? (
        <>
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
          <p className="note">
            다시 옴 = 그 시술 뒤 90일 안에 다시 오신 비율이에요. 최근 90일 시술은 아직 돌아올 시간이 안 돼 빼고,
            10건이 안 되면 비율이 흔들려 &lsquo;-&rsquo;로 둡니다. 객단가는 받은 금액 그대로예요(선불 차감 포함).
            {vacation ? ' 사이에 휴가가 끼면 그만큼 90일을 늘려서 셌어요.' : ''}
          </p>
        </>
      ) : (
        <Empty title="시술 데이터가 없어요" hint="최근 1년 시술 기록이 없어요. 첫 수집이 끝나면 채워져요." />
      )}
    </div>
  );
}
