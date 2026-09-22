// Supabase Edge Function: reset-usage
// Resets monthly usage counters for all users whose reset_date has passed.
// Schedule this via Supabase Dashboard → Database → Extensions → pg_cron:
//   select cron.schedule('reset-usage', '0 0 1 * *', $$
//     select net.http_post(
//       url := '<your-project-url>/functions/v1/reset-usage',
//       headers := '{"Authorization": "Bearer <service-role-key>"}'::jsonb
//     )
//   $$);

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

Deno.serve(async (req: Request) => {
  // Verify the request comes from Supabase cron (service-role key in Authorization)
  const authHeader = req.headers.get("Authorization") ?? "";
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  if (!authHeader.includes(serviceRoleKey) && !authHeader.includes("Bearer")) {
    return new Response("Unauthorized", { status: 401 });
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL") ?? "",
    serviceRoleKey,
  );

  const { error } = await supabase.rpc("reset_monthly_usage");

  if (error) {
    console.error("reset_monthly_usage failed:", error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  console.log("Monthly usage reset completed at", new Date().toISOString());
  return new Response(JSON.stringify({ ok: true, timestamp: new Date().toISOString() }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
});
