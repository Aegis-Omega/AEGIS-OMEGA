#!/usr/bin/env python3
"""Build/search a local cross-repository SQLite metadata index. Never executes assets."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import tempfile

HEX = re.compile(r'[0-9a-f]{40}')
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')

def build(snapshot, output, allow_private=False):
    snapshot, output = Path(snapshot), Path(output)
    if snapshot.resolve() == output.resolve():
        raise ValueError('Output cannot replace the source manifest')
    if snapshot.stat().st_size > 20_000_000:
        raise ValueError('Manifest exceeds 20 MB')
    data = json.loads(snapshot.read_text())
    if data.get('schema_version') != 1 or not isinstance(data.get('sources'), list):
        raise ValueError('Unsupported manifest')
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.aegis-catalog-', dir=output.parent)
    os.close(fd)
    try:
        with sqlite3.connect(temporary) as db:
            db.execute('PRAGMA foreign_keys=ON')
            db.executescript('''
              CREATE TABLE source_snapshots (
                repository TEXT NOT NULL, revision TEXT NOT NULL,
                ref TEXT NOT NULL, visibility TEXT NOT NULL, observed_at TEXT NOT NULL,
                PRIMARY KEY(repository, revision));
              CREATE TABLE source_assets (
                repository TEXT NOT NULL, revision TEXT NOT NULL, path TEXT NOT NULL,
                blob_sha TEXT NOT NULL,
                PRIMARY KEY(repository, revision, path),
                FOREIGN KEY(repository, revision) REFERENCES source_snapshots(repository, revision));
              CREATE INDEX assets_blob ON source_assets(blob_sha);
            ''')
            for source in data['sources']:
                repo, revision = source['repository'], source['revision']
                if not REPO.fullmatch(repo) or not HEX.fullmatch(revision):
                    raise ValueError('Invalid source identity')
                if source.get('truncated') is not False:
                    raise ValueError('Incomplete source tree')
                visibility = source['visibility']
                if visibility not in ('public', 'private') or (visibility == 'private' and not allow_private):
                    raise ValueError('Private metadata requires explicit local opt-in')
                db.execute('INSERT INTO source_snapshots VALUES (?,?,?,?,?)',
                           (repo, revision, source['ref'], visibility, data['observed_at']))
                for asset in source['assets']:
                    path, blob = asset['path'], asset['blob_sha']
                    if not path or '\\' in path or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts:
                        raise ValueError('Unsafe asset path')
                    if not HEX.fullmatch(blob):
                        raise ValueError('Invalid blob identity')
                    db.execute('INSERT INTO source_assets VALUES (?,?,?,?)', (repo, revision, path, blob))
            count = db.execute('SELECT count(*) FROM source_assets').fetchone()[0]
        os.replace(temporary, output)
        return count
    finally:
        if os.path.exists(temporary): os.unlink(temporary)

def search(database, query, limit=30):
    uri = Path(database).resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as db:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute('''
          SELECT a.repository,a.revision,a.path,a.blob_sha,s.visibility
          FROM source_assets a JOIN source_snapshots s USING(repository,revision)
          WHERE instr(lower(a.path),lower(?))>0
          ORDER BY a.repository,a.path LIMIT ?''', (query, min(max(limit,1),100)))]

def search_alpha_corpus(database, query, limit=30):
    """Read the existing AlphaEvolve master objects table without copying data.

    Preserve import/quarantine states; an index match is not evaluator admission.
    The caller supplies an already-authorized local catalog, not a remote URL.
    """
    uri = Path(database).resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        db.row_factory = sqlite3.Row
        columns = {r[1] for r in db.execute('PRAGMA table_info(objects)')}
        required = {'id','sha256','category','format','status','member'}
        if required <= columns:
            return [dict(r) for r in db.execute("""
              SELECT id AS source_object_id,sha256,category,format,status,member,
                     'ALPHAEVOLVE_CORPUS_METADATA' AS source_kind
              FROM objects WHERE instr(lower(member),lower(?))>0
              ORDER BY id LIMIT ?""", (query, min(max(limit,1),100)))]
        # The existing evaluated catalog preserves one content record per digest
        # and a separate coverage row for every source object and alias.
        columns = {r[1] for r in db.execute('PRAGMA table_info(assets)')}
        coverage = {r[1] for r in db.execute('PRAGMA table_info(coverage)')}
        required = {'digest','member','category','format','state','science_state','verified'}
        if not required <= columns or not {'object_id','digest','state'} <= coverage:
            raise ValueError('Unsupported AlphaEvolve corpus schema')
        return [dict(r) for r in db.execute("""
          SELECT a.digest AS sha256,a.category,a.format,a.state AS status,a.member,
                 a.science_state,a.verified,
                 (SELECT count(*) FROM coverage c WHERE c.digest=a.digest) AS source_references,
                 'ALPHAEVOLVE_EVALUATED_METADATA' AS source_kind
          FROM assets a WHERE instr(lower(a.member),lower(?))>0
          ORDER BY a.digest LIMIT ?""", (query, min(max(limit,1),100)))]


# Source-bounded metadata-only connector observations; this module never
# calls remote providers or grants execution authority.
from datetime import datetime, timezone

CONNECTOR_STATES = frozenset({
    'CONNECTED_AND_VERIFIED', 'AVAILABLE_UNTESTED', 'NOT_CONNECTED', 'DENIED', 'STALE'
})
CONNECTOR_TYPES = re.compile(r'[a-z][a-z0-9_-]{1,63}\Z')
OPAQUE_DIGEST = re.compile(r'sha256:[0-9a-f]{64}\Z')


def _connector_time(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError('Invalid observation timestamp')
    try:
        when = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('Invalid observation timestamp') from exc
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError('Observation timestamp requires timezone')
    return when.astimezone(timezone.utc)


def ingest_connectors(database, snapshot, allow_private_local=False):
    """Import an explicit metadata-only snapshot into an EXISTING local catalog.

    Raw provider URLs, OAuth tokens, names, messages, file contents and
    credential-bearing identifiers are not accepted. Never publishes a snapshot.
    """
    database, snapshot = Path(database), Path(snapshot)
    if not database.is_file():
        raise ValueError('First build the local source catalog')
    if snapshot.resolve() == database.resolve() or snapshot.stat().st_size > 1_000_000:
        raise ValueError('Unsafe connector manifest')
    data = json.loads(snapshot.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or set(data) != {'schema_version', 'observed_at', 'connectors'} or data['schema_version'] != 1:
        raise ValueError('Unsupported connector manifest')
    observed = _connector_time(data['observed_at'])
    entries = data['connectors']
    if not isinstance(entries, list) or len(entries) > 500:
        raise ValueError('Connector snapshot too large')
    rows, seen = [], set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'provider', 'resource_kind', 'source_ref', 'visibility', 'status', 'source_revision'}:
            raise ValueError('Unsupported connector record fields')
        provider, kind, ref = entry['provider'], entry['resource_kind'], entry['source_ref']
        if not isinstance(provider, str) or not CONNECTOR_TYPES.fullmatch(provider):
            raise ValueError('Invalid provider name')
        if not isinstance(kind, str) or not CONNECTOR_TYPES.fullmatch(kind):
            raise ValueError('Invalid resource kind')
        if ref is not None and (not isinstance(ref, str) or not OPAQUE_DIGEST.fullmatch(ref)):
            raise ValueError('Source reference must be opaque SHA-256; raw links forbidden')
        if entry['status'] not in CONNECTOR_STATES:
            raise ValueError('Unrecognized connector status')
        if entry['status'] == 'CONNECTED_AND_VERIFIED' and ref is None:
            raise ValueError('Verified source requires source identity')
        if entry['visibility'] not in ('public', 'private'):
            raise ValueError('Unrecognized visibility')
        if entry['visibility'] == 'private' and not allow_private_local:
            raise ValueError('Private metadata needs explicit local opt-in')
        revision = entry['source_revision']
        if revision is not None and (not isinstance(revision, str) or not HEX.fullmatch(revision)):
            raise ValueError('Invalid source revision')
        key = (provider, kind, ref or '')
        if key in seen:
            raise ValueError('Duplicate connector identity')
        seen.add(key)
        rows.append((provider, kind, ref or '', entry['visibility'], entry['status'], revision, observed.isoformat()))
    # Validate entire manifest BEFORE beginning local SQLite transaction.
    with sqlite3.connect(database) as db:
        if not {'source_snapshots', 'source_assets'} <= {
            row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }:
            raise ValueError('Database is not an AEGIS source catalog')
        with db:
            db.execute('BEGIN')  # Include table creation in the rollback boundary.
            db.execute('''CREATE TABLE IF NOT EXISTS connector_observations (
                provider TEXT NOT NULL, resource_kind TEXT NOT NULL,
                source_ref TEXT NOT NULL, visibility TEXT NOT NULL,
                status TEXT NOT NULL, source_revision TEXT,
                observed_at TEXT NOT NULL,
                PRIMARY KEY(provider,resource_kind,source_ref))''')
            for row in rows:
                prior = db.execute('''SELECT visibility,status,source_revision,observed_at
                    FROM connector_observations
                    WHERE provider=? AND resource_kind=? AND source_ref=?''', row[:3]).fetchone()
                if prior is not None:
                    old_time = _connector_time(prior[3])
                    if observed < old_time:
                        raise ValueError('Older connector snapshot cannot replace newer evidence')
                    if observed == old_time and tuple(row[3:6]) != tuple(prior[:3]):
                        # An equal-time explicit denial may strengthen the prior state,
                        # but cannot retract it or change source identity/provenance.
                        if not (row[4] == 'DENIED' and prior[1] != 'DENIED' and
                                row[3] == prior[0] and row[5] == prior[2]):
                            raise ValueError('Conflicting evidence at identical observation time')
            db.executemany('''INSERT INTO connector_observations VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(provider,resource_kind,source_ref) DO UPDATE SET
                visibility=excluded.visibility, status=excluded.status,
                source_revision=excluded.source_revision,
                observed_at=excluded.observed_at''', rows)
    return len(rows)


def search_connectors(database, provider='', max_age_minutes=1440, limit=30, now=None):
    """Read-only lookup; stale observations never masquerade as current."""
    if not isinstance(provider, str) or (provider and not CONNECTOR_TYPES.fullmatch(provider)):
        raise ValueError('Invalid provider filter')
    if not isinstance(max_age_minutes, int) or max_age_minutes < 0 or max_age_minutes > 525600:
        raise ValueError('Invalid freshness window')
    now = _connector_time(now or datetime.now(timezone.utc).isoformat())
    uri = Path(database).resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        db.row_factory = sqlite3.Row
        items = [dict(r) for r in db.execute('''SELECT * FROM connector_observations
            WHERE (? = '' OR provider = ?) ORDER BY provider,resource_kind,source_ref
            LIMIT ?''', (provider, provider, min(max(limit, 1), 100)))]
    for item in items:
        delta = (now - _connector_time(item['observed_at'])).total_seconds()
        item['effective_status'] = 'STALE' if delta < -60 or delta > max_age_minutes * 60 else item['status']
    return items

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database', type=Path, required=True)
    p.add_argument('--snapshot', type=Path)
    p.add_argument('--allow-private-local', action='store_true')
    p.add_argument('--search')
    p.add_argument('--connector-snapshot', type=Path, help='Import an explicit local metadata-only connector snapshot')
    p.add_argument('--connector-query', nargs='?', const='', help='Search locally indexed connector status by provider')
    p.add_argument('--allow-private-connectors-local', action='store_true')
    p.add_argument('--alpha-corpus', type=Path, help='Read-only existing AlphaEvolve corpus.sqlite')
    a=p.parse_args()
    if a.snapshot:
        print(json.dumps({'indexed_assets':build(a.snapshot,a.database,a.allow_private_local)}))
    if a.connector_snapshot is not None:
        print(json.dumps({'indexed_connectors':ingest_connectors(a.database,a.connector_snapshot,a.allow_private_connectors_local)}))
    if a.connector_query is not None:
        print(json.dumps({'connectors':search_connectors(a.database,a.connector_query)},indent=2))
    if a.search is not None:
        result = {'git_sources': search(a.database,a.search)}
        if a.alpha_corpus is not None:
            result['alphaevolve_sources'] = search_alpha_corpus(a.alpha_corpus,a.search)
        print(json.dumps(result,indent=2))
    if a.snapshot is None and a.search is None and a.connector_snapshot is None and a.connector_query is None:
        p.error('Supply --snapshot, --search, --connector-snapshot or --connector-query')

if __name__=='__main__': main()
