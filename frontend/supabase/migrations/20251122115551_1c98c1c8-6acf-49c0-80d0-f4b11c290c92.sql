-- Remove public SELECT policy from conversations table
DROP POLICY IF EXISTS "Anyone can view conversation logs" ON public.conversations;
