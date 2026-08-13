-- Create promoter_profiles table for professional information
CREATE TABLE public.promoter_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL UNIQUE,
  first_name text NOT NULL,
  last_name text NOT NULL,
  city text NOT NULL,
  industry_role text NOT NULL,
  managed_entity text NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL
);

-- Enable RLS
ALTER TABLE public.promoter_profiles ENABLE ROW LEVEL SECURITY;

-- Users can view their own promoter profile
CREATE POLICY "Users can view their own promoter profile"
  ON public.promoter_profiles FOR SELECT
  USING (auth.uid() = user_id);

-- Users can update their own promoter profile
CREATE POLICY "Users can update their own promoter profile"
  ON public.promoter_profiles FOR UPDATE
  USING (auth.uid() = user_id);

-- Service role can insert promoter profiles
CREATE POLICY "Service role can insert promoter profiles"
  ON public.promoter_profiles FOR INSERT
  WITH CHECK (true);

-- Add updated_at trigger
CREATE TRIGGER update_promoter_profiles_updated_at
  BEFORE UPDATE ON public.promoter_profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
