// HandSOS 의 예약·매출 시각은 한국 현지시각(KST) 문자열이다. 배포 런타임(Cloudflare 엣지)은 UTC 라서
// new Date().toISOString() 으로 '오늘'을 구하면 한국 새벽 00~09시에 날짜가 하루 밀린다.
// 예약 표시는 KST 기준으로 계산해야 정확하다.

const KST_OFFSET = 9 * 60 * 60 * 1000;

/** KST 기준 현재 날짜·시각. { date: 'YYYY-MM-DD', time: 'HH:MM' } */
export function kstNow(): { date: string; time: string } {
  const iso = new Date(Date.now() + KST_OFFSET).toISOString();
  return { date: iso.slice(0, 10), time: iso.slice(11, 16) };
}

/** KST 기준 오늘 + n일의 날짜(YYYY-MM-DD). */
export function kstDatePlus(days: number): string {
  return new Date(Date.now() + KST_OFFSET + days * 86400000).toISOString().slice(0, 10);
}

/** 아직 지나지 않은 예약인가 — 오늘이면 시간까지 비교(10:00 예약은 11:00 이 지나면 제외). */
export function isUpcoming(date: string | null | undefined, time: string | null | undefined): boolean {
  if (!date) return false;
  const now = kstNow();
  if (date > now.date) return true;
  if (date < now.date) return false;
  return !time || time >= now.time;
}
