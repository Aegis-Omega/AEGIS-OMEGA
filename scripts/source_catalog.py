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

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database', type=Path, required=True)
    p.add_argument('--snapshot', type=Path)
    p.add_argument('--allow-private-local', action='store_true')
    p.add_argument('--search')
    p.add_argument('--alpha-corpus', type=Path, help='Read-only existing AlphaEvolve corpus.sqlite')
    a=p.parse_args()
    if a.snapshot:
        print(json.dumps({'indexed_assets':build(a.snapshot,a.database,a.allow_private_local)}))
    if a.search is not None:
        result = {'git_sources': search(a.database,a.search)}
        if a.alpha_corpus is not None:
            result['alphaevolve_sources'] = search_alpha_corpus(a.alpha_corpus,a.search)
        print(json.dumps(result,indent=2))
    if a.snapshot is None and a.search is None: p.error('Supply --snapshot or --search')

if __name__=='__main__': main()
