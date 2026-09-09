import rules from './tx-rules.json';
// POS 메뉴명을 '고객에게 보낼 문구'용으로 부드럽게 다듬는다.
//   남자컷(부원장) → 커트 / 여자컷(원장)+다운펌 → 커트 + 다운펌 / 남자콜드펌 → 콜드펌
// 직급((원장)·(부원장)…)·성별 접두(남자·여자…)는 가격표 느낌이라 빼고, '컷'은 더 흔한 '커트'로 통일.
// 선불충전·부가재료처럼 시술이 아닌 항목은 빈 문자열을 돌려줘 문구가 '지난 시술'로 폴백하게 한다
// ("지난 원충전 관리할 시기예요" 같은 어색한 문장 방지).
// 카르테·통계 등 내부 화면은 원본 메뉴명을 그대로 써야 하므로 여기서만 사용한다.

const TIER = /\s*\((?:원장|부원장|실장|점장|수석|팀장|디자이너|인턴)[^)]*\)/g;
const PROMO = /\s*[[<][^\]>]*(?:이벤트|할인)[^\]>]*[\]>]\s*/g;
const BRACKET = /\s*\[[^\]]*\]\s*/g; // [330,000] 같은 금액·코드 표기
const CUT = /(?:남자|여자|남성|여성|주니어|학생|아동|어린이)\s*(?:컷|커트)/g;
const GENDER = /^(?:남자|여자|남성|여성)\s*/;
// 시술이 아닌 항목 — 거래 분류와 같은 어휘를 쓴다(tx-rules.json).
// 여기만 따로 두면 '선불권' 같은 걸 한쪽에만 추가하는 일이 생긴다.
const NOT_SERVICE = new RegExp(
  Object.values(rules.patterns).flat().join('|'),
);

export function friendlyService(s: string | null | undefined): string {
  if (!s) return '';
  let t = String(s);
  t = t.replace(TIER, '');
  t = t.replace(PROMO, ' ');
  t = t.replace(BRACKET, ' ');
  t = t.replace(CUT, '커트');
  t = t.replace(/컷/g, '커트'); // 남은 단독 '컷'('커트'와 글자가 달라 중복 치환 없음)
  t = t.replace(/\s+/g, ' ').trim();
  t = t.replace(GENDER, ''); // 커트 외 시술의 성별 접두(남자콜드펌 → 콜드펌)
  t = t.replace(/\s*\+\s*/g, ' + ');
  t = t.replace(/\s+/g, ' ').trim();
  if (!t || NOT_SERVICE.test(t)) return '';
  return t;
}
