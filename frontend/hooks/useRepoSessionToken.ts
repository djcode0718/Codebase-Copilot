'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';

export function useRepoSessionToken() {
  const [token, setToken] = useState('');

  useEffect(() => {
    let mounted = true;
    async function loadSessionToken() {
      try {
        const { data } = await createClient().auth.getSession();
        if (!mounted) return;
        setToken(data.session?.access_token ?? '');
      } catch {
        if (!mounted) return;
        setToken('');
      }
    }
    void loadSessionToken();
    return () => {
      mounted = false;
    };
  }, []);

  return token;
}
