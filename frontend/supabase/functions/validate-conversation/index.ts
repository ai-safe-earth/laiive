import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import "https://deno.land/x/xhr@0.1.0/mod.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

// Rate limiting: track requests per IP
const rateLimitMap = new Map<string, { count: number; resetTime: number }>();
const RATE_LIMIT = 60; // requests per minute (higher for validation)
const RATE_WINDOW = 60000; // 1 minute in ms

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const entry = rateLimitMap.get(ip);

  if (!entry || now > entry.resetTime) {
    rateLimitMap.set(ip, { count: 1, resetTime: now + RATE_WINDOW });
    return true;
  }

  if (entry.count >= RATE_LIMIT) {
    return false;
  }

  entry.count++;
  return true;
}

function getClientIP(req: Request): string {
  return req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
         req.headers.get("x-real-ip") ||
         "unknown";
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  // Rate limit check
  const clientIP = getClientIP(req);
  if (!checkRateLimit(clientIP)) {
    console.log(`Rate limit exceeded for IP: ${clientIP}`);
    return new Response(
      JSON.stringify({ error: "Rate limit exceeded. Please try again later." }),
      { status: 429, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }

  try {
    const { session_id, conversation_type, message_role, message_content, device_type, user_agent, language } = await req.json();

    // Input length validation
    if (message_content && message_content.length > 10000) {
      return new Response(JSON.stringify({ error: 'Message too long' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    // Quick validation
    if (!session_id || !message_content || !conversation_type || !message_role) {
      return new Response(JSON.stringify({ error: 'Missing required fields' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    // Use lightweight LLM to validate if content is legitimate
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) throw new Error("LOVABLE_API_KEY not configured");

    const validationResponse = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${LOVABLE_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash-lite",
        messages: [
          {
            role: "system",
            content: `You are a permissive content filter for a live music events platform. Your job is to ALLOW most content and only BLOCK obvious abuse.

ALWAYS ALLOW:
- Questions about music, concerts, events, artists, venues
- URLs to event pages, ticket sites, or any websites
- Event details, dates, prices, descriptions
- Greetings, casual conversation
- Any language (English, Spanish, Italian, Catalan, etc.)
- Assistant responses

ONLY BLOCK:
- Explicit hate speech or threats
- Obvious spam (repeated identical messages)
- Clearly malicious content

When in doubt, ALLOW. Respond with ONLY 'ALLOW' or 'BLOCK'.`
          },
          {
            role: "user",
            content: `Role: ${message_role}\nContent: ${message_content}`
          }
        ],
        temperature: 0.1,
        max_tokens: 10,
      }),
    });

    if (!validationResponse.ok) {
      console.error("LLM validation failed:", validationResponse.status);
      // On LLM failure, allow the message (fail open to avoid blocking legitimate users)
      return new Response(JSON.stringify({ error: "Validation service unavailable" }), {
        status: 503,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    const validationData = await validationResponse.json();
    const decision = validationData.choices?.[0]?.message?.content?.trim().toUpperCase();

    console.log(`Validation decision for session ${session_id}: ${decision}`);

    if (decision !== "ALLOW") {
      console.log(`Blocked message from session ${session_id}: potential spam/abuse`);
      return new Response(JSON.stringify({ blocked: true, reason: "Content flagged by filter" }), {
        status: 403,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    // Content is valid, insert into database
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? ""
    );

    const { error: insertError } = await supabase.from('conversations').insert({
      session_id,
      conversation_type,
      message_role,
      message_content,
      device_type,
      user_agent,
      language,
    });

    if (insertError) {
      console.error("Insert error:", insertError);
      return new Response(JSON.stringify({ error: "Failed to log conversation" }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    return new Response(JSON.stringify({ success: true }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error("Validation error:", error);
    return new Response(JSON.stringify({ error: error instanceof Error ? error.message : "Unknown error" }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
