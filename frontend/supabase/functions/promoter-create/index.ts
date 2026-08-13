import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.81.1";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

// Rate limiting: track requests per IP
const rateLimitMap = new Map<string, { count: number; resetTime: number }>();
const RATE_LIMIT = 30; // requests per minute
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
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  // Rate limit check
  const clientIP = getClientIP(req);
  if (!checkRateLimit(clientIP)) {
    console.log(`Rate limit exceeded for IP: ${clientIP}`);
    return new Response(
      JSON.stringify({ error: "Rate limit exceeded. Please try again later." }),
      { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }

  try {
    // Verify JWT authentication
    const authHeader = req.headers.get('authorization');
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return new Response(
        JSON.stringify({ error: "Authentication required. Please sign in to create events." }),
        { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const token = authHeader.replace('Bearer ', '');

    // Create auth client to verify user
    const supabaseAuth = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_ANON_KEY") ?? ""
    );

    const { data: { user }, error: authError } = await supabaseAuth.auth.getUser(token);

    if (authError || !user) {
      return new Response(
        JSON.stringify({ error: "Invalid or expired token. Please sign in again." }),
        { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const { messages, language = 'en' } = await req.json();

    // Input validation - limit conversation history
    if (messages && messages.length > 50) {
      return new Response(
        JSON.stringify({ error: "Conversation history too long" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    console.log("Promoter create request:", { userId: user.id, messageCount: messages.length });

    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) {
      throw new Error("LOVABLE_API_KEY is not configured");
    }

    const supabaseClient = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? ""
    );

    const tools = [
      {
        type: "function",
        function: {
          name: "extract_event",
          description: "Extract event details from conversation to show in confirmation form",
          parameters: {
            type: "object",
            properties: {
              name: { type: "string", description: "Event name" },
              artist: { type: "string", description: "Artist name" },
              description: { type: ["string", "null"], description: "Event description (optional)" },
              venue: { type: "string", description: "Venue name" },
              city: { type: "string", description: "City name" },
              event_date: { type: "string", description: "Event date and time in ISO format" },
              price: { type: "number", description: "Ticket price" },
              ticket_url: { type: ["string", "null"], description: "Ticket URL (optional)" },
            },
            required: ["name", "artist", "venue", "city", "event_date", "price"],
          },
        },
      },
    ];

    const languageMap: Record<string, string> = {
      'en': 'English',
      'es': 'Spanish',
      'it': 'Italian',
      'ca': 'Catalan'
    };
    const userLanguage = languageMap[language] || 'English';

    const systemPrompt = `You are an AI assistant helping event promoters publish their events on laiive. IMPORTANT: Always respond in ${userLanguage}.

CRITICAL: Do NOT greet the user or introduce yourself. Do NOT say "Hey!", "Hi!", "Ciao!", "Hello!" or any welcome message. Do NOT explain what you can do. Just wait for the user to describe their event and respond directly to what they share.

Your goal is to collect these details through natural conversation:

Required: event name, artist name, date and time, venue name, city, ticket price
Optional: event description, ticket URL

Ask for missing details naturally, one or two at a time. Once you have all required information, use the extract_event tool to show the confirmation form.

Important notes:
- Never make up information
- Ask clarifying questions when needed
- Parse dates naturally (like "tomorrow at 8pm" or "next Friday")
- Call extract_event only when you have all required fields`;

    const response = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${LOVABLE_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash",
        messages: [
          { role: "system", content: systemPrompt },
          ...messages,
        ],
        tools: tools,
        stream: true,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error("AI gateway error:", response.status, errorText);

      if (response.status === 429) {
        return new Response(
          JSON.stringify({ error: "Rate limits exceeded, please try again later." }),
          { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      if (response.status === 402) {
        return new Response(
          JSON.stringify({ error: "Payment required, please add funds to your Lovable AI workspace." }),
          { status: 402, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      return new Response(
        JSON.stringify({ error: "AI gateway error" }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error("No response body");

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        const decoder = new TextDecoder();
        let buffer = "";
        let toolCallBuffer = "";

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
              if (!line.trim() || line.startsWith(":")) continue;
              if (!line.startsWith("data: ")) continue;

              const data = line.slice(6).trim();
              if (data === "[DONE]") continue;

              try {
                const parsed = JSON.parse(data);
                const toolCalls = parsed.choices?.[0]?.delta?.tool_calls;

                if (toolCalls) {
                  for (const toolCall of toolCalls) {
                    if (toolCall.function?.name === "extract_event") {
                      // Accumulate tool call arguments
                      if (toolCall.function?.arguments) {
                        toolCallBuffer += toolCall.function.arguments;
                      }

                      // Try to parse when we have complete JSON
                      try {
                        const args = JSON.parse(toolCallBuffer);
                        console.log("Extracted event details:", args);

                        // Send event details as a special message
                        controller.enqueue(
                          encoder.encode(
                            `data: ${JSON.stringify({
                              choices: [
                                {
                                  delta: {
                                    content: `__EVENT_EXTRACTED__${JSON.stringify(args)}__EVENT_EXTRACTED__`,
                                  },
                                },
                              ],
                            })}\n\n`
                          )
                        );

                        toolCallBuffer = "";
                      } catch (e) {
                        // JSON not complete yet, continue accumulating
                        console.log("Waiting for complete JSON...");
                      }
                    }
                  }
                } else {
                  controller.enqueue(encoder.encode(`data: ${data}\n\n`));
                }
              } catch (e) {
                console.error("Parse error:", e);
              }
            }
          }

          controller.enqueue(encoder.encode("data: [DONE]\n\n"));
          controller.close();
        } catch (error) {
          console.error("Stream error:", error);
          controller.error(error);
        }
      },
    });

    return new Response(stream, {
      headers: {
        ...corsHeaders,
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
      },
    });
  } catch (error) {
    console.error("Promoter create error:", error);
    return new Response(
      JSON.stringify({ error: error instanceof Error ? error.message : "Unknown error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
