-- Remove unrestricted INSERT policy from events table
DROP POLICY IF EXISTS "Anyone can create events" ON public.events;

-- Add new restrictive policy that blocks direct inserts
-- Events should only be created through the validate-event edge function
CREATE POLICY "Events can only be created through validation function"
ON public.events
FOR INSERT
WITH CHECK (false);

-- Add policy to allow the service role (used by edge functions) to insert
CREATE POLICY "Service role can insert validated events"
ON public.events
FOR INSERT
TO service_role
WITH CHECK (true);
