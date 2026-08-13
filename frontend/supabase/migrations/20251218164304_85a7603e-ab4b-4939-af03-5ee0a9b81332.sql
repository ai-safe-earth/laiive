-- Add DELETE policy for promoter_profiles to allow users to delete their own data (GDPR compliance)
CREATE POLICY "Users can delete their own promoter profile"
ON public.promoter_profiles
FOR DELETE
USING (auth.uid() = user_id);
