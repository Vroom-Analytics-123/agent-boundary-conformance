#!/usr/bin/env python3
"""Pure-Python Ed25519 (RFC 8032), stdlib only.

Vendored for the FinePrint evidence-bundling pipeline so that bundle signing
needs no third-party dependency: the replication story stays "python3 and the
repo". The structure follows Daniel J. Bernstein's public-domain reference
implementation of Ed25519 (the well-known ~100-line form); it was re-derived
here rather than copied, and correctness is pinned by the RFC 8032 section
7.1 test vectors in tests/test_signing.py.

API:
    publickey(sk: bytes) -> bytes            # 32-byte secret seed -> 32-byte public key
    signature(m: bytes, sk: bytes, pk: bytes) -> bytes   # 64-byte signature
    checkvalid(sig: bytes, m: bytes, pk: bytes) -> bool

Security notes:
  - This is NOT constant-time; it is a signing/verifying utility for
    evidence bundles, not a high-throughput or side-channel-exposed service.
  - Keys are 32-byte seeds from os.urandom; the private key file is chmod
    600 and lives OUTSIDE all repos (see tools/signing.py).
"""

import hashlib

_b = 256
_q = (1 << 255) - 19
_l = (1 << 252) + 27742317777372353535851937790883648493


def _H(m: bytes) -> bytes:
    return hashlib.sha512(m).digest()


def _expmod(base: int, exp: int, mod: int) -> int:
    if exp == 0:
        return 1
    t = _expmod(base, exp // 2, mod) ** 2 % mod
    if exp & 1:
        t = t * base % mod
    return t


def _inv(x: int) -> int:
    return _expmod(x, _q - 2, _q)


_d = -121665 * _inv(121666) % _q
_I = _expmod(2, (_q - 1) // 4, _q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_d * y * y + 1) % _q
    x = _expmod(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    if x % 2 != 0:
        x = _q - x
    return x


_By = 4 * _inv(5) % _q
_Bx = _xrecover(_By)
_B = (_Bx % _q, _By % _q)


def _edwards(P, Q):
    # Addition law for the twisted Edwards curve a*x^2 + y^2 = 1 + d*x^2*y^2
    # with a = -1 (Hisil-Wong-Carter-Dawson affine form):
    #   x3 = (x1*y2 + x2*y1) / (1 + d*x1*x2*y1*y2)
    #   y3 = (y1*y2 - a*x1*x2) / (1 - d*x1*x2*y1*y2)
    #      = (y1*y2 + x1*x2) / (1 - d*x1*x2*y1*y2)   [a = -1]
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _d * x1 * x2 * y1 * y2) % _q
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _d * x1 * x2 * y1 * y2) % _q
    return (x3, y3)


def _scalarmult(P, e: int):
    if e == 0:
        return (0, 1)
    Q = _scalarmult(P, e // 2)
    Q = _edwards(Q, Q)
    if e & 1:
        Q = _edwards(Q, P)
    return Q


def _encodeint(y: int) -> bytes:
    return y.to_bytes(_b // 8, "little")


def _encodepoint(P) -> bytes:
    x, y = P
    return ((y | ((x & 1) << 255))).to_bytes(_b // 8, "little")


def _bit(h: bytes, i: int) -> int:
    return (h[i // 8] >> (i % 8)) & 1


def _decodeint(s: bytes) -> int:
    return int.from_bytes(s, "little")


def _decodepoint(s: bytes):
    if len(s) != _b // 8:
        raise ValueError("bad encoded point length")
    y = _decodeint(s) & ((1 << 255) - 1)
    sign = _bit(s, _b - 1)
    x = _xrecover(y)
    if x & 1 != sign:
        x = _q - x
    P = (x, y)
    x, y = P
    if (-x * x + y * y - 1 - _d * x * x * y * y) % _q != 0:
        raise ValueError("point not on curve")
    return P


def _hint(m: bytes) -> int:
    return int.from_bytes(_H(m), "little")


def publickey(sk: bytes) -> bytes:
    """Derive the 32-byte Ed25519 public key from a 32-byte secret seed."""
    if len(sk) != 32:
        raise ValueError("secret seed must be 32 bytes")
    h = _H(sk)
    a = 2 ** (_b - 2) + sum(2 ** i * _bit(h, i) for i in range(3, _b - 2))
    return _encodepoint(_scalarmult(_B, a))


def signature(m: bytes, sk: bytes, pk: bytes) -> bytes:
    """Sign message m with the 32-byte secret seed sk (pk = publickey(sk))."""
    if len(sk) != 32:
        raise ValueError("secret seed must be 32 bytes")
    if len(pk) != 32:
        raise ValueError("public key must be 32 bytes")
    h = _H(sk)
    a = 2 ** (_b - 2) + sum(2 ** i * _bit(h, i) for i in range(3, _b - 2))
    r = _hint(h[_b // 8:_b // 4] + m)
    R = _scalarmult(_B, r)
    S = (r + _hint(_encodepoint(R) + pk + m) * a) % _l
    return _encodepoint(R) + _encodeint(S)


def checkvalid(sig: bytes, m: bytes, pk: bytes) -> bool:
    """Verify an Ed25519 signature. Returns True/False, never raises on bad input."""
    if len(sig) != _b // 4 or len(pk) != _b // 8:
        return False
    try:
        R = _decodepoint(sig[:_b // 8])
        A = _decodepoint(pk)
        S = _decodeint(sig[_b // 8:_b // 4])
        h = _hint(_encodepoint(R) + pk + m)
    except (ValueError, IndexError):
        return False
    return _scalarmult(_B, S) == _edwards(R, _scalarmult(A, h))
