// next/navigation 대역 — 측정은 정적으로 그리기만 해서 이동·새로고침이 필요 없다. 주소 쿼리는 비어 있다.
module.exports = {
  useRouter: () => ({ refresh() {}, push() {}, back() {} }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(''),
};
