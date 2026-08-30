// ============================================================
// AEGIS Ω — RFC 8785 JSON Canonicalization
// EPISTEMIC TIER: T0
// Byte-identical port of canonicalizeJCS from src/core/canonicalize.ts.
// Parses JSON bytes, sorts object keys by Unicode code point order,
// and re-serializes with minimal whitespace and canonical escaping.
// ============================================================

/// Canonicalize UTF-8 JSON bytes per RFC 8785.
/// Returns canonical UTF-8 bytes with keys sorted lexicographically.
pub fn canonicalize_json(input: &[u8]) -> Vec<u8> {
    let s = match core::str::from_utf8(input) {
        Ok(s) => s,
        Err(_) => return input.to_vec(), // pass-through on invalid UTF-8
    };
    let mut parser = Parser::new(s.trim());
    let mut out = Vec::new();
    parser.parse_value(&mut out);
    out
}

struct Parser<'a> {
    input: &'a [u8],
    pos: usize,
}

impl<'a> Parser<'a> {
    fn new(s: &'a str) -> Self {
        Parser { input: s.as_bytes(), pos: 0 }
    }

    fn peek(&self) -> Option<u8> {
        self.input.get(self.pos).copied()
    }

    fn advance(&mut self) -> Option<u8> {
        let b = self.peek()?;
        self.pos += 1;
        Some(b)
    }

    fn skip_ws(&mut self) {
        while let Some(b) = self.peek() {
            if matches!(b, b' ' | b'\t' | b'\n' | b'\r') {
                self.pos += 1;
            } else {
                break;
            }
        }
    }

    fn parse_value(&mut self, out: &mut Vec<u8>) {
        self.skip_ws();
        match self.peek() {
            Some(b'{') => self.parse_object(out),
            Some(b'[') => self.parse_array(out),
            Some(b'"') => self.parse_string_canonical(out),
            Some(b'n') => { self.pos += 4; out.extend_from_slice(b"null"); }
            Some(b't') => { self.pos += 4; out.extend_from_slice(b"true"); }
            Some(b'f') => { self.pos += 5; out.extend_from_slice(b"false"); }
            Some(b'-') | Some(b'0'..=b'9') => self.parse_number(out),
            _ => {}
        }
    }

    /// Parse a JSON string and return as Rust String (with escapes decoded).
    fn parse_string_raw(&mut self) -> String {
        debug_assert_eq!(self.peek(), Some(b'"'));
        self.pos += 1; // consume opening quote

        let mut result = String::new();
        loop {
            match self.advance() {
                Some(b'"') => break,
                Some(b'\\') => match self.advance() {
                    Some(b'"')  => result.push('"'),
                    Some(b'\\') => result.push('\\'),
                    Some(b'/')  => result.push('/'),
                    Some(b'b')  => result.push('\x08'),
                    Some(b't')  => result.push('\t'),
                    Some(b'n')  => result.push('\n'),
                    Some(b'f')  => result.push('\x0c'),
                    Some(b'r')  => result.push('\r'),
                    Some(b'u')  => {
                        let code = self.parse_hex4();
                        if (0xD800..=0xDBFF).contains(&code) {
                            // High surrogate — read low surrogate \uXXXX
                            if self.peek() == Some(b'\\') { self.pos += 1; }
                            if self.peek() == Some(b'u')  { self.pos += 1; }
                            let low = self.parse_hex4();
                            let scalar = 0x10000u32
                                + ((code - 0xD800) << 10)
                                + (low - 0xDC00);
                            result.push(char::from_u32(scalar).unwrap_or('\u{FFFD}'));
                        } else {
                            result.push(char::from_u32(code).unwrap_or('\u{FFFD}'));
                        }
                    }
                    _ => {}
                },
                Some(b) => result.push(b as char),
                None => break,
            }
        }
        result
    }

    fn parse_hex4(&mut self) -> u32 {
        let mut code = 0u32;
        for _ in 0..4 {
            let d = match self.advance() {
                Some(b @ b'0'..=b'9') => (b - b'0') as u32,
                Some(b @ b'a'..=b'f') => (b - b'a' + 10) as u32,
                Some(b @ b'A'..=b'F') => (b - b'A' + 10) as u32,
                _ => 0,
            };
            code = code * 16 + d;
        }
        code
    }

    /// Serialize a Rust String with RFC 8785 / JSON canonical escaping.
    fn write_canonical_string(s: &str, out: &mut Vec<u8>) {
        out.push(b'"');
        for ch in s.chars() {
            let cp = ch as u32;
            match ch {
                '"'    => out.extend_from_slice(b"\\\""),
                '\\'   => out.extend_from_slice(b"\\\\"),
                '\x08' => out.extend_from_slice(b"\\b"),
                '\t'   => out.extend_from_slice(b"\\t"),
                '\n'   => out.extend_from_slice(b"\\n"),
                '\x0c' => out.extend_from_slice(b"\\f"),
                '\r'   => out.extend_from_slice(b"\\r"),
                _ if cp < 0x20 => {
                    // Other control characters: \uXXXX
                    out.extend_from_slice(b"\\u");
                    let hex = format!("{:04x}", cp);
                    out.extend_from_slice(hex.as_bytes());
                }
                _ => {
                    // BMP and non-BMP characters: encode as UTF-8
                    let mut buf = [0u8; 4];
                    let s = ch.encode_utf8(&mut buf);
                    out.extend_from_slice(s.as_bytes());
                }
            }
        }
        out.push(b'"');
    }

