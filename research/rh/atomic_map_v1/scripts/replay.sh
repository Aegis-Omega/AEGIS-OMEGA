#!/usr/bin/env bash
S="${S:?set S to a scratch dir containing w/order.tsv}"
export PATH=$HOME/.elan/bin:$PATH
cd /home/user/formal-conjectures
BASE="$(lake env printenv LEAN_PATH)"
export LEAN_PATH="$S/olean:$BASE"
: > $S/w/replay.tsv
while IFS=$'\t' read -r name file digest; do
  t0=$(date +%s)
  lean --trust=0 -o "$S/olean/$name.olean" "$file" > "$S/w/log_$name.txt" 2>&1; rc=$?
  t1=$(date +%s)
  printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$rc" "$((t1-t0))" "$digest" "$(grep -c -i 'error' $S/w/log_$name.txt)" >> $S/w/replay.tsv
  [ $rc -ne 0 ] && { echo FAIL $name; break; }
done < $S/w/order.tsv
cat > $S/w/Audit.lean <<'LEAN'
import WeilSeparatedArchBridgeV31
#print axioms AEGIS.WeilSeparatedArchBridgeV31.three_block_bound_of_moments
#print axioms AEGIS.WeilSeparatedArchBridgeV31.three_cross_bounds_of_moments
#print axioms AEGIS.WeilSeparatedArchBridgeV31.three_arch_bounds_of_moments
#print axioms AEGIS.WeilSeparatedArchBridgeV31.translated_arch_norm_bound
#print axioms AEGIS.WeilSeparatedArchBridgeV31.separated_arch_norm_bound
#print axioms AEGIS.WeilSeparatedArchBridgeV31.centered_arch_kernel_bound
#print axioms AEGIS.WeilSeparatedArchBridgeV31.separated_arch_eq_log_kernel
#print axioms AEGIS.WeilWidthArchIntegralV27.width_diagonal_103_over_100_v27
#print axioms AEGIS.WeilWidthArchCorrelationV25.norm_logCorrelation_le_energy_v25
#print axioms AEGIS.WeilThreeBlockCrossPrimeV28.logCross_translate_eq_logCorrelation_v28
#print axioms AEGIS.WeilThreeBlockPrimeEvaluationV30.adjacent_prime_sum_exact
#print axioms AEGIS.WeilThreeBlockPrimeEvaluationV30.outer_prime_sum_exact
#print axioms AEGIS.WeilThreeBlockCrossAssemblyV30.three_block_bound_of_two_arch
#print axioms AEGIS.WeilThreeBlockTranslatedPacketsV22.translate_preserves_moments
LEAN
lean --trust=0 $S/w/Audit.lean > $S/w/audit.log 2>&1; echo "AUDIT_RC $?" >> $S/w/audit.log
echo DONE
