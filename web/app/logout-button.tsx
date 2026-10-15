'use client';
import { supabaseBrowser } from '@/lib/supabase/client';

export default function LogoutButton({ label = '로그아웃' }: { label?: string }) {
  return (
    <button
      className="linkbtn"
      onClick={async () => {
        await supabaseBrowser().auth.signOut();
        location.href = '/login';
      }}
    >
      {label}
    </button>
  );
}
