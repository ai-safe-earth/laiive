import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

Deno.serve(async (req) => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const supabaseAnonKey = Deno.env.get('SUPABASE_ANON_KEY')!;

    const body = await req.json();
    const { email, password, firstName, lastName, city, country, industryRole, upgrade, entities } = body;

    // Validate required fields
    if (!firstName || !lastName || !city || !country || !industryRole) {
      return new Response(
        JSON.stringify({ error: 'All professional information fields are required' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const supabaseAdmin = createClient(supabaseUrl, supabaseServiceKey);

    let userId: string;

    if (upgrade) {
      // Upgrade existing user - get user from auth header
      const authHeader = req.headers.get('Authorization');
      if (!authHeader) {
        return new Response(
          JSON.stringify({ error: 'Authentication required for upgrade' }),
          { status: 401, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      const supabaseAuth = createClient(supabaseUrl, supabaseAnonKey, {
        global: { headers: { Authorization: authHeader } },
      });

      const { data: { user }, error: userError } = await supabaseAuth.auth.getUser();
      if (userError || !user) {
        return new Response(
          JSON.stringify({ error: 'Invalid authentication' }),
          { status: 401, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      userId = user.id;

      // Check if already a promoter
      const { data: existingRole } = await supabaseAdmin
        .from('user_roles')
        .select('id')
        .eq('user_id', userId)
        .eq('role', 'promoter')
        .maybeSingle();

      if (existingRole) {
        return new Response(
          JSON.stringify({ error: 'You are already a promoter' }),
          { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }
    } else {
      // New signup - validate email and password
      if (!email || !password) {
        return new Response(
          JSON.stringify({ error: 'Email and password are required' }),
          { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      if (password.length < 6) {
        return new Response(
          JSON.stringify({ error: 'Password must be at least 6 characters' }),
          { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      // Create new user
      const { data: authData, error: authError } = await supabaseAdmin.auth.admin.createUser({
        email,
        password,
        email_confirm: false,
      });

      if (authError) {
        console.error('Auth error:', authError);
        return new Response(
          JSON.stringify({ error: authError.message }),
          { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      userId = authData.user.id;
    }

    // Insert promoter profile
    const { data: profileData, error: profileError } = await supabaseAdmin
      .from('promoter_profiles')
      .insert({
        user_id: userId,
        first_name: firstName,
        last_name: lastName,
        city,
        country,
        industry_role: industryRole,
      })
      .select('id')
      .single();

    if (profileError) {
      console.error('Profile error:', profileError);
      // If signup (not upgrade), we should clean up the created user
      if (!upgrade) {
        await supabaseAdmin.auth.admin.deleteUser(userId);
      }
      return new Response(
        JSON.stringify({ error: 'Failed to create promoter profile' }),
        { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const promoterProfileId = profileData.id;

    // Assign promoter role
    const { error: roleError } = await supabaseAdmin
      .from('user_roles')
      .insert({
        user_id: userId,
        role: 'promoter',
      });

    if (roleError) {
      console.error('Role error:', roleError);
      // Clean up
      await supabaseAdmin.from('promoter_profiles').delete().eq('user_id', userId);
      if (!upgrade) {
        await supabaseAdmin.auth.admin.deleteUser(userId);
      }
      return new Response(
        JSON.stringify({ error: 'Failed to assign promoter role' }),
        { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Optional: Create initial entities if provided
    if (entities && Array.isArray(entities) && entities.length > 0) {
      for (const entity of entities) {
        const { type, data } = entity;
        if (!type || !data?.name) continue;

        const tableName = type === 'venue' ? 'venues' : type === 'band' ? 'bands' : 'festivals';
        const { error: entityError } = await supabaseAdmin
          .from(tableName)
          .insert({
            ...data,
            promoter_id: promoterProfileId,
            created_by: userId,
          });

        if (entityError) {
          console.error(`Entity creation error for ${type} (non-fatal):`, entityError);
          // Don't fail the whole signup, just log it
        } else {
          console.log(`Created ${type} "${data.name}" for promoter ${promoterProfileId}`);
        }
      }
    }

    console.log(`Promoter account ${upgrade ? 'upgraded' : 'created'} for user ${userId}`);

    return new Response(
      JSON.stringify({
        success: true,
        message: upgrade ? 'Successfully upgraded to promoter' : 'Promoter account created'
      }),
      { status: 200, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    console.error('Unexpected error:', error);
    return new Response(
      JSON.stringify({ error: 'An unexpected error occurred' }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});
