import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/hooks/useAuth';

const WEEKLY_LIMIT = 5;

/** Get Monday of current week (UTC) */
function getWeekStart(): string {
  const now = new Date();
  const day = now.getUTCDay();
  const diff = now.getUTCDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), diff));
  return monday.toISOString().split('T')[0];
}

async function fetchQueryCount(userId: string): Promise<number> {
  const weekStart = getWeekStart();
  const { data } = await supabase
    .from('user_query_usage')
    .select('query_count')
    .eq('user_id', userId)
    .eq('week_start', weekStart)
    .maybeSingle();

  return data?.query_count ?? 0;
}

export function QueryCounter() {
  const { user, isPromoter } = useAuth();

  const { data: queryCount = 0, isLoading } = useQuery({
    queryKey: ['queryUsage', user?.id],
    queryFn: () => fetchQueryCount(user!.id),
    enabled: !!user && !isPromoter,
    staleTime: 60_000, // cache for 1 minute
  });

  if (isPromoter || isLoading || !user) return null;

  const remaining = Math.max(0, WEEKLY_LIMIT - queryCount);
  const isLow = remaining <= 2;
  const isExhausted = remaining === 0;

  return (
    <div className={`text-xs px-2 py-1 rounded-full border ${
      isExhausted
        ? 'bg-destructive/10 border-destructive/30 text-destructive'
        : isLow
          ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-500'
          : 'bg-card border-border/50 text-muted-foreground'
    }`}>
      {remaining}/{WEEKLY_LIMIT} queries
    </div>
  );
}

export function useQueryLimit() {
  const { user, isPromoter } = useAuth();
  const [optimisticExtra, setOptimisticExtra] = useState(0);

  const { data: serverCount = 0, isLoading } = useQuery({
    queryKey: ['queryUsage', user?.id],
    queryFn: () => fetchQueryCount(user!.id),
    enabled: !!user,
    staleTime: 60_000,
  });

  const queryCount = serverCount + optimisticExtra;
  const canQuery = isPromoter || queryCount < WEEKLY_LIMIT;
  const remaining = Math.max(0, WEEKLY_LIMIT - queryCount);

  const incrementCount = () => {
    if (!isPromoter) {
      setOptimisticExtra((prev) => prev + 1);
    }
  };

  return { canQuery, remaining, isLoading, incrementCount, isPromoter };
}
