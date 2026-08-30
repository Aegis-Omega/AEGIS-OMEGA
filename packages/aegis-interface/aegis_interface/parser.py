"""WIT-subset parser — RFC 0001 §4 Interface Definition Layer.

Recognises the contract surface defined by the RFC: named records and
variants composed of primitive types, plus ``list<T>`` / ``option<T>``
wrappers and an ``@range(min, max)`` constraint annotation. The grammar is
deliberately small; it is the *only* place WIT syntax is interpreted.

Grammar (EBNF)::

    file        := typedef*
    typedef     := record_def | variant_def
    record_def  := ("record" | "interface") IDENT "{" field_list "}"
    variant_def := "variant" IDENT "{" case_list "}"
    field_list  := (annotation? field ","?)*
    field       := IDENT ":" type
    case_list   := (IDENT ","?)*
    type        := ("list" | "option") "<" type ">" | IDENT
    annotation  := "@range" "(" NUMBER "," NUMBER ")"

Line comments (``// ...``) are permitted anywhere and discarded.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Optional


class ParseError(ValueError):
    """Raised on any malformed WIT input. Carries line/column context."""


# --------------------------------------------------------------------------- #
# AST
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TypeRef:
    """A type reference: a leaf name or a single-argument wrapper.

    ``wrapper`` is ``None`` for leaves (``string``, ``MyRecord``), or
    ``"list"`` / ``"option"`` for the parametric forms, in which case
    ``inner`` holds the element type.
    """

    name: str
    wrapper: Optional[str] = None
    inner: Optional["TypeRef"] = None


@dataclass(frozen=True)
class Range:
    min: float
    max: float


@dataclass
class Field:
    name: str
    type: TypeRef
    range: Optional[Range] = None


@dataclass
class Record:
    name: str
    fields: list[Field] = dc_field(default_factory=list)


@dataclass
class Variant:
    name: str
    cases: list[str] = dc_field(default_factory=list)


@dataclass
class Document:
    records: list[Record] = dc_field(default_factory=list)
    variants: list[Variant] = dc_field(default_factory=list)


# --------------------------------------------------------------------------- #
# Tokeniser
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Token:
    kind: str  # "ident" | "number" | "punct"
    value: str
    line: int
    col: int


_PUNCT = set("{}<>(),:@")


def _tokenize(src: str) -> list[Token]:
    tokens: list[Token] = []
    line = 1
    col = 1
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        if ch == "\n":
            line += 1
            col = 1
            i += 1
            continue
        if ch in " \t\r":
            i += 1
            col += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if ch in _PUNCT:
            tokens.append(Token("punct", ch, line, col))
            i += 1
            col += 1
            continue
        if ch.isdigit() or (ch in "+-." and i + 1 < n and (src[i + 1].isdigit() or src[i + 1] == ".")):
            start = i
            start_col = col
            i += 1
            col += 1
            while i < n and (src[i].isdigit() or src[i] in ".eE+-"):
                i += 1
                col += 1
            tokens.append(Token("number", src[start:i], line, start_col))
            continue
        if ch.isalpha() or ch == "_":
            start = i
            start_col = col
            i += 1
            col += 1
            while i < n and (src[i].isalnum() or src[i] == "_"):
                i += 1
                col += 1
            tokens.append(Token("ident", src[start:i], line, start_col))
            continue
        raise ParseError(f"unexpected character {ch!r} at line {line}, col {col}")
    return tokens


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
class _Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> Optional[Token]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self) -> Token:
        tok = self._peek()
        if tok is None:
            raise ParseError("unexpected end of input")
        self.pos += 1
        return tok

    def _expect_punct(self, value: str) -> Token:
        tok = self._next()
        if tok.kind != "punct" or tok.value != value:
            raise ParseError(
                f"expected {value!r} but found {tok.value!r} at line {tok.line}, col {tok.col}"
            )
        return tok

    def _expect_ident(self) -> Token:
        tok = self._next()
        if tok.kind != "ident":
            raise ParseError(
                f"expected identifier but found {tok.value!r} at line {tok.line}, col {tok.col}"
            )
        return tok

    def parse(self) -> Document:
        doc = Document()
        while self._peek() is not None:
            tok = self._peek()
            if tok.kind != "ident":
                raise ParseError(
                    f"expected type definition keyword at line {tok.line}, col {tok.col}"
                )
            if tok.value in ("record", "interface"):
                self._next()
                doc.records.append(self._parse_record())
            elif tok.value == "variant":
                self._next()
                doc.variants.append(self._parse_variant())
            else:
                raise ParseError(
                    f"unknown keyword {tok.value!r} at line {tok.line}, col {tok.col} "
                    f"(expected 'record', 'interface' or 'variant')"
                )
        return doc

    def _parse_record(self) -> Record:
        name = self._expect_ident().value
        self._expect_punct("{")
        rec = Record(name=name)
        seen: set[str] = set()
        while True:
            tok = self._peek()
            if tok is None:
                raise ParseError(f"unterminated record {name!r}")
            if tok.kind == "punct" and tok.value == "}":
                self._next()
                break
            rng = self._parse_optional_range()
            field_name = self._expect_ident().value
            if field_name in seen:
                raise ParseError(f"duplicate field {field_name!r} in record {name!r}")
            seen.add(field_name)
            self._expect_punct(":")
            type_ref = self._parse_type()
            rec.fields.append(Field(name=field_name, type=type_ref, range=rng))
            self._consume_optional_comma()
        return rec

    def _parse_variant(self) -> Variant:
        name = self._expect_ident().value
        self._expect_punct("{")
        var = Variant(name=name)
        seen: set[str] = set()
        while True:
            tok = self._peek()
            if tok is None:
                raise ParseError(f"unterminated variant {name!r}")
            if tok.kind == "punct" and tok.value == "}":
                self._next()
                break
            case_name = self._expect_ident().value
            if case_name in seen:
                raise ParseError(f"duplicate case {case_name!r} in variant {name!r}")
            seen.add(case_name)
            var.cases.append(case_name)
            self._consume_optional_comma()
        return var

    def _parse_type(self) -> TypeRef:
        tok = self._expect_ident()
        if tok.value in ("list", "option"):
            self._expect_punct("<")
            inner = self._parse_type()
            self._expect_punct(">")
            return TypeRef(name=tok.value, wrapper=tok.value, inner=inner)
        return TypeRef(name=tok.value)

    def _parse_optional_range(self) -> Optional[Range]:
        tok = self._peek()
        if tok is None or tok.kind != "punct" or tok.value != "@":
            return None
        self._next()  # '@'
        kw = self._expect_ident()
        if kw.value != "range":
            raise ParseError(
                f"unknown annotation @{kw.value} at line {kw.line}, col {kw.col} "
                f"(only @range is supported in Stage 1)"
            )
        self._expect_punct("(")
        lo = float(self._expect_number().value)
        self._expect_punct(",")
        hi = float(self._expect_number().value)
        self._expect_punct(")")
        if lo > hi:
            raise ParseError(f"@range min {lo} exceeds max {hi}")
        return Range(min=lo, max=hi)

    def _expect_number(self) -> Token:
        tok = self._next()
        if tok.kind != "number":
            raise ParseError(
                f"expected number but found {tok.value!r} at line {tok.line}, col {tok.col}"
            )
        return tok

    def _consume_optional_comma(self) -> None:
        tok = self._peek()
        if tok is not None and tok.kind == "punct" and tok.value == ",":
            self._next()


def parse(src: str) -> Document:
    """Parse WIT-subset source into an AST :class:`Document`."""
    return _Parser(_tokenize(src)).parse()
