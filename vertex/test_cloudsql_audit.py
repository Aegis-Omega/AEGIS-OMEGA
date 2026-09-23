import hashlib
import importlib.util
import json
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parent / "cloudsql_audit.py"
spec = importlib.util.spec_from_file_location("cloudsql_audit", MODULE)
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


def compute_hash(previous, sequence, observation):
    body = json.dumps(
        observation, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(
        previous.encode() + sequence.to_bytes(8, "big") + body
    ).hexdigest()


def test_config_normalizes_service_account_and_existing_terraform_env():
    cfg = audit.CloudSqlAuditConfig.from_env(
        {
            "CLOUD_SQL_AUDIT_MODE": "required",
            "database_postgresql_CLOUD_SQL_DATABASE_CONNECTION_NAME": "aegisomegav1:us-central1:aegis-audit-db",
            "CLOUD_SQL_IAM_USER": "Service@AegisOmegaV1.iam.gserviceaccount.com",
        }
    )
    assert cfg.enabled and cfg.required
    assert cfg.db_name == "default"
    assert cfg.db_iam_user == "service@aegisomegav1.iam"


def test_config_uses_metadata_identity_when_explicit_user_absent():
    cfg = audit.CloudSqlAuditConfig.from_env(
        {
            "CLOUD_SQL_AUDIT_MODE": "optional",
            "CLOUD_SQL_INSTANCE_CONNECTION_NAME": "aegisomegav1:us-central1:aegis-audit-db",
            "CLOUD_SQL_DB_NAME": "default",
        },
        metadata_email=lambda: "runtime@aegisomegav1.iam.gserviceaccount.com",
    )
    assert cfg.db_iam_user == "runtime@aegisomegav1.iam"


def test_off_mode_never_calls_metadata():
    called = False

    def resolver():
        nonlocal called
        called = True
        raise AssertionError("metadata must not be called")

    cfg = audit.CloudSqlAuditConfig.from_env(
        {"CLOUD_SQL_AUDIT_MODE": "off"},
        metadata_email=resolver,
    )
    assert not cfg.enabled
    assert not called


def test_invalid_required_config_fails_closed():
    try:
        audit.CloudSqlAuditConfig.from_env(
            {"CLOUD_SQL_AUDIT_MODE": "required"},
            metadata_email=lambda: "runtime@example.iam.gserviceaccount.com",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("required config must reject missing instance")


class Result:
    def __init__(self, rows=None, rowcount=1):
        self._rows = rows or []
        self.rowcount = rowcount

    def mappings(self):
        return self

    def one(self):
        if len(self._rows) != 1:
            raise AssertionError("expected one row")
        return self._rows[0]

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows

    def __iter__(self):
        return iter(self._rows)


class Tx:
    def __init__(self, engine):
        self.engine = engine

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        params = params or {}
        self.engine.calls.append((sql, dict(params)))
        if "select next_sequence, terminal_hash" in sql:
            return Result([{
                "next_sequence": self.engine.next_sequence,
                "terminal_hash": self.engine.terminal_hash,
            }])
        if "append_constitutional_entry_v1" in sql:
            if self.engine.reject_next_append:
                self.engine.reject_next_append = False
                self.engine.next_sequence += 1
                self.engine.terminal_hash = "b" * 64
                return Result([{"accepted": False}])
            if (
                params["sequence"] != self.engine.next_sequence
                or params["previous_entry_hash"] != self.engine.terminal_hash
            ):
                return Result([{"accepted": False}])
            self.engine.entries.append({
                "sequence": params["sequence"],
                "previous_entry_hash": params["previous_entry_hash"],
                "entry_hash": params["entry_hash"],
                "observation": json.loads(params["observation"]),
                "tier": params["tier"],
                "timestamp_ms": params["timestamp_ms"],
            })
            self.engine.next_sequence += 1
            self.engine.terminal_hash = params["entry_hash"]
            return Result([{"accepted": True}])
        if "where sequence=:sequence" in sql:
            rows = [x for x in self.engine.entries if x["sequence"] == params["sequence"]]
            return Result(rows)
        if "order by sequence asc" in sql:
            return Result(list(self.engine.entries))
        raise AssertionError("unexpected SQL: " + sql)


class Engine:
    def __init__(self):
        self.calls = []
        self.entries = []
        self.next_sequence = 0
        self.terminal_hash = audit.GENESIS_HASH
        self.reject_next_append = False
        self.disposed = False

    def begin(self):
        return Tx(self)

    def connect(self):
        return Tx(self)

    def dispose(self):
        self.disposed = True


def test_append_uses_compare_and_swap_and_preserves_existing_hash_format():
    engine = Engine()
    store = audit.CloudSqlAuditStore(engine)
    first = store.append({"b": 2, "a": 1}, "T1", 1000, compute_hash)
    second = store.append({"x": "y"}, "T2", 1001, compute_hash)
    assert first["sequence"] == 0
    assert second["sequence"] == 1
    assert second["previous_entry_hash"] == first["entry_hash"]
    assert engine.next_sequence == 2
    assert sum("append_constitutional_entry_v1" in sql for sql, _ in engine.calls) == 2


def test_certify_detects_tamper_and_head_mismatch():
    engine = Engine()
    store = audit.CloudSqlAuditStore(engine)
    store.append({"a": 1}, "T1", 1000, compute_hash)
    assert store.certify(compute_hash)["is_valid"] is True
    engine.entries[0]["observation"] = {"a": 2}
    assert store.certify(compute_hash)["failure"] == "entry_hash_mismatch"


def test_no_password_field_exists_in_config():
    assert "password" not in audit.CloudSqlAuditConfig.__dataclass_fields__


def test_append_retries_after_concurrent_writer_moves_head():
    engine = Engine()
    engine.reject_next_append = True
    store = audit.CloudSqlAuditStore(engine)
    entry = store.append({"worker": "second"}, "T1", 1000, compute_hash)
    assert entry["sequence"] == 1
    assert entry["previous_entry_hash"] == "b" * 64
    assert sum("append_constitutional_entry_v1" in sql for sql, _ in engine.calls) == 2


def test_schema_uses_security_definer_cas_and_least_privilege_writer_role():
    sql = (Path(__file__).resolve().parent.parent / "gcp" / "cloudsql" / "001_constitutional_audit_chain_v1.sql").read_text()
    assert "security definer" in sql.lower()
    assert "for update" in sql.lower()
    assert "return false" in sql.lower()
    assert "grant execute on function aegis_audit.append_constitutional_entry_v1" in sql
    assert "grant select, update on aegis_audit.constitutional_chain_head_v1" not in sql
    assert "grant select, insert on aegis_audit.constitutional_chain_v1" not in sql


def test_serve_wires_cloud_sql_as_optional_authoritative_backend():
    serve = (Path(__file__).resolve().parent / "serve.py").read_text()
    assert "from cloudsql_audit import CloudSqlAuditConfig, CloudSqlAuditStore" in serve
    assert 'self.audit_backend = "cloud_sql"' in serve
    assert "asyncio.to_thread(" in serve
    assert "self.audit_store.append" in serve
    assert '"CLOUD_SQL_AUDIT_MODE", "off"' in serve
    assert "CLOUD_SQL_AUDIT_REQUIRED_UNAVAILABLE" in serve
    assert '"audit_backend": state.audit_backend' in serve
    assert "self.audit_required = config.required" in serve
    assert serve.count("if state.audit_required:") >= 6
    assert "durable audit certification unavailable" in serve


def test_docker_pins_cloud_sql_connector_driver_and_sqlalchemy():
    docker = (Path(__file__).resolve().parent / "Dockerfile").read_text()
    assert "cloud-sql-python-connector[pg8000]==1.22.0" in docker
    assert "pg8000==1.31.5" in docker
    assert "SQLAlchemy==2.0.54" in docker
    assert "COPY vertex/cloudsql_audit.py /app/cloudsql_audit.py" in docker


def test_cloud_sql_schema_is_single_canonical_cas_contract():
    sql = (Path(__file__).resolve().parent.parent / "gcp" / "cloudsql" / "001_constitutional_audit_chain_v1.sql").read_text()
    lower = sql.lower()
    assert lower.count("create table if not exists aegis_audit.constitutional_chain_head_v1") == 1
    assert lower.count("create table if not exists aegis_audit.constitutional_chain_v1") == 1
    assert lower.count("create or replace function aegis_audit.append_constitutional_entry_v1") == 1
    assert lower.count("create or replace function aegis_audit.reject_constitutional_chain_mutation_v1") == 1
    assert sql.count("$$") == 6
    assert "^[0-9a-f]{64}$" in sql
    assert "^[0-9a-f]{64}\n" not in sql
    assert "grant select, insert on aegis_audit.constitutional_chain_v1" not in lower
    assert "grant select, update on aegis_audit.constitutional_chain_head_v1" not in lower
