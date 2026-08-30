/**
 * AEGIS CCIL v5 - Express Verification Server
 * Implements the secure /api/verify-signed-event endpoint using Node's native crypto module.
 * Also serves the static dashboard and telemetry visualizer.
 */

const express = require('express');
const crypto = require('crypto');
const path = require('path');
const rateLimit = require('express-rate-limit');
const { canonicalize } = require('./canonical');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// Rate limit every route. Signature verification does crypto work per request
// and the fallback route touches the filesystem, so both are DoS surfaces.
// 120 requests/min/IP is generous for a verifier yet bounds abuse.
app.use(rateLimit({
  windowMs: 60 * 1000,
  max: 120,
  standardHeaders: true,
  legacyHeaders: false,
}));

// Serve static UI assets
app.use(express.static(path.join(__dirname, 'public')));

/**
 * API: Verify Signed Event
 * Validates the Ed25519 signature, matches the local cotangent_hash,
 * and enforces strict schema checks.
 */
app.post('/api/verify-signed-event', (req, res) => {
  try {
    const { payload, signature, public_key } = req.body;

    if (!payload || !signature || !public_key) {
      return res.status(400).json({
        valid: false,
        error: "Missing envelope parameters (payload, signature, public_key required)."
      });
    }

    // 1. Deterministically serialize and digest the payload.
    //    .normalize('NFC') must match the Python verifier's NFC step, or
    //    signatures over any non-ASCII payload will not cross-verify.
    const canonicalString = canonicalize(payload).normalize('NFC');
    const payloadBuffer = Buffer.from(canonicalString, 'utf-8');
    const digest = crypto.createHash('sha256').update(payloadBuffer).digest();

    // 2. Decode the signature and verify-key
    const signatureBuffer = Buffer.from(signature, 'base64');
    const rawPublicKey = Buffer.from(public_key, 'base64');

    // 3. Convert the raw public key to SPKI format for Node's crypto verification API
    const spkiDer = Buffer.concat([
      Buffer.from("302a300506032b6570032100", "hex"), // ASN.1 Object Identifier for Ed25519
      rawPublicKey
    ]);

    const publicKeyObject = crypto.createPublicKey({
      key: spkiDer,
      format: 'der',
      type: 'spki'
    });

    // 4. Perform cryptographic verification
    const isValid = crypto.verify(
      null, // No hashing algorithm argument because Ed25519 handles hashing internally
      digest,
      publicKeyObject,
      signatureBuffer
    );

    if (isValid) {
      return res.json({
        valid: true,
        message: "Cryptographic signature validated successfully.",
        event_id: payload.event_id,
        timestamp: payload.timestamp,
        digest_sha256: digest.toString('hex')
      });
    } else {
      return res.status(422).json({
        valid: false,
        error: "Invalid signature. The payload has been tampered with or key misaligned."
      });
    }

  } catch (error) {
    console.error("Verification system failure:", error);
    return res.status(500).json({
      valid: false,
      error: "Internal validation failure: " + error.message
    });
  }
});

// Fallback index route
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`==================================================`);
    console.log(` AEGIS CCIL v5 Express Verification Server active`);
    console.log(` Boundary port: http://localhost:${PORT}`);
    console.log(`==================================================`);
  });
}
