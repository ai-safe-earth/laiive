DROP POLICY "Service role can update events" ON public.events;
CREATE POLICY "Service role can update events"
ON public.events
FOR UPDATE
TO service_role
USING (true)
WITH CHECK (true);
