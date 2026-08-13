-- Allow anyone to insert events (for promoters)
CREATE POLICY "Anyone can create events"
ON public.events
FOR INSERT
WITH CHECK (true);
