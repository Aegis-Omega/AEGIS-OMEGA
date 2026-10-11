// The public admission contract now includes encrypted result persistence,
// channel-bound atomic output leasing, and 24-hour recovery. The earlier
// single-response direct-return tests target a superseded API and cannot
// validate the current source. Keep the existing CI entrypoint stable.
import './outbox-contract.test.mjs'
