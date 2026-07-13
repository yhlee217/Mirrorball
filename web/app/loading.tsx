export default function Loading() {
  return (
    <main className="wrap">
      <div className="bar">
        <div className="ttl" style={{ color: 'var(--muted)' }}>불러오는 중…</div>
      </div>
      <div className="body">
        <div className="sk" style={{ height: 54, marginBottom: 16 }} />
        <div className="sk" style={{ height: 66, marginBottom: 14 }} />
        <div className="sk" style={{ height: 120, marginBottom: 13 }} />
        <div className="sk" style={{ height: 120 }} />
      </div>
    </main>
  );
}
