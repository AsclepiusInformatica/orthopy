import math
import sys

import numpy
import sympy


def _math_comb(n, k):
    if sys.version < "3.8":
        if k > n - k:
            k = n - k

        out = 1
        for i in range(k):
            out *= n - i
            out //= i + 1
        return out

    return math.comb(n, k)


def full_like(x, val):
    if isinstance(x, numpy.ndarray):
        return numpy.full_like(x, val)

    # assume x is just a float or int or sympy.Poly
    return x * 0 + val


class Eval1D:
    def __init__(self, x, rc):
        self.rc = rc
        self.x = x
        self.k = 0
        self.last = [None, None]

    def __iter__(self):
        return self

    def __next__(self):
        if self.k == 0:
            out = full_like(self.x, self.rc.p0)
        else:
            a, b, c = self.rc[self.k - 1]
            out = self.last[0] * (self.x * a - b)
            if self.k > 1:
                out -= self.last[1] * c

        self.last[1] = self.last[0]
        self.last[0] = out
        self.k += 1
        return out


class ProductEval:
    """Evaluates the entire tree of orthogonal polynomials for an n-dimensional product
    domain.

    The computation is organized such that tree returns a list of arrays, L={0, ...,
    dim}, where each level corresponds to the polynomial degree L. Further, each level
    is organized like a discrete (dim-1)-dimensional simplex. Let's demonstrate this for
    3D:

    L = 1:
                   (0, 0, 0)

    L = 2:
                   (1, 0, 0)
              (0, 1, 0) (0, 0, 1)

    L = 3:
                   (2, 0, 0)
              (1, 1, 0) (1, 0, 1)
         (0, 2, 0) (0, 1, 1) (0, 0, 2)

    L = 4:
                   (3, 0, 0)
              (2, 1, 0) (2, 0, 1)
         (1, 2, 0) (1, 1, 1) (1, 0, 2)
    (0, 3, 0) (0, 2, 1) (0, 1, 2) (0, 0, 3)

    The main insight here that makes computation for n dimensions easy is that the next
    level is composed by:

       * Taking the whole previous level and adding +1 to the first entry.
       * Taking the last row of the previous level and adding +1 to the second entry.
       * Taking the last entry of the last row of the previous and adding +1 to the
         third entry.

    In the same manner this can be repeated for `dim` dimensions.
    """

    def __init__(self, rc, X, symbolic):
        self.rc = rc

        self.a = []
        self.b = []
        self.c = []
        X = numpy.asarray(X)
        self.dim = X.shape[0]
        self.p0n = rc.p0 ** self.dim
        self.k = 0
        self.X = X
        self.last_values = [None, None]
        self.last_degrees = None

    def __iter__(self):
        return self

    def __next__(self):
        print()
        print()
        print("start")
        a = self.a
        b = self.b
        c = self.c

        X = self.X
        L = self.k
        dim = X.shape[0]

        if L == 0:
            values = numpy.array([X[0] * 0 + self.p0n])
            degrees = numpy.array([numpy.zeros(dim, dtype=int)])
        else:
            aa, bb, cc = self.rc[L - 1]
            a.append(aa)
            b.append(bb)
            c.append(cc)

            values = []
            degrees = []
            mask = numpy.ones(len(self.last_degrees), dtype=bool)
            for i in range(dim - 1):
                m1 = _math_comb(L + dim - i - 2, dim - i - 1)
                last0 = self.last_values[0][-m1:]
                if L > 1:
                    m2 = _math_comb(L + dim - i - 3, dim - i - 1)
                    last1 = self.last_values[1][-m2:]
                r = 0
                for k in range(L):
                    m = _math_comb(k + dim - i - 2, dim - i - 2)
                    val = last0[r : r + m] * (a[L - k - 1] * X[i] - b[L - k - 1])
                    if L - k > 1:
                        val -= last1[r : r + m] * c[L - k - 1]
                    r += m
                    values.append(val)

                deg = self.last_degrees[mask]
                deg[:, i] += 1
                degrees.append(deg)
                # mask is True for all entries where the first k degrees are 0
                mask &= (self.last_degrees[:, i] == 0)

            # treat the last one separately
            val = self.last_values[0][-1] * (a[L - 1] * X[-1] - b[L - 1])
            if L > 1:
                val -= self.last_values[1][-1] * c[L - 1]
            values.append([val])
            deg = self.last_degrees[-1]
            deg[-1] += 1
            degrees.append([deg])

            values = numpy.concatenate(values)
            degrees = numpy.concatenate(degrees)

        self.last_values[1] = self.last_values[0]
        self.last_values[0] = values

        self.last_degrees = degrees
        self.k += 1

        print(values)
        print(degrees)
        print("end")
        # assert len(values) == len(degrees)
        return values, degrees


class Eval135:
    """Evaluates a 1-3-5-tree as seen with associated Legendre polynomials and spherical
    harmonics.

    There are many recurrence relations that can be used to construct the associated
    Legendre polynomials. However, only few are numerically stable. Many implementations
    (including this one) use the classical Legendre recurrence relation with increasing
    L.

    The return value is a list of arrays, where `values[k]` hosts the `2*k+1` values of
    the `k`th level of the tree

                              (0, 0)
                    (-1, 1)   (0, 1)   (1, 1)
          (-2, 2)   (-1, 2)   (0, 2)   (1, 2)   (2, 2)
            ...       ...       ...     ...       ...
    """

    def __init__(self, rc, x, xi=None, symbolic=False):
        self.rc = rc

        self.k = 0
        self.x = x
        # xi[0] == sqrt(1 - x**2) / exp(i*phi)
        # xi[1] == sqrt(1 - x**2) * exp(i*phi)
        if xi is None:
            sqrt = numpy.vectorize(sympy.sqrt) if symbolic else numpy.sqrt
            # Such functions aren't always polynomials, see, e.g.,
            # <https://en.wikipedia.org/wiki/Associated_Legendre_polynomials>:
            #
            # > In general, when l and m are integers, the regular solutions are
            # > sometimes called "associated Legendre polynomials", even though they are
            # > not polynomials when m is odd.
            a = sqrt(1 - x ** 2)
            self.xi = [a, a]
        else:
            self.xi = xi

        self.last = [None, None]

    def __iter__(self):
        return self

    def __next__(self):
        if self.k == 0:
            out = numpy.array([full_like(self.x, self.rc.p0)])
        else:
            z0, z1, c0, c1 = self.rc[self.k]
            out = numpy.concatenate(
                [
                    [self.last[0][0] * (self.xi[0] * z0)],
                    self.last[0] * numpy.multiply.outer(c0, self.x),
                    [self.last[0][-1] * (self.xi[1] * z1)],
                ]
            )

            if self.k > 1:
                out[2:-2] -= (self.last[1].T * c1).T

        self.last[1] = self.last[0]
        self.last[0] = out
        self.k += 1
        return out
