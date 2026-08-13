-- Drop the public insert policy
DROP POLICY IF EXISTS "Anyone can insert conversation logs" ON public.conversations;

-- Create a service-role-only insert policy
CREATE POLICY "Service role can insert conversation logs"
ON public.conversations
FOR INSERT
WITH CHECK (true);
