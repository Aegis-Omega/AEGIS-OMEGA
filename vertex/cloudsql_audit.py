"""AEGIS Cloud SQL authoritative constitutional audit store V1.

No schema mutation is performed by this module. The database schema must already
exist and the runtime IAM database user must already hold aegis_audit_writer.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

GENESIS_HASH = "0" * 64
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_INSTANCE = re.compile(r"^[a-z][a-z0-9-]{4,62}:[a-z0-9-]+:[a-z][a-z0-9-]{0,97}$")
_MODE = {"off", "optional", "required"}


def _bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_cloud_sql_iam_user(value: str) -> str:
    user = value.strip().lower()
    suffix = ".gserviceaccount.com"
    if user.endswith(suffix):
        user = user[: -len(suffix)]
    if not user or "@" not in user:
        raise ValueError("Cloud SQL IAM database user must be an email-style identity")
    return user


def metadata_service_account_email(timeout: float = 1.0) -> str:
    req = urllib.request.Request(
        "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email",
        headers={"Metadata-Flavor": "Google"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310 - GCP metadata endpoint
        value = response.read().decode("utf-8").strip()
    if not value:
        raise RuntimeError("Cloud Run metadata service account email is empty")
    return value


@dataclass(frozen=True)
class CloudSqlAuditConfig:
    mode: str
    instance_connection_name: str
    db_iam_user: str
    db_name: str
    private_ip: bool

    @property
    def enabled(self) -> bool:
        return self.mode != "off"

    @property
    def required(self) -> bool:
        return self.mode == "required"

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        metadata_email: Callable[[], str] | None = None,
    ) -> "CloudSqlAuditConfig":
        source = os.environ if env is None else env
        mode = source.get("CLOUD_SQL_AUDIT_MODE", "off").strip().lower()
        if mode not in _MODE:
            raise ValueError("CLOUD_SQL_AUDIT_MODE must be off, optional, or required")

        instance = (
            source.get("CLOUD_SQL_INSTANCE_CONNECTION_NAME", "").strip()
            or source.get("database_postgresql_CLOUD_SQL_DATABASE_CONNECTION_NAME", "").strip()
        )
        db_name = source.get("CLOUD_SQL_DB_NAME", "default").strip()
        explicit_user = source.get("CLOUD_SQL_IAM_USER", "").strip()

        if mode == "off":
            return cls(mode="off", instance_connection_name=instance, db_iam_user="", db_name=db_name, private_ip=False)

        if not instance or not _INSTANCE.fullmatch(instance):
            raise ValueError("valid Cloud SQL instance connection name is required")
        if not db_name:
            raise ValueError("CLOUD_SQL_DB_NAME must be non-empty")

        if explicit_user:
            iam_user = normalize_cloud_sql_iam_user(explicit_user)
        else:
            resolver = metadata_email or metadata_service_account_email
            iam_user = normalize_cloud_sql_iam_user(resolver())

        return cls(
            mode=mode,
            instance_connection_name=instance,
            db_iam_user=iam_user,
            db_name=db_name,
            private_ip=_bool(source.get("CLOUD_SQL_PRIVATE_IP")),
        )


def _sql(statement: str) -> Any:
    try:
        from sqlalchemy import text
    except ImportError:
        return statement
    return text(statement)


class CloudSqlAuditStore:
    """Transactional, multi-instance-safe append store.

    The singleton chain head row is locked FOR UPDATE. Sequence and predecessor
    are therefore allocated by PostgreSQL, while the application computes the
    existing AEGIS hash format inside the same transaction.
    """

    def __init__(self, engine: Any, connector: Any | None = None):
        self._engine = engine
        self._connector = connector

    @classmethod
    def from_config(cls, config: CloudSqlAuditConfig) -> "CloudSqlAuditStore":
        if not config.enabled:
            raise ValueError("Cloud SQL audit store is disabled")

        from google.cloud.sql.connector import Connector, IPTypes
        import sqlalchemy

        connector = Connector(refresh_strategy="LAZY")
        ip_type = IPTypes.PRIVATE if config.private_ip else IPTypes.PUBLIC

        def getconn() -> Any:
            return connector.connect(
                config.instance_connection_name,
                "pg8000",
                user=config.db_iam_user,
                db=config.db_name,
                enable_iam_auth=True,
                ip_type=ip_type,
            )

        engine = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=2,
            pool_timeout=10,
            pool_recycle=1800,
        )
        return cls(engine=engine, connector=connector)

    def close(self) -> None:
        self._engine.dispose()
        if self._connector is not None:
            self._connector.close()

    def head(self) -> dict[str, Any]:
        with self._engine.connect() as conn:
            row = conn.execute(
                _sql(
                    "select next_sequence, terminal_hash "
                    "from aegis_audit.constitutional_chain_head_v1 "
                    "where chain_id=:chain_id"
                ),
                {"chain_id": "constitutional"},
            ).mappings().one()
        return {
            "next_sequence": int(row["next_sequence"]),
            "terminal_hash": str(row["terminal_hash"]),
        }

    def append(
        self,
        observation: dict[str, Any],
        tier: str,
        timestamp_ms: int,
        compute_hash: Callable[[str, int, dict[str, Any]], str],
    ) -> dict[str, Any]:
        if not isinstance(observation, dict):
            raise TypeError("observation must be object")
        if not isinstance(tier, str) or not tier.strip():
            raise TypeError("tier must be non-empty")
        if not isinstance(timestamp_ms, int) or timestamp_ms < 0:
            raise TypeError("timestamp_ms must be non-negative integer")

        observation_json = json.dumps(
            observation,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        with self._engine.begin() as conn:
            head = conn.execute(
                _sql(
                    "select next_sequence, terminal_hash "
                    "from aegis_audit.constitutional_chain_head_v1 "
                    "where chain_id=:chain_id for update"
                ),
                {"chain_id": "constitutional"},
            ).mappings().one()

            sequence = int(head["next_sequence"])
            previous_hash = str(head["terminal_hash"])
            if not _SHA256.fullmatch(previous_hash):
                raise RuntimeError("invalid durable audit head hash")

            entry_hash = compute_hash(previous_hash, sequence, observation)
            if not _SHA256.fullmatch(entry_hash):
                raise RuntimeError("audit hash callback returned invalid SHA-256")

            conn.execute(
                _sql(
                    "insert into aegis_audit.constitutional_chain_v1 "
                    "(sequence, previous_entry_hash, entry_hash, observation, tier, timestamp_ms) "
                    "values (:sequence, :previous_entry_hash, :entry_hash, "
                    "cast(:observation as jsonb), :tier, :timestamp_ms)"
                ),
                {
                    "sequence": sequence,
                    "previous_entry_hash": previous_hash,
                    "entry_hash": entry_hash,
                    "observation": observation_json,
                    "tier": tier,
                    "timestamp_ms": timestamp_ms,
                },
            )
            result = conn.execute(
                _sql(
                    "update aegis_audit.constitutional_chain_head_v1 "
                    "set next_sequence=:next_sequence, terminal_hash=:terminal_hash, updated_at=now() "
                    "where chain_id=:chain_id and next_sequence=:expected_sequence"
                ),
                {
                    "next_sequence": sequence + 1,
                    "terminal_hash": entry_hash,
                    "chain_id": "constitutional",
                    "expected_sequence": sequence,
                },
            )
            if getattr(result, "rowcount", 1) != 1:
                raise RuntimeError("durable audit head update lost its fence")

        return {
            "sequence": sequence,
            "previous_entry_hash": previous_hash,
            "entry_hash": entry_hash,
            "observation": observation,
            "tier": tier,
            "timestamp_ms": timestamp_ms,
        }

    def get_entry(self, sequence: int) -> dict[str, Any] | None:
        if not isinstance(sequence, int) or sequence < 0:
            raise ValueError("sequence must be non-negative integer")
        with self._engine.connect() as conn:
            row = conn.execute(
                _sql(
                    "select sequence, previous_entry_hash, entry_hash, observation, tier, timestamp_ms "
                    "from aegis_audit.constitutional_chain_v1 where sequence=:sequence"
                ),
                {"sequence": sequence},
            ).mappings().first()
        return dict(row) if row is not None else None

    def tail(self, limit: int = 200) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or limit < 1 or limit > 500:
            raise ValueError("limit must be in [1,500]")
        with self._engine.connect() as conn:
            rows = conn.execute(
                _sql(
                    "select sequence, previous_entry_hash, entry_hash, observation, tier, timestamp_ms "
                    "from (select sequence, previous_entry_hash, entry_hash, observation, tier, timestamp_ms "
                    "from aegis_audit.constitutional_chain_v1 order by sequence desc limit :limit) q "
                    "order by sequence asc"
                ),
                {"limit": limit},
            ).mappings().all()
        return [dict(row) for row in rows]

    def certify(
        self,
        compute_hash: Callable[[str, int, dict[str, Any]], str],
    ) -> dict[str, Any]:
        previous_hash = GENESIS_HASH
        expected_sequence = 0
        terminal_hash = GENESIS_HASH

        with self._engine.connect() as conn:
            rows = conn.execute(
                _sql(
                    "select sequence, previous_entry_hash, entry_hash, observation "
                    "from aegis_audit.constitutional_chain_v1 order by sequence asc"
                )
            ).mappings()

            for row in rows:
                sequence = int(row["sequence"])
                observation = row["observation"]
                if isinstance(observation, str):
                    observation = json.loads(observation)
                if sequence != expected_sequence:
                    return {
                        "is_valid": False,
                        "entry_count": expected_sequence,
                        "terminal_hash": terminal_hash,
                        "failure": "sequence_gap",
                        "tampered_at_sequence": sequence,
                    }
                if row["previous_entry_hash"] != previous_hash:
                    return {
                        "is_valid": False,
                        "entry_count": expected_sequence + 1,
                        "terminal_hash": str(row["entry_hash"]),
                        "failure": "previous_hash_mismatch",
                        "tampered_at_sequence": sequence,
                    }
                expected_hash = compute_hash(previous_hash, sequence, observation)
                if expected_hash != row["entry_hash"]:
                    return {
                        "is_valid": False,
                        "entry_count": expected_sequence + 1,
                        "terminal_hash": str(row["entry_hash"]),
                        "failure": "entry_hash_mismatch",
                        "tampered_at_sequence": sequence,
                    }
                previous_hash = str(row["entry_hash"])
                terminal_hash = previous_hash
                expected_sequence += 1

        head = self.head()
        if head["next_sequence"] != expected_sequence or head["terminal_hash"] != terminal_hash:
            return {
                "is_valid": False,
                "entry_count": expected_sequence,
                "terminal_hash": terminal_hash,
                "failure": "head_mismatch",
            }

        return {
            "is_valid": True,
            "entry_count": expected_sequence,
            "terminal_hash": terminal_hash,
        }
