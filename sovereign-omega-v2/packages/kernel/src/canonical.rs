// ============================================================
// AEGIS Ω — RFC 8785 JSON Canonicalization
// EPISTEMIC TIER: T0
// Byte-identical port of canonicalizeJCS from src/core/canonicalize.ts.
// Parses JSON bytes, sorts object keys by UTF-16 code unit order,
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
                Some(b) if b.is_ascii() => result.push(b as char),
                Some(_) => {
                    // Input was validated as UTF-8 before parsing.
                    let start = self.pos - 1;
                    let rest = core::str::from_utf8(&self.input[start..])
                        .expect("source UTF-8 validated");
                    let ch = rest.chars().next().expect("nonempty UTF-8 scalar");
                    result.push(ch);
                    self.pos += ch.len_utf8() - 1;
                },
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

        // RFC 8785 sec. 3.2.3 requires UTF-16 code-unit order.
        pairs.sort_by(|a, b| a.0.encode_utf16().cmp(b.0.encode_utf16()));

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
        return "0".to_string(); // both +0.0 and -0.0
    }

    // Rust Display provides shortest round-tripping decimal digits for f64
    // but not ECMAScript's fixed/scientific formatting thresholds.
    // RFC 8785 requires the shortest digits in ES2020 Number::toString layout.
    let raw = v.abs().to_string();
    let (mantissa, exponent) = match raw.find(|ch: char| ch == 'e' || ch == 'E') {
        Some(i) => (&raw[..i], raw[i + 1..].parse::<i32>().expect("decimal exponent")),
        None => (raw.as_str(), 0),
    };

    let mut digits = String::new();
    let mut decimal_point = None;
    for ch in mantissa.chars() {
        if ch == '.' {
            decimal_point = Some(digits.len() as i32);
        } else {
            debug_assert!(ch.is_ascii_digit(), "f64 Display emits decimal digits");
            digits.push(ch);
        }
    }
    let mut n = decimal_point.unwrap_or(digits.len() as i32) + exponent;

    // Normalize "0.00001230" to digits="123" and n=-4.
    let leading_zeros = digits.bytes().take_while(|b| *b == b'0').count();
    digits.drain(..leading_zeros);
    n -= leading_zeros as i32;
    while digits.ends_with('0') {
        digits.pop();
    }
    if digits.is_empty() {
        return "0".to_string();
    }

    let k = digits.len() as i32;
    let formatted = if k <= n && n <= 21 {
        format!("{}{}", digits, "0".repeat((n - k) as usize))
    } else if 0 < n && n <= 21 {
        format!("{}.{}", &digits[..n as usize], &digits[n as usize..])
    } else if -6 < n && n <= 0 {
        format!("0.{}{}", "0".repeat((-n) as usize), digits)
    } else {
        let mantissa = if k == 1 {
            digits
        } else {
            format!("{}.{}", &digits[..1], &digits[1..])
        };
        let e = n - 1;
        if e >= 0 {
            format!("{}e+{}", mantissa, e)
        } else {
            format!("{}e{}", mantissa, e)
        }
    };
    if v.is_sign_negative() {
        format!("-{}", formatted)
    } else {
        formatted
    }
}

#[cfg(test)]
mod rfc8785_unicode_regressions {
    use super::canonicalize_json;

    fn canonical(s: &str) -> String {
        String::from_utf8(canonicalize_json(s.as_bytes())).unwrap()
    }

    #[test]
    fn non_bmp_key_precedes_bmp_private_use() {
        let input = r#"{"\uE000":1,"😀":2}"#;
        let expected = format!("{{\"😀\":2,\"{}\":1}}", '\u{E000}');
        assert_eq!(canonical(input), expected);
    }

    #[test]
    fn raw_utf8_multibyte_keys_and_values() {
        assert_eq!(
            canonical(r#"{"😀":"漢字","é":"🧪"}"#),
            r#"{"é":"🧪","😀":"漢字"}"#
        );
    }

    #[test]
    fn escaped_surrogate_pair_order() {
        let input = r#"{"\uE000":1,"\uD83D\uDE00":2}"#;
        let expected = format!("{{\"😀\":2,\"{}\":1}}", '\u{E000}');
        assert_eq!(canonical(input), expected);
    }

    #[test]
    fn nested_objects_preserve_unicode_values() {
        let input = r#"{"outer":[{"\uE000":"漢","😀":"字"}],"a":1}"#;
        let expected = format!(
            "{{\"a\":1,\"outer\":[{{\"😀\":\"字\",\"{}\":\"漢\"}}]}}",
            '\u{E000}'
        );
        assert_eq!(canonical(input), expected);
    }
}

#[cfg(test)]
mod rfc8785_numeric_regressions {
    use super::canonicalize_json;

    fn canonical(s: &str) -> String {
        String::from_utf8(canonicalize_json(s.as_bytes())).unwrap()
    }

    #[test]
    fn es2020_scientific_notation_thresholds() {
        assert_eq!(canonical("1e21"), "1e+21");
        assert_eq!(canonical("1e-7"), "1e-7");
        assert_eq!(canonical("1e-6"), "0.000001");
        assert_eq!(canonical("1e20"), "100000000000000000000");
    }

    #[test]
    fn javascript_negative_zero_and_signed_exponents() {
        assert_eq!(canonical("-0"), "0");
        assert_eq!(canonical("-1e21"), "-1e+21");
        assert_eq!(canonical("1.25e-7"), "1.25e-7");
    }
    #[test]
    fn extra_jcs_numeric_vectors() {
        let vectors = [
            ("1e21", "1e+21"),
            ("-1e21", "-1e+21"),
            ("1e20", "100000000000000000000"),
            ("1e22", "1e+22"),
            ("1e-6", "0.000001"),
            ("1e-7", "1e-7"),
            ("1.25e-7", "1.25e-7"),
            ("1.7976931348623157e308", "1.7976931348623157e+308"),
            ("2.2250738585072014e-308", "2.2250738585072014e-308"),
            ("5e-324", "5e-324"),
            ("1e308", "1e+308"),
            ("1e-308", "1e-308"),
            ("9007199254740991", "9007199254740991"),
            ("9007199254740992", "9007199254740992"),
            ("333333333.33333329", "333333333.3333333"),
            ("0.000001", "0.000001"),
            ("0.0000001", "1e-7"),
            ("-0", "0"),
            ("1.2345678901234567", "1.2345678901234567"),
            ("0.000001234", "0.000001234"),
            ("0.0000001234", "1.234e-7"),
            ("1234567890123456789", "1234567890123456800"),
            ("-1e-8", "-1e-8"),
            ("1.25e-6", "0.00000125"),
            ("4.50e21", "4.5e+21"),
            ("1.0000000000000002", "1.0000000000000002"),
        ];
        for (raw, expected) in vectors {
            assert_eq!(canonical(raw), expected, "input {raw}");
        }
    }

}
