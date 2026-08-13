-- Create conversations table to log all chat interactions
CREATE TABLE public.conversations (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id TEXT NOT NULL,
  conversation_type TEXT NOT NULL CHECK (conversation_type IN ('user', 'promoter')),
  message_role TEXT NOT NULL CHECK (message_role IN ('user', 'assistant')),
  message_content TEXT NOT NULL,
  device_type TEXT,
  ip_address TEXT,
  user_agent TEXT,
  language TEXT,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create index for faster queries by session and type
CREATE INDEX idx_conversations_session_id ON public.conversations(session_id);
CREATE INDEX idx_conversations_type ON public.conversations(conversation_type);
CREATE INDEX idx_conversations_created_at ON public.conversations(created_at DESC);

-- Enable Row Level Security
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;

-- Allow anyone to insert conversation logs (for tracking)
CREATE POLICY "Anyone can insert conversation logs"
ON public.conversations
FOR INSERT
WITH CHECK (true);

-- Only allow reading for analysis purposes (you can restrict this further later)
CREATE POLICY "Anyone can view conversation logs"
ON public.conversations
FOR SELECT
USING (true);
