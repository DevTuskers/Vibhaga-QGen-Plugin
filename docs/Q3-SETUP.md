# One-time Q3 setup

Run once as `postgres` on the merged project. Q3 reads through `qgen.q3`, a counts-only SECURITY
DEFINER function — RLS on `auth.*` has no policies, so a plain reader role would see zero rows, and
the reader must not be BYPASSRLS. The 4th column needs admins to carry
`raw_app_meta_data->>'vibhaga_role' = 'admin'` in `auth.users` (they do — set at merge); without the
flag an admin uid reads `actor_is_admin = 0` → NOT ok. The MCP fallback still works: postgres can
execute the function.

```sql
create schema if not exists qgen;
create or replace function qgen.q3(actor uuid)
returns table(actor_exists bigint, sessions bigint, active_refresh_tokens bigint, actor_is_admin bigint)
language sql stable security definer set search_path = '' as $$
  select (select count(*) from auth.users where id = actor),
         (select count(*) from auth.sessions where user_id = actor),
         (select count(*) from auth.refresh_tokens where user_id = actor::text and revoked is not true),
         (select count(*) from auth.users where id = actor
            and raw_app_meta_data->>'vibhaga_role' = 'admin');
$$;
revoke all on function qgen.q3(uuid) from public, anon, authenticated, service_role;
create role qgen_auth_reader login password '<strong password>';   -- skip if it exists
grant usage on schema qgen to qgen_auth_reader;
grant execute on function qgen.q3(uuid) to qgen_auth_reader;
```
