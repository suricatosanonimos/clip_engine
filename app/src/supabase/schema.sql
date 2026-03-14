-- ═══════════════════════════════════════════════════════════════
--  CLIP ENGINE — Supabase Schema
--  Execute no SQL Editor do Supabase dashboard
-- ═══════════════════════════════════════════════════════════════

-- ── Extensão para UUIDs ────────────────────────────────────────
create extension if not exists "uuid-ossp";

-- ── Tabela de perfis (espelha auth.users) ─────────────────────
create table public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  email       text,
  full_name   text,
  avatar_url  text,
  created_at  timestamptz default now()
);

-- Cria perfil automaticamente ao criar usuário
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into public.profiles (id, email, full_name, avatar_url)
  values (
    new.id,
    new.email,
    new.raw_user_meta_data->>'full_name',
    new.raw_user_meta_data->>'avatar_url'
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ── Tabela de jobs de processamento ───────────────────────────
create table public.jobs (
  id              uuid primary key default uuid_generate_v4(),
  user_id         uuid references public.profiles(id) on delete cascade,
  status          text not null default 'pending'
                    check (status in ('pending','downloading','processing',
                                      'transcribing','analyzing','done','error')),
  progress        float default 0.0,
  message         text default '',
  error           text,

  -- fonte: URL do YouTube ou nome do arquivo no Storage
  source_type     text not null check (source_type in ('youtube','upload')),
  source_url      text,                        -- URL do YouTube
  source_storage_path text,                   -- path no Supabase Storage (bucket: videos)

  -- metadados do vídeo
  video_title     text,
  video_duration  int,                         -- segundos

  -- configurações do pipeline
  num_clips       int default 10,
  clip_duration   int default 60,
  tracking        boolean default true,

  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);

-- Atualiza updated_at automaticamente
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger jobs_updated_at
  before update on public.jobs
  for each row execute function public.set_updated_at();

-- ── Tabela de clipes gerados ───────────────────────────────────
create table public.clips (
  id              uuid primary key default uuid_generate_v4(),
  job_id          uuid references public.jobs(id) on delete cascade,
  user_id         uuid references public.profiles(id) on delete cascade,

  filename        text not null,
  storage_path    text not null,               -- path no bucket: clips
  public_url      text,                        -- URL pública para download

  size_mb         float,
  duration_sec    float,
  clip_index      int,                         -- ordem do clipe (1, 2, 3...)

  -- análise de IA (opcional)
  score           float default 0.0,
  motivo          text,

  created_at      timestamptz default now()
);

-- ── Índices para performance ───────────────────────────────────
create index jobs_user_id_idx  on public.jobs(user_id);
create index jobs_status_idx   on public.jobs(status);
create index clips_job_id_idx  on public.clips(job_id);
create index clips_user_id_idx on public.clips(user_id);

-- ── Row Level Security ─────────────────────────────────────────
-- Usuário só vê e edita seus próprios dados

alter table public.profiles enable row level security;
create policy "profiles: próprio usuário" on public.profiles
  using (auth.uid() = id);

alter table public.jobs enable row level security;
create policy "jobs: próprio usuário" on public.jobs
  using (auth.uid() = user_id);

alter table public.clips enable row level security;
create policy "clips: próprio usuário" on public.clips
  using (auth.uid() = user_id);

-- ── Storage Buckets ────────────────────────────────────────────
-- Execute separadamente no Supabase dashboard > Storage
-- ou via API. Aqui como referência:

-- bucket "videos"  → vídeos enviados pelo usuário (privado)
-- bucket "clips"   → clipes processados (privado, link assinado para download)

-- insert into storage.buckets (id, name, public) values ('videos', 'videos', false);
-- insert into storage.buckets (id, name, public) values ('clips',  'clips',  false);

-- Políticas de storage: usuário só acessa sua pasta (user_id/...)
-- create policy "videos: upload próprio"
--   on storage.objects for insert to authenticated
--   with check (bucket_id = 'videos' and (storage.foldername(name))[1] = auth.uid()::text);

-- create policy "videos: leitura própria"
--   on storage.objects for select to authenticated
--   using (bucket_id = 'videos' and (storage.foldername(name))[1] = auth.uid()::text);

-- create policy "clips: leitura própria"
--   on storage.objects for select to authenticated
--   using (bucket_id = 'clips' and (storage.foldername(name))[1] = auth.uid()::text);
