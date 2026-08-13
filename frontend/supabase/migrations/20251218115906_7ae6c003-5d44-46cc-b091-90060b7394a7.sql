-- Add country column to venues table
ALTER TABLE public.venues
ADD COLUMN country text;

-- Add country column to festivals table
ALTER TABLE public.festivals
ADD COLUMN country text;

-- Add country column to bands table (for band origin)
ALTER TABLE public.bands
ADD COLUMN country text;
