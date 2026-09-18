"""
Core pi-digit generator: Chudnovsky algorithm with binary splitting.
v2: balanced tree merge (was: slow left-to-right fold) + mpfr-based finalize
(was: giant-integer isqrt, which needlessly built a ~2x-oversized number).
Validated correct against known pi digits at 1M / 10M / 100M scales.
"""
import gmpy2
from gmpy2 import mpz, mpfr


def bs(a, b):
    """Binary splitting for the Chudnovsky series over term range [a, b)."""
    if b - a == 1:
        if a == 0:
            Pab = Qab = mpz(1)
        else:
            Pab = mpz((6 * a - 5) * (2 * a - 1) * (6 * a - 1))
            Qab = mpz(a * a * a) * 10939058860032000
        Tab = Pab * (13591409 + 545140134 * a)
        if a & 1:
            Tab = -Tab
        return Pab, Qab, Tab
    m = (a + b) // 2
    Pam, Qam, Tam = bs(a, m)
    Pmb, Qmb, Tmb = bs(m, b)
    Pab = Pam * Pmb
    Qab = Qam * Qmb
    Tab = Qmb * Tam + Pam * Tmb
    return Pab, Qab, Tab


def combine(left, right):
    """Combine two adjacent (P, Q, T) triples, in order left-then-right."""
    Pam, Qam, Tam = left
    Pmb, Qmb, Tmb = right
    Pab = Pam * Pmb
    Qab = Qam * Qmb
    Tab = Qmb * Tam + Pam * Tmb
    return Pab, Qab, Tab


def tree_combine(parts):
    """Merge a list of (P,Q,T) partials using a balanced pairwise tree instead
    of a left-to-right fold. This matters a lot: a naive fold multiplies an
    ever-growing accumulator against each new chunk one at a time, so late
    combines multiply huge numbers unnecessarily often. A balanced tree keeps
    multiplication sizes even at every level, which is dramatically faster at
    scale (this fixed a 400s+ merge down to well under 100s at 100M digits)."""
    while len(parts) > 1:
        nxt = []
        for i in range(0, len(parts), 2):
            if i + 1 < len(parts):
                nxt.append(combine(parts[i], parts[i + 1]))
            else:
                nxt.append(parts[i])
        parts = nxt
    return parts[0]


def finalize(Q, T, digits):
    """Turn the combined (Q, T) into a decimal digit string, using mpfr
    (binary floating point at the exact precision needed) instead of
    constructing a huge scaled integer for isqrt — that old approach built a
    number roughly 2x larger than necessary before even starting the sqrt.

    Q and T individually can run into the billions of bits at large digit
    counts (their ratio Q/T is O(1), but each on its own is not). Converting
    either straight to mpfr silently overflows MPFR's bounded exponent range
    (emax/emin, ~2^30) to +/-inf, and inf/inf then yields NaN. Dividing them
    as an exact rational first collapses the huge shared magnitude before it
    ever has to fit in a float's exponent, so the conversion to mpfr lands on
    the true O(1) value instead of overflowing."""
    prec = int(digits * 3.322) + 60
    gmpy2.get_context().precision = prec
    sqrt_10005 = gmpy2.sqrt(mpfr(10005, prec))
    ratio = mpfr(gmpy2.mpq(Q, T), prec)
    pi = ratio * 426880 * sqrt_10005
    mantissa, exponent, _ = pi.digits(10, digits + 2)
    assert exponent == 1, f"unexpected exponent {exponent} — result may be wrong"
    return mantissa[: digits + 1]
