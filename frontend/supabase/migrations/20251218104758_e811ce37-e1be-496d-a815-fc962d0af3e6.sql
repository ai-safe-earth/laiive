-- Create venues table
CREATE TABLE public.venues (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  promoter_id UUID NOT NULL REFERENCES public.promoter_profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  capacity INTEGER,
  atmosphere TEXT,
  address TEXT,
  city TEXT,
  location TEXT,
  contact TEXT,
  link TEXT,
  phone TEXT,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create bands table
CREATE TABLE public.bands (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  promoter_id UUID NOT NULL REFERENCES public.promoter_profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  members TEXT,
  year_of_formation INTEGER,
  genre TEXT,
  description TEXT,
  influences TEXT,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create festivals table
CREATE TABLE public.festivals (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  promoter_id UUID NOT NULL REFERENCES public.promoter_profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  first_edition INTEGER,
  genres TEXT,
  past_artists TEXT,
  address TEXT,
  city TEXT,
  location TEXT,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable RLS
ALTER TABLE public.venues ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bands ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.festivals ENABLE ROW LEVEL SECURITY;

-- RLS policies for venues
CREATE POLICY "Users can view their own venues" ON public.venues
  FOR SELECT USING (
    promoter_id IN (SELECT id FROM public.promoter_profiles WHERE user_id = auth.uid())
  );

CREATE POLICY "Users can insert their own venues" ON public.venues
  FOR INSERT WITH CHECK (
    promoter_id IN (SELECT id FROM public.promoter_profiles WHERE user_id = auth.uid())
  );

CREATE POLICY "Users can update their own venues" ON public.venues
  FOR UPDATE USING (
    promoter_id IN (SELECT id FROM public.promoter_profiles WHERE user_id = auth.uid())
  );

CREATE POLICY "Users can delete their own venues" ON public.venues
  FOR DELETE USING (
    promoter_id IN (SELECT id FROM public.promoter_profiles WHERE user_id = auth.uid())
  );

-- RLS policies for bands
CREATE POLICY "Users can view their own bands" ON public.bands
  FOR SELECT USING (
    promoter_id IN (SELECT id FROM public.promoter_profiles WHERE user_id = auth.uid())
  );

CREATE POLICY "Users can insert their own bands" ON public.bands
  FOR INSERT WITH CHECK (
    promoter_id IN (SELECT id FROM public.promoter_profiles WHERE user_id = auth.uid())
  );

CREATE POLICY "Users can update their own bands" ON public.bands
  FOR UPDATE USING (
    promoter_id IN (SELECT id FROM public.promoter_profiles WHERE user_id = auth.uid())
  );

CREATE POLICY "Users can delete their own bands" ON public.bands
  FOR DELETE USING (
    promoter_id IN (SELECT id FROM public.promoter_profiles WHERE user_id = auth.uid())
  );

-- RLS policies for festivals
CREATE POLICY "Users can view their own festivals" ON public.festivals
  FOR SELECT USING (
    promoter_id IN (SELECT id FROM public.promoter_profiles WHERE user_id = auth.uid())
  );

CREATE POLICY "Users can insert their own festivals" ON public.festivals
  FOR INSERT WITH CHECK (
    promoter_id IN (SELECT id FROM public.promoter_profiles WHERE user_id = auth.uid())
  );

CREATE POLICY "Users can update their own festivals" ON public.festivals
  FOR UPDATE USING (
    promoter_id IN (SELECT id FROM public.promoter_profiles WHERE user_id = auth.uid())
  );

CREATE POLICY "Users can delete their own festivals" ON public.festivals
  FOR DELETE USING (
    promoter_id IN (SELECT id FROM public.promoter_profiles WHERE user_id = auth.uid())
  );

-- Triggers for updated_at
CREATE TRIGGER update_venues_updated_at
  BEFORE UPDATE ON public.venues
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_bands_updated_at
  BEFORE UPDATE ON public.bands
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_festivals_updated_at
  BEFORE UPDATE ON public.festivals
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();
