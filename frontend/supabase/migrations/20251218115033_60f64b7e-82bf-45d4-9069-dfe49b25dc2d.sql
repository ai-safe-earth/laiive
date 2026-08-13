-- Add audit fields to events table
ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES auth.users(id),
  ADD COLUMN IF NOT EXISTS modified_by UUID REFERENCES auth.users(id);

-- Add audit fields to venues table
ALTER TABLE public.venues
  ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES auth.users(id),
  ADD COLUMN IF NOT EXISTS modified_by UUID REFERENCES auth.users(id);

-- Add audit fields to bands table
ALTER TABLE public.bands
  ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES auth.users(id),
  ADD COLUMN IF NOT EXISTS modified_by UUID REFERENCES auth.users(id);

-- Add audit fields to festivals table
ALTER TABLE public.festivals
  ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES auth.users(id),
  ADD COLUMN IF NOT EXISTS modified_by UUID REFERENCES auth.users(id);
