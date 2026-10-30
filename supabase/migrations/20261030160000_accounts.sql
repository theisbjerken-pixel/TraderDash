-- TraderDash accounts shared by the Streamlit app and the stripe-webhook function.
-- Apply with: supabase db push
--
-- Subscription fields live on users. One account has one effective plan, so a
-- second subscriptions table would duplicate plan and status.
--
-- The browser anon key cannot read these tables. Streamlit uses DATABASE_URL
-- as the Postgres role. The Edge Function uses the service role.

create table if not exists public.users (
    user_id text primary key,
    email text not null unique,
    password_hash text not null,
    plan text not null check (plan in ('free', 'nordic', 'international')),
    subscription_status text not null check (
        subscription_status in (
            'free', 'active', 'trialing', 'past_due',
            'incomplete', 'cancelled', 'expired'
        )
    ),
    stripe_customer_id text,
    stripe_subscription_id text,
    subscription_current_period_end text,
    cancel_at_period_end boolean not null default false,
    created_at text not null,
    updated_at text not null
);

create unique index if not exists users_stripe_customer_id_key
    on public.users (stripe_customer_id)
    where stripe_customer_id is not null;

create unique index if not exists users_stripe_subscription_id_key
    on public.users (stripe_subscription_id)
    where stripe_subscription_id is not null;

create table if not exists public.stripe_events (
    stripe_event_id text primary key,
    event_type text not null,
    processed_at text not null,
    processing_status text not null check (
        processing_status in ('received', 'rejected', 'failed')
    ),
    error_message text
);

alter table public.users enable row level security;
alter table public.stripe_events enable row level security;

do $$
begin
    if exists (select 1 from pg_roles where rolname = 'anon') then
        revoke all on table public.users from anon;
        revoke all on table public.stripe_events from anon;
    end if;
    if exists (select 1 from pg_roles where rolname = 'authenticated') then
        revoke all on table public.users from authenticated;
        revoke all on table public.stripe_events from authenticated;
    end if;
end $$;
