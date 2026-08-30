Verify that all frozen constitutional files remain unmodified.

Run: `node scripts/verify-hashes.mjs`

If all hashes match, report: FROZEN FILES VERIFIED — no modifications detected.

If any hash mismatches, report the affected file, the expected hash, the actual hash,
and: FROZEN FILE VIOLATION — requires /guardian APPROVED verdict before proceeding.
Do not attempt to restore, rewrite, or work around the modified file.
