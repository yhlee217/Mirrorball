'use client';
import { supabaseBrowser } from '@/lib/supabase/client';

export default function LogoutButton() {
  return (
    <button
      className="linkbtn"
      onClick={async () => {
        await supabaseBrowser().auth.signOut();
        location.href = '/login';
      }}
    >
      로그아웃
    </button>
  );
}
