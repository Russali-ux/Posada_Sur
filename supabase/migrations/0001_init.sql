-- Ciclo Productivo del Cerdo — esquema inicial
-- Ejecutar en el proyecto Supabase indicado (ver README.md)

create extension if not exists pgcrypto;

create table if not exists public.cerdo_lotes (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  birth_date date not null,
  stage_settings jsonb,                 -- null = usa las duraciones/pesos de referencia
  current_stage_id text,
  current_stage_name text,
  age_days integer,
  estimated_weight numeric(6,2),
  slaughter_date date,
  days_to_slaughter integer,
  last_calculated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.cerdo_lotes is 'Un registro por lote de cerdos: fecha de nacimiento y estado de ciclo calculado.';
comment on column public.cerdo_lotes.stage_settings is 'Arreglo JSON opcional que sobreescribe las duraciones/pesos/alimento por etapa para este lote.';

create table if not exists public.cerdo_lotes_eventos (
  id uuid primary key default gen_random_uuid(),
  lote_id uuid not null references public.cerdo_lotes(id) on delete cascade,
  previous_stage text,
  new_stage text not null,
  occurred_on date not null default current_date,
  notified boolean not null default false,
  created_at timestamptz not null default now()
);

comment on table public.cerdo_lotes_eventos is 'Un registro cada vez que el cron detecta que un lote cruzó a una nueva etapa. notified=false hasta que un canal (correo/Slack) lo procese.';

-- Mantener updated_at al día en cada escritura
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_cerdo_lotes_updated_at on public.cerdo_lotes;
create trigger trg_cerdo_lotes_updated_at
  before update on public.cerdo_lotes
  for each row execute function public.set_updated_at();

-- Row Level Security
alter table public.cerdo_lotes enable row level security;
alter table public.cerdo_lotes_eventos enable row level security;

-- Acceso abierto para la clave anon: esta app no tiene login propio.
-- Ver README.md → "Seguridad" antes de hacer público el repositorio o el sitio.
drop policy if exists cerdo_lotes_anon_all on public.cerdo_lotes;
create policy cerdo_lotes_anon_all on public.cerdo_lotes
  for all
  using (true)
  with check (true);

drop policy if exists cerdo_lotes_eventos_anon_all on public.cerdo_lotes_eventos;
create policy cerdo_lotes_eventos_anon_all on public.cerdo_lotes_eventos
  for all
  using (true)
  with check (true);
