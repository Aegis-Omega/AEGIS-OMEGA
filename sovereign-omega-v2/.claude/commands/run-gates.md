Run the sovereign-runtime build gates in sequence. Stop immediately on any failure and report the result.

Execute each gate in order:

Gate 1: `npm run test -- --reporter=verbose test/unit/jcs.test.ts`
Gate 2: `npm run test -- test/unit/sequence.test.ts`
Gate 3: `npm run test -- test/unit/immutable.test.ts`
Gate 4: `npm run test -- test/unit/reducer.test.ts`
Gate 5: `npm run test -- test/unit/vcg.test.ts`
Gate 6: `npm run test -- test/unit/gate.test.ts`
Gate 7: `npm run test -- test/integration/replay.test.ts test/integration/pipeline.test.ts`
Gate 8: `npm run test && npm run typecheck && npm run build`

For each gate, report:
- GATE [N]: PASSED or FAILED
- Command run
- Pass count or error output
- Action: PROCEED or HALT — reason

If all eight gates pass, report: ALL GATES PASSED — system is deployment-ready.
If any gate fails, report: GATE [N] FAILED — halting. Do not proceed past the failure.
