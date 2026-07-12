-- 암호화 컬럼 bytea → text(base64). PostgREST/supabase-js/Node·Python 상호운용 단순화.
-- 형식: base64( iv(12바이트) || ciphertext || GCM태그(16바이트) ). 컬럼이 비어있는 초기 상태에서 안전.

alter table customers        alter column pii_enc        type text using nullif(encode(pii_enc, 'base64'), '');
alter table pos_credentials  alter column enc_blob       type text using encode(enc_blob, 'base64');
alter table pos_credentials  alter column session_cookie type text using nullif(encode(session_cookie, 'base64'), '');
alter table tenants          alter column dek_wrapped    type text using nullif(encode(dek_wrapped, 'base64'), '');
