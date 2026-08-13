import "https://deno.land/x/xhr@0.1.0/mod.ts";
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

// Rate limiting: track requests per IP
const rateLimitMap = new Map<string, { count: number; resetTime: number }>();
const RATE_LIMIT = 20; // requests per minute
const RATE_WINDOW = 60000; // 1 minute in ms
const MAX_URL_LENGTH = 2048; // Standard URL length limit

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
    const { url, language = 'en' } = await req.json();

    if (!url) {
      return new Response(JSON.stringify({ error: 'URL is required' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    // Input validation - limit URL length
    if (url.length > MAX_URL_LENGTH) {
      return new Response(JSON.stringify({ error: 'URL too long' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    // Validate URL to prevent SSRF attacks
    let parsedUrl: URL;
    try {
      parsedUrl = new URL(url);
    } catch {
      return new Response(JSON.stringify({ error: 'Invalid URL format' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    // Block private IPs, localhost, and cloud metadata endpoints
    const hostname = parsedUrl.hostname.toLowerCase();
    const blockedPatterns = [
      'localhost',
      '127.0.0.1',
      '0.0.0.0',
      '169.254.169.254', // AWS/GCP metadata
      '[::1]',
    ];

    const blockedPrefixes = [
      '10.',
      '192.168.',
      '172.16.', '172.17.', '172.18.', '172.19.',
      '172.20.', '172.21.', '172.22.', '172.23.',
      '172.24.', '172.25.', '172.26.', '172.27.',
      '172.28.', '172.29.', '172.30.', '172.31.',
    ];

    if (blockedPatterns.includes(hostname) ||
        blockedPrefixes.some(prefix => hostname.startsWith(prefix)) ||
        hostname.endsWith('.local') ||
        hostname.endsWith('.internal')) {
      console.log('Blocked SSRF attempt to:', hostname);
      return new Response(JSON.stringify({ error: 'URL not allowed' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    // Only allow http and https protocols
    if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
      return new Response(JSON.stringify({ error: 'Only HTTP and HTTPS URLs are allowed' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    console.log('Fetching URL:', url);

    // Fetch the webpage content
    const pageResponse = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
      },
    });

    if (!pageResponse.ok) {
      console.error('Failed to fetch URL:', pageResponse.status);
      return new Response(JSON.stringify({ error: 'Could not fetch the webpage' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    const html = await pageResponse.text();

    // Extract text content from HTML (simple extraction)
    const textContent = html
      .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
      .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .substring(0, 8000); // Limit content size

    console.log('Extracted text length:', textContent.length);

    // Use Lovable AI to extract event details
    const extractionResponse = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${Deno.env.get('LOVABLE_API_KEY')}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash",
        messages: [
          {
            role: "system",
            content: `You are an event data extractor. Extract event information from webpage content.

IMPORTANT: Respond ONLY with a valid JSON object, no markdown, no explanation.

Extract these fields (use null if not found):
- name: Event name/title
- artist: Performer/artist name
- venue: Venue/location name
- city: City name
- event_date: Date and time in ISO format (YYYY-MM-DDTHH:mm:ss)
- price: Ticket price as a number (just the number, no currency)
- description: Brief event description
- ticket_url: URL to buy tickets (use the original URL if no specific ticket link found)

Response format: {"name": "...", "artist": "...", "venue": "...", "city": "...", "event_date": "...", "price": null, "description": "...", "ticket_url": "..."}`
          },
          {
            role: "user",
            content: `Extract event details from this webpage content:\n\nURL: ${url}\n\nContent:\n${textContent}`
          }
        ],
        temperature: 0.1,
        max_tokens: 1000
      })
    });

    if (!extractionResponse.ok) {
      const errorText = await extractionResponse.text();
      console.error('AI extraction failed:', errorText);
      return new Response(JSON.stringify({ error: 'Failed to extract event details' }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    const extractionData = await extractionResponse.json();
    const aiResponse = extractionData.choices[0]?.message?.content || '';

    console.log('AI response:', aiResponse);

    // Parse the JSON response
    let eventData;
    try {
      // Clean up potential markdown formatting
      const cleanedResponse = aiResponse.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
      eventData = JSON.parse(cleanedResponse);
    } catch (parseError) {
      console.error('Failed to parse AI response:', parseError);
      return new Response(JSON.stringify({ error: 'Could not parse event details' }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    // Ensure ticket_url has the original URL as fallback
    if (!eventData.ticket_url) {
      eventData.ticket_url = url;
    }

    return new Response(JSON.stringify({ success: true, eventData }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });

  } catch (error) {
    console.error('Error in extract-event-from-url:', error);
    return new Response(JSON.stringify({ error: error instanceof Error ? error.message : 'Unknown error' }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
