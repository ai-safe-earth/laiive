-- Create events table for storing live music events
CREATE TABLE public.events (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  artist TEXT,
  venue TEXT NOT NULL,
  city TEXT NOT NULL,
  latitude DECIMAL(10, 8),
  longitude DECIMAL(11, 8),
  event_date TIMESTAMP WITH TIME ZONE NOT NULL,
  price DECIMAL(10, 2),
  ticket_url TEXT,
  description TEXT,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;

-- Create policy for public read access (events are public)
CREATE POLICY "Events are viewable by everyone"
ON public.events
FOR SELECT
USING (true);

-- Create index for location-based queries
CREATE INDEX idx_events_location ON public.events (latitude, longitude);

-- Create index for date queries
CREATE INDEX idx_events_date ON public.events (event_date);

-- Create function to update timestamps
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = public;

-- Create trigger for automatic timestamp updates
CREATE TRIGGER update_events_updated_at
BEFORE UPDATE ON public.events
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();
