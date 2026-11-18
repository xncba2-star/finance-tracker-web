-- RuangUang multi-user schema
-- Run this entire file in Supabase Dashboard > SQL Editor.
create extension if not exists pgcrypto;

create table if not exists public.workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  type text not null check (type in ('personal','family')),
  created_by uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

create table if not exists public.workspace_members (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member' check (role in ('owner','admin','member')),
  created_at timestamptz not null default now(),
  primary key(workspace_id,user_id)
);

create table if not exists public.accounts (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  name text not null,
  kind text not null,
  opening_balance numeric(16,2) not null default 0,
  is_active boolean not null default true,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  unique(workspace_id,name)
);

create table if not exists public.transactions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  kind text not null check (kind in ('Income','Expense','Transfer In','Transfer Out')),
  amount numeric(16,2) not null check (amount > 0),
  category text,
  account text not null,
  tx_date date not null,
  note text,
  transfer_peer text,
  transfer_group uuid,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);

create table if not exists public.bills (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  title text not null,
  provider text,
  amount numeric(16,2) not null check (amount > 0),
  due_date date not null,
  paid boolean not null default false,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);

create table if not exists public.workspace_invites (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  invite_email text not null,
  status text not null default 'pending' check (status in ('pending','accepted','revoked')),
  invited_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  unique(workspace_id,invite_email)
);

create or replace function public.is_workspace_member(p_workspace_id uuid)
returns boolean language sql stable security definer set search_path=public
as $$
  select exists (
    select 1 from public.workspace_members
    where workspace_id=p_workspace_id and user_id=auth.uid()
  );
$$;

create or replace function public.has_workspace_role(p_workspace_id uuid, p_roles text[])
returns boolean language sql stable security definer set search_path=public
as $$
  select exists (
    select 1 from public.workspace_members
    where workspace_id=p_workspace_id and user_id=auth.uid() and role=any(p_roles)
  );
$$;

create or replace function public.create_workspace(p_name text,p_type text)
returns uuid language plpgsql security definer set search_path=public
as $$
declare new_id uuid;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if p_type not in ('personal','family') then raise exception 'Invalid workspace type'; end if;
  if length(trim(p_name)) < 2 then raise exception 'Workspace name is too short'; end if;
  insert into public.workspaces(name,type,created_by)
  values(trim(p_name),p_type,auth.uid()) returning id into new_id;
  insert into public.workspace_members(workspace_id,user_id,role)
  values(new_id,auth.uid(),'owner');
  return new_id;
end;
$$;

create or replace function public.invite_workspace_member(p_workspace_id uuid,p_email text)
returns uuid language plpgsql security definer set search_path=public
as $$
declare new_invite uuid;
begin
  if not public.has_workspace_role(p_workspace_id,array['owner','admin']) then
    raise exception 'Not authorized to invite members';
  end if;
  if p_email is null or position('@' in p_email)=0 then raise exception 'Invalid email'; end if;
  insert into public.workspace_invites(workspace_id,invite_email,invited_by)
  values(p_workspace_id,lower(trim(p_email)),auth.uid())
  on conflict(workspace_id,invite_email) do update set status='pending', invited_by=auth.uid()
  returning id into new_invite;
  return new_invite;
end;
$$;

create or replace function public.accept_workspace_invite(p_invite_id uuid)
returns void language plpgsql security definer set search_path=public
as $$
declare inv public.workspace_invites%rowtype;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  select * into inv from public.workspace_invites
  where id=p_invite_id and invite_email=lower(auth.jwt()->>'email') and status='pending';
  if not found then raise exception 'Invitation not found or not addressed to this account'; end if;
  insert into public.workspace_members(workspace_id,user_id,role)
  values(inv.workspace_id,auth.uid(),'member')
  on conflict(workspace_id,user_id) do nothing;
  update public.workspace_invites set status='accepted' where id=p_invite_id;
end;
$$;

alter table public.workspaces enable row level security;
alter table public.workspace_members enable row level security;
alter table public.accounts enable row level security;
alter table public.transactions enable row level security;
alter table public.bills enable row level security;
alter table public.workspace_invites enable row level security;

drop policy if exists "members can view workspaces" on public.workspaces;
create policy "members can view workspaces" on public.workspaces
for select to authenticated using (public.is_workspace_member(id));

drop policy if exists "members can view memberships" on public.workspace_members;
create policy "members can view memberships" on public.workspace_members
for select to authenticated using (public.is_workspace_member(workspace_id) or user_id=auth.uid());

drop policy if exists "members can manage accounts" on public.accounts;
create policy "members can manage accounts" on public.accounts
for all to authenticated using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

drop policy if exists "members can manage transactions" on public.transactions;
create policy "members can manage transactions" on public.transactions
for all to authenticated using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

drop policy if exists "members can manage bills" on public.bills;
create policy "members can manage bills" on public.bills
for all to authenticated using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

drop policy if exists "invited users or members can view invites" on public.workspace_invites;
create policy "invited users or members can view invites" on public.workspace_invites
for select to authenticated using (
  invite_email=lower(auth.jwt()->>'email') or public.is_workspace_member(workspace_id)
);


create or replace function public.create_internal_transfer(
  p_workspace_id uuid,
  p_source text,
  p_target text,
  p_amount numeric,
  p_tx_date date,
  p_note text default ''
)
returns uuid language plpgsql security definer set search_path=public
as $$
declare transfer_id uuid := gen_random_uuid();
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if not public.is_workspace_member(p_workspace_id) then raise exception 'Not a workspace member'; end if;
  if p_source = p_target then raise exception 'Source and target must be different'; end if;
  if p_amount <= 0 then raise exception 'Amount must be positive'; end if;
  if not exists(select 1 from public.accounts where workspace_id=p_workspace_id and name=p_source and is_active=true)
     or not exists(select 1 from public.accounts where workspace_id=p_workspace_id and name=p_target and is_active=true) then
    raise exception 'Both accounts must exist in this workspace';
  end if;
  insert into public.transactions(workspace_id,kind,amount,category,account,tx_date,note,transfer_peer,transfer_group,created_by)
  values
    (p_workspace_id,'Transfer Out',p_amount,'Transfer internal',p_source,p_tx_date,p_note,p_target,transfer_id,auth.uid()),
    (p_workspace_id,'Transfer In',p_amount,'Transfer internal',p_target,p_tx_date,p_note,p_source,transfer_id,auth.uid());
  return transfer_id;
end;
$$;

grant execute on function public.create_internal_transfer(uuid,text,text,numeric,date,text) to authenticated;
grant execute on function public.create_workspace(text,text) to authenticated;
grant execute on function public.invite_workspace_member(uuid,text) to authenticated;
grant execute on function public.accept_workspace_invite(uuid) to authenticated;
grant execute on function public.is_workspace_member(uuid) to authenticated;
grant execute on function public.has_workspace_role(uuid,text[]) to authenticated;