    /// Parse and re-emit a JSON string with canonical escaping.
    fn parse_string_canonical(&mut self, out: &mut Vec<u8>) {
        let s = self.parse_string_raw();
        Self::write_canonical_string(&s, out);
    }

    fn parse_object(&mut self, out: &mut Vec<u8>) {
        debug_assert_eq!(self.peek(), Some(b'{'));
        self.pos += 1; // consume '{'
        self.skip_ws();

        if self.peek() == Some(b'}') {
            self.pos += 1;
            out.extend_from_slice(b"{}");
            return;
        }

        // Collect all key-value pairs
        let mut pairs: Vec<(String, Vec<u8>)> = Vec::new();

        loop {
            self.skip_ws();
            let key = self.parse_string_raw();
            self.skip_ws();
            // consume ':'
            if self.peek() == Some(b':') { self.pos += 1; }
            self.skip_ws();
            let mut val = Vec::new();
            self.parse_value(&mut val);
            pairs.push((key, val));
            self.skip_ws();
            match self.peek() {
                Some(b',') => { self.pos += 1; }
                _ => break,
            }
        }
        // consume '}'
        if self.peek() == Some(b'}') { self.pos += 1; }

        // Sort keys by Unicode code point sequence (RFC 8785)
        pairs.sort_by(|a, b| {
            let mut ai = a.0.chars();
            let mut bi = b.0.chars();
            loop {
                match (ai.next(), bi.next()) {
                    (None, None) => return core::cmp::Ordering::Equal,
                    (None, _)   => return core::cmp::Ordering::Less,
                    (_, None)   => return core::cmp::Ordering::Greater,
                    (Some(ac), Some(bc)) => {
                        let ord = (ac as u32).cmp(&(bc as u32));
                        if ord != core::cmp::Ordering::Equal { return ord; }
                    }
                }
            }
        });

        out.push(b'{');
        for (i, (key, val)) in pairs.iter().enumerate() {
            if i > 0 { out.push(b','); }
            Self::write_canonical_string(key, out);
            out.push(b':');
            out.extend_from_slice(val);
        }
        out.push(b'}');
    }

    fn parse_array(&mut self, out: &mut Vec<u8>) {
        debug_assert_eq!(self.peek(), Some(b'['));
        self.pos += 1; // consume '['
        self.skip_ws();

        if self.peek() == Some(b']') {
            self.pos += 1;
            out.extend_from_slice(b"[]");
            return;
        }

        out.push(b'[');
        let mut first = true;
        loop {
            self.skip_ws();
            if !first { out.push(b','); }
            first = false;
            self.parse_value(out);
            self.skip_ws();
            match self.peek() {
                Some(b',') => { self.pos += 1; }
                _ => break,
            }
        }
        if self.peek() == Some(b']') { self.pos += 1; }
        out.push(b']');
    }

    fn parse_number(&mut self, out: &mut Vec<u8>) {
        // Read raw number token
        let start = self.pos;
        if self.peek() == Some(b'-') { self.pos += 1; }
        while let Some(b'0'..=b'9') = self.peek() { self.pos += 1; }
        if self.peek() == Some(b'.') {
            self.pos += 1;
            while let Some(b'0'..=b'9') = self.peek() { self.pos += 1; }
        }
        if matches!(self.peek(), Some(b'e') | Some(b'E')) {
            self.pos += 1;
            if matches!(self.peek(), Some(b'+') | Some(b'-')) { self.pos += 1; }
            while let Some(b'0'..=b'9') = self.peek() { self.pos += 1; }
        }
        let num_str = core::str::from_utf8(&self.input[start..self.pos]).unwrap_or("0");

        // Parse as f64 then re-serialize as per RFC 8785 / JS Number::toString
        let v: f64 = num_str.parse().unwrap_or(0.0);
        let canonical = format_number_js(v);
        out.extend_from_slice(canonical.as_bytes());
    }
}

/// Format f64 as JavaScript Number::toString would — shortest round-trip decimal.
/// Special case: -0.0 → "0" (RFC 8785).
fn format_number_js(v: f64) -> String {
    if v == 0.0 {
        return "0".to_string(); // handles both 0.0 and -0.0
    }
    // For integer values representable without loss, use integer format
    if v.fract() == 0.0 && v.abs() < 1.0e15 {
        return format!("{}", v as i64);
    }
    // For general floats: Rust's default f64 Display uses the Grisu3/Dragon4
    // shortest-round-trip algorithm — matches JavaScript for common values.
    let s = format!("{}", v);
    // Normalize exponent notation to match JavaScript (e.g. "1e20" not "1E20")
    if let Some(e_pos) = s.find('e') {
        let mantissa = &s[..e_pos];
        let exp_str = &s[e_pos + 1..];
        let exp: i32 = exp_str.parse().unwrap_or(0);
        if exp >= 0 {
            return format!("{}e+{}", mantissa, exp);
        } else {
            return format!("{}e{}", mantissa, exp);
        }
    }
    s
}
