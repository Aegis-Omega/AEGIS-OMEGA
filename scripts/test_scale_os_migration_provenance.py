from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
OLD = MIGRATIONS / "20260719033000_scale_os_control_plane_v1.sql"
SIGNED = MIGRATIONS / "20260719033000_scale_os_signed_event_envelopes_v1.sql"


def test_signed_event_migration_has_unique_provenance_name() -> None:
    assert not OLD.exists(), "signed-event SQL reuses the name of an already-applied live Scale OS migration"
    assert SIGNED.is_file()

    sql = SIGNED.read_text(encoding="utf-8")
    assert "create table if not exists public.scale_os_event_envelopes_v1" in sql
    assert "create table if not exists public.scale_os_approval_projection_v1" in sql
    assert "idempotency_key text not null unique" in sql

    # This file is the signed event-envelope model, not the older live scale_os
    # operational schema whose migration history uses the same logical name.
    assert "scale_os.service_connections" not in sql
    assert "scale_os.corpus_assets" not in sql
    assert "scale_os.tasks" not in sql
