import numpy
import sympy


def tree(X, n, symbolic=False):
    """Evaluates the entire tree of orthogonal polynomials on the unit disk.

    The return value is a list of arrays, where `out[k]` hosts the `2*k+1`
    values of the `k`th level of the tree

        (0, 0)
        (0, 1)   (1, 1)
        (0, 2)   (1, 2)   (2, 2)
          ...      ...      ...

    See

    Yuan Xu
    Orthogonal polynomials of several variables,
    Jan. 2017,
    <https://arxiv.org/abs/1701.02709>

    equation (3.4) for a formulation in terms of Gegenbauer polynomials C. The
    recurrence relation can be worked out from there.
    """
    frac = sympy.Rational if symbolic else lambda x, y: x / y
    sqrt = sympy.sqrt if symbolic else numpy.sqrt
    pi = sympy.pi if symbolic else numpy.pi

    mu = frac(1, 2)

    p0 = 1 / sqrt(pi)

    def alpha(n):
        return numpy.array(
            [
                2
                * sqrt(
                    frac(
                        (n + mu + frac(1, 2)) * (n + mu - frac(1, 2)),
                        (n - k) * (n + k + 2 * mu),
                    )
                )
                for k in range(n)
            ]
        )

    def beta(n):
        return 2 * sqrt(
            frac((n + mu - 1) * (n + mu + frac(1, 2)), (n + 2 * mu - 1) * n)
        )

    def gamma(n):
        return numpy.array(
            [
                sqrt(
                    frac(
                        (n - 1 - k) * (n + mu + frac(1, 2)) * (n + k + 2 * mu - 1),
                        (n - k) * (n + mu - frac(3, 2)) * (n + k + 2 * mu),
                    )
                )
                for k in range(n - 1)
            ]
        )

    def delta(n):
        return sqrt(
            frac(
                (n - 1)
                * (n + 2 * mu - 2)
                * (n + mu - frac(1, 2))
                * (n + mu + frac(1, 2)),
                n * (n + 2 * mu - 1) * (n + mu - 1) * (n + mu - 2),
            )
        )

    out = [numpy.array([0 * X[0] + p0])]

    one_min_x2 = 1 - X[0] ** 2

    for L in range(1, n + 1):
        nxt = numpy.concatenate(
            [
                out[-1] * numpy.multiply.outer(alpha(L), X[0]),
                [out[-1][L - 1] * beta(L) * X[1]],
            ]
        )

        if L > 1:
            nxt[: L - 1] -= (out[-2].T * gamma(L)).T
            nxt[-1] -= out[-2][-1] * delta(L) * one_min_x2

        out.append(nxt)

    return out
