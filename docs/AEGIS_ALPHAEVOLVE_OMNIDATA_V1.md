# AEGIS Ω × AlphaEvolve — Omnidata Evolution v1

**Issue:** Aegis-Omega/AEGIS-OMEGA#758; dependencies #757 / #734.  **Source work branch:** PR #773.

## What actually runs

1. **All-file bounded intake** of a user-chosen folder. Reversible, exact-byte codec search across *all regular files*, not only CSV/XLSX. The supplied extension catalog recognizes 167 native aliases and 228 compressed variants (overlap means counts should not be summed as distinct formats without care). Unknown formats stay visible, with `NOT_INSPECTED` for unavailable parsers.
2. **Content-preserving evolutionary search:** choose among `identity`, zlib level 1/6, BZip2 level 6, LZMA preset 1 on stratified training bytes, full-file roundtrip verification and exact SHA-256 read-back; rejects compressed outputs that expand the full file. Fitness = stored bytes. This is storage optimization, **not a research-model improvement**.
3. **Real scientific adapters (existing sources):** reuse `agents.alphaevolve_data_fusion_v2` for agent policy (640 rows) and finite quantum bath (240 rows), respecting its pinned input digests and grouped splits. New ablation policy evolves an explicit feature-threshold decision rule over 56 diagnostic rows, with independent lambda configurations separated; finite truncation sensitivity identifies rows changing CG/Davies winner. All remain scientific **NOT_ADMITTED** pending independent evaluation.
4. **Anti-leakage:** compares two purported secular train/holdout CSVs by declared physical configuration (8-decimal key-normalization solely to flag possible leakage); tested source pair has complete 192/192 configuration overlap. There is **no independent holdout** there; promotion denied.
5. **Recoverable data artifact:** `pack_archive(...)` emits `.zip` containing actual compressed payloads and a manifest of byte hashes. `verify_archive(...)` restores by carefully bounded path checking, no overwrite, no code execution. Archive internal hashes detect corruption but **do not authenticate the source publisher**; separately pin archive SHA if distributing externally.

## Reproduce (local, Colab or Kaggle: manually provide a dataset folder)

```bash
python -m agents.alphaevolve_omnidata_v1 \
  --data-root ./datasets \
  --format-catalog ./AEGIS_Dataset_Format_Catalog.json \
  --output ./receipts/omnidata.json
python -m unittest agents.tests.test_alphaevolve_omnidata_v1 -v
```

No cloud/GPU claim is made by running these CPU-only tests. GitHub and connected accounts do not by themselves prove remote notebook kernel execution.

## Limitations and authority

- Reversible codec evolution applies to every supported regular file type. Parsed scientific *meaning* requires a domain evaluator with ground truth and independent holdout; biomedical/genomic/spatial/quantum/gravity dataset metadata must not be treated as evidence of a valid discovery.
- The ablation holdout contains only **2 independent lambda groups**; the quantum policy only 3 groups and agent policy 24 seed clusters in existing local comparison. All are below 30 paired independent evaluations required by issue #758, and no production promotion is authorized.
- Entire corpus in the supplied package: 23 files, **719,888 bytes** originally, **306,783 compressed payload bytes**; after recovery exactly the original 23 file contents, as tested. Archive metadata incurs extra bytes.
- Sensitive data are **not** committed to the source repo: only code, tests and documentation. Results and dataset bytes remain in the local downloadable package unless explicitly approved for publication.
- Not the proprietary Google DeepMind AlphaEvolve product. It's an AEGIS-governed, bounded candidate search inspired by generate → evaluate → select → retain.
- No claims of financial value, validation of physical laws, new medicines, RH proof, commercial revenue, third-party authorization, or production writes.