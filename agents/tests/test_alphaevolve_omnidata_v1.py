"""Hostile-input and real calculation tests for AEGIS omnidata evolution."""
import bz2
import csv
import io
import json
import lzma
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

from agents.alphaevolve_omnidata_v1 import (
    CODECS, ablation_search, bounded_decompress, classify, compress, digest,
    evolution_of_bytes, extension_registry, file_bytes, leakage_overlap,
    pack_archive, run, sha256, structural_inspection, truncation_stability,
    verify_archive,
)


class OmniDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def sample_catalog(self):
        path=self.root/"formats.json"
        path.write_text(json.dumps({"schema":"AEGIS_FORMAT_CATALOG_V1",
            "groups":{"tabular":{"CSV":[".csv"],"PARQUET":[".pq"]},
            "structured":{"JSONL":[".jsonl"]},
            "genomics":{"FASTA":[".fasta"]}}}),encoding="utf-8")
        return path

    def test_lossless_codecs_full_bytes(self):
        data=(b"ACGT"*700)+b"\x00\xff"
        for codec in CODECS:
            with self.subTest(codec=codec):
                blob=compress(data,codec)
                self.assertEqual(bounded_decompress(blob,codec,len(data)),data)

    def test_codec_search_never_expands_large_source(self):
        v=evolution_of_bytes(b"SOVEREIGN\n"*2500)
        self.assertEqual(v["roundtrip"],"BYTE_EXACT_PASS")
        self.assertGreater(v["saved_bytes"],100)
        self.assertIn(v["candidate_codec"],CODECS)

    def test_empty_bytes_preserved(self):
        v=evolution_of_bytes(b"")
        self.assertEqual(v["source_bytes"],v["candidate_bytes"])

    def test_bomb_fails_bounded_decoder(self):
        raw=b"A"*300_000
        for codec in ("zlib6","bz26","lzma1"):
            with self.subTest(codec=codec),self.assertRaises(ValueError):
                bounded_decompress(compress(raw,codec),codec,1024)

    def test_bad_codec_rejected(self):
        with self.assertRaisesRegex(ValueError,"DECODE_BUDGET_INVALID"):
            bounded_decompress(b"z", "pickle", 10)

    def test_catalog_unknown_not_hidden(self):
        registry=extension_registry(self.sample_catalog())
        self.assertEqual(classify("sample.fasta",registry)["format"],"FASTA")
        self.assertEqual(classify("sample.csv.gz",registry)["recognition"],"CATALOG_COMPRESSED_VARIANT")
        self.assertEqual(classify("mystery.blob",registry)["recognition"],"NOT_IN_CATALOG")

    def test_catalog_malformed_rejected(self):
        path=self.root/"bad.json"
        path.write_text('{"schema":"UNTRUSTED","groups":{}}')
        with self.assertRaises(ValueError):
            extension_registry(path)

    def test_csv_structural_validation_and_nan_signal(self):
        p=self.root/"data.csv"
        bad=b"x,y\n1,NaN\n2,3\n"
        x=structural_inspection(p,bad,{"recognition":"CATALOG"})
        self.assertEqual(x["nonfinite_literals"],1)
        self.assertEqual(x["row_count"],2)
        self.assertEqual(structural_inspection(p,b"x,x\n1,2\n",{})["parse"],"REJECTED")

    def test_notebook_never_executes_cells(self):
        p=self.root/"x.ipynb"
        data={"nbformat":4,"cells":[{"cell_type":"code","source":"raise RuntimeError('bad')"}]}
        x=structural_inspection(p,json.dumps(data).encode(),{})
        self.assertEqual(x["code_cells"],1)
        self.assertIn("DISABLED",x["execution"])

    def test_leakage_detects_float_rounding_collision(self):
        a=b"bath_family,J\nsub,0.20000000000001\n"
        b=b"bath_family,J\nsub,0.2\n"
        x=leakage_overlap(a,b,("bath_family","J"))
        self.assertEqual(x["overlap_configs"],1)
        self.assertEqual(x["independent_holdout"],"DENIED")

    def test_leakage_no_match_not_promoted(self):
        a=b"J\n1\n"; b=b"J\n2\n"
        x=leakage_overlap(a,b,("J",))
        self.assertEqual(x["independent_holdout"],"NOT_ESTABLISHED")
        self.assertEqual(x["scientific_promotion"],"DENIED")

    def test_ablation_evolves_only_on_train_lambda_groups(self):
        records=[]
        for k in range(7):
            for i in range(8):
                records.append({"lambda":str(0.01+k*.01),"R":str(i),
                    "abs_sinc_chi_dom":str(i/10),
                    "baseline_error":"0.12","ablated_error":"0.08" if i%2==0 else "0.2",
                    "baseline_status":"WITHIN_BUDGET","ablated_status":"WITHIN_BUDGET"})
        output=io.StringIO();w=csv.DictWriter(output,fieldnames=records[0]);w.writeheader();w.writerows(records)
        x=ablation_search(output.getvalue().encode())
        self.assertEqual(len(x["train_lambda_groups"]),3)
        self.assertEqual(len(x["validation_lambda_groups"]),2)
        self.assertEqual(len(x["holdout_lambda_groups"]),2)
        self.assertEqual(x["promotion"],"DENIED")

    def test_ablation_rejects_nan(self):
        head="lambda,R,abs_sinc_chi_dom,baseline_error,ablated_error,baseline_status,ablated_status\n"
        row="0.1,4,NaN,0.1,0.2,WITHIN_BUDGET,WITHIN_BUDGET\n"
        with self.assertRaisesRegex(ValueError,"NONFINITE_SCIENCE_FIELD"):
            ablation_search((head+row).encode())

    def test_truncation_switch_count(self):
        header="winner_ref_2lvl3mode,winner_ref_3lvl3mode,winner_ref_2lvl4mode\n"
        body="CG,CG,CG\nCG,DAVIES,CG\n"
        x=truncation_stability((header+body).encode())
        self.assertEqual((x["stable_winner_rows"],x["winner_changes_across_truncations"]),(1,1))

    def test_source_symlink_rejected(self):
        p=self.root/"normal.csv";p.write_bytes(b"h\n1\n")
        link=self.root/"link.csv";link.symlink_to(p)
        with self.assertRaisesRegex(ValueError,"NONREGULAR_OR_SYMLINK"):
            file_bytes(link)

    def test_archive_roundtrip_and_no_overwrite(self):
        (self.root/"test.csv").write_bytes(b"a,b\n"+b"1,2\n"*128)
        (self.root/"mysterious.xyz").write_bytes(b"\x00\x01\xff"*71)
        catalog=self.sample_catalog()
        x=run(self.root,catalog=catalog,enable_selected_science=False)
        archive=self.root.parent/(self.root.name+"_test.aegis.zip")
        self.addCleanup(lambda:archive.unlink(missing_ok=True))
        packed=pack_archive(self.root,x,archive)
        self.assertEqual(packed["files"],len(x["dataset_records"]))
        target=self.root/"restored"
        result=verify_archive(archive,restore_root=target)
        self.assertEqual(result["verified_files"],len(x["dataset_records"]))
        self.assertEqual((target/"test.csv").read_bytes(),(self.root/"test.csv").read_bytes())
        with self.assertRaisesRegex(ValueError,"RESTORE_TARGET_ALREADY_EXISTS"):
            verify_archive(archive,restore_root=target)

    def test_archive_manifest_external_hash_rejected(self):
        (self.root/"small.csv").write_text("a\n1\n")
        x=run(self.root,enable_selected_science=False)
        archive=self.root.parent/(self.root.name+"_h.aegis.zip")
        self.addCleanup(lambda:archive.unlink(missing_ok=True))
        pack_archive(self.root,x,archive)
        with self.assertRaisesRegex(ValueError,"EXTERNAL_MANIFEST_SHA_MISMATCH"):
            verify_archive(archive,expected_manifest_sha="a"*64)

    def test_archive_path_traversal_rejected(self):
        dest=self.root/"evil.zip"
        manifest={"schema":"AEGIS_OMNIDATA_LOSSLESS_ARCHIVE_V1",
                  "files":[{"path":"../hijack","codec":"identity","sha256":sha256(b"x"),
                            "source_size":1,"compressed_size":1}]}
        with zipfile.ZipFile(dest,"w") as z:
            z.writestr("manifest.json",json.dumps(manifest))
            z.writestr("objects/000000.bin",b"x")
        with self.assertRaisesRegex(ValueError,"UNSAFE_ARCHIVE_PATH"):
            verify_archive(dest)

    def test_digest_deterministic_and_sensitive(self):
        self.assertEqual(digest({"a":3}),digest({"a":3}))
        self.assertNotEqual(digest({"a":3}),digest({"a":4}))


if __name__=="__main__":
    unittest.main()