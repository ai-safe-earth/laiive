-- Allow service role to update events (for duplicate prevention)
CREATE POLICY "Service role can update events"
ON public.events
FOR UPDATE
USING (true)
WITH CHECK (true);
