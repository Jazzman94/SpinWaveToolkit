"""
Core (private) file for the `SingleLayerNumeric` class.
"""

import numpy as np
from numpy import linalg
from SpinWaveToolkit.helpers import *

__all__ = ["SingleLayerNumeric"]


class SingleLayerNumeric:
    """Compute spin wave characteristic in dependance to k-vector
    (wavenumber) such as frequency, group velocity, lifetime and
    propagation length for up to three lowest-order modes.

    The dispersion model uses the approach of Tacchi et al., see:
    https://doi.org/10.1103/PhysRevB.100.104406

    Most parameters can be specified as vectors (1d numpy arrays)
    of the same shape. This functionality is not guaranteed.

    Parameters
    ----------
    Bext : float
        (T) external magnetic field.
    material : Material
        instance of `Material` describing the magnetic layer material.
        Its properties are saved as attributes, but this object is not.
    d : float
        (m) layer thickness (in z direction)
    kxi : float or ndarray, default np.linspace(1e-12, 25e6, 200)
        (rad/m) k-vector (wavenumber), usually a vector.
    theta : float, default np.pi/2
        (rad) out of plane angle static M, pi/2 is totally
        in-plane magnetization.
    phi : float or ndarray, default np.pi/2
        (rad) in-plane angle of kxi from M, pi/2 is DE geometry.
    weff : float, optional
        (m) effective width of the waveguide (not used for zeroth
        order width modes).
    boundary_cond : {1, 2, 3, 4}, default 1
        boundary conditions (BCs), 1 is totally unpinned and 2 is
        totally pinned BC, 3 is a long wave limit, 4 is partially
        pinned BC.
        ### The only working BCs are 1 right now, some functions
            implement 2 and 4, but it is not complete!
    dp : float, optional
        pinning parameter for 4 BC, ranges from 0 to inf,
        0 means totally unpinned.
    KuOOP : float, optional
        (J/m^3) OOP anisotropy strength used in the Tacchi model.
        ### Should this be calculated from the surface anisotropy
            strength as `KuOOP = 2*Ks/d + OOP_comp_of_bulk_anis`?,
            where `d` is film thickness and `Ks` is the surface
            anisotropy strength (same as material.Ku)

    Attributes (same as Parameters, plus these)
    -------------------------------------------
    Ms : float
        (A/m) saturation magnetization.
    gamma : float
        (rad*Hz/T) gyromagnetic ratio (positive convention).
    Aex : float
        (J/m) exchange stiffness constant.
    alpha : float
        () Gilbert damping.
    mu0dH0 : float
        (T) inhomogeneous broadening.
    w0 : float
        (rad*Hz) parameter in Slavin-Kalinikos equation.
        `w0 = MU0*gamma*Hext`
    wM : float
        (rad*Hz) parameter in Slavin-Kalinikos equation.
        `wM = MU0*gamma*Ms`
    A : float
        (m^2) parameter in Slavin-Kalinikos equation.
        `A = Aex*2/(Ms**2*MU0)`
    wU : float
        (rad*Hz) circular frequency of OOP anisotropy field,
        used in the Tacchi model.

    Methods
    -------
    GetDisperison
    GetGroupVelocity
    GetLifetime
    GetDecLen
    GetDensityOfStates
    GetExchangeLen

    Private methods
    ---------------
    __CnncTacchi
    __pnncTacchi
    __qnncTacchi
    __OmegankTacchi
    __ankTacchi
    __bTacchi
    __PnncTacchi
    __QnncTacchi

    Code example
    ------------
    Example of calculation of the dispersion relation `f(k_xi)`, and
    other important quantities, for the lowest-order mode in a 30 nm
    thick NiFe (Permalloy) layer.
    .. code-block:: python
        kxi = np.linspace(1e-6, 150e6, 150)

        PyChar = SingleLayerNumeric(Bext=20e-3, kxi=kxi, theta=np.pi/2,
                                    phi=np.pi/2, d=30e-9, weff=2e-6,
                                    boundary_cond=2, material=SWT.NiFe)
        DispPy = PyChar.GetDispersion()[0][0]*1e-9/(2*np.pi)  # GHz
        vgPy = PyChar.GetGroupVelocity()*1e-3  # km/s
        lifetimePy = PyChar.GetLifetime()*1e9  # ns
        decLen = PyChar.GetDecLen()*1e6  # um

    See also
    --------
    SingleLayer, DoubleLayerNumeric, Material

    """

    def __init__(
        self,
        Bext,
        material,
        d,
        kxi=np.linspace(1e-12, 25e6, 200),
        theta=np.pi / 2,
        phi=np.pi / 2,
        weff=3e-6,
        boundary_cond=1,
        dp=0,
        KuOOP=0,
    ):
        self._Bext = Bext
        self._Ms = material.Ms
        self._gamma = material.gamma
        self._Aex = material.Aex
        self._KuOOP = KuOOP
        self.kxi = np.array(kxi)
        self.theta = theta
        self.phi = phi
        self.d = d
        self.weff = weff
        self.boundary_cond = boundary_cond
        self.dp = dp
        self.alpha = material.alpha
        self.mu0dH0 = material.mu0dH0
        # Compute Slavin-Kalinikos parameters wM, w0, A
        self.wM = self.Ms * self.gamma * MU0
        self.w0 = self.gamma * Bext
        self.wU = self.gamma * 2 * self.KuOOP / self.Ms  # only for Tacchi
        self.A = self.Aex * 2 / (self.Ms**2 * MU0)

    @property
    def Bext(self):
        """external field value (T)"""
        return self._Bext

    @Bext.setter
    def Bext(self, val):
        self._Bext = val
        self.w0 = self.gamma * val

    @property
    def Ms(self):
        """saturation magnetization (A/m)"""
        return self._Ms

    @Ms.setter
    def Ms(self, val):
        self._Ms = val
        self.wM = val * self.gamma * MU0
        self.A = self.Aex * 2 / (val**2 * MU0)
        self.wU = self.gamma * 2 * self.KuOOP / val

    @property
    def gamma(self):
        """gyromagnetic ratio (rad*Hz/T)"""
        return self._gamma

    @gamma.setter
    def gamma(self, val):
        self._gamma = val
        self.wM = self.Ms * val * MU0
        self.w0 = val * self.Bext
        self.wU = val * 2 * self.KuOOP / self.Ms

    @property
    def Aex(self):
        """Exchange stiffness constant (J/m)."""
        return self._Aex

    @Aex.setter
    def Aex(self, val):
        self._Aex = val
        self.A = val * 2 / (self.Ms**2 * MU0)

    @property
    def KuOOP(self):
        """OOP uniaxial anisotropy constant (J/m^3)."""
        return self._KuOOP

    @KuOOP.setter
    def KuOOP(self, val):
        self._KuOOP = val
        self.wU = self.gamma * 2 * val / self.Ms

    def __CnncTacchi(self, n, nc, k, phi):
        """Calculate the C_{n,nc}."""
        return -self.wM / 2 * (1 - np.sin(phi) ** 2) * self.__PnncTacchi(n, nc, k)

    def __pnncTacchi(self, n, nc, k, phi):
        """Calculate the p_{n,nc}."""
        return -self.wM / 2 * (1 + np.sin(phi) ** 2) * self.__PnncTacchi(n, nc, k)

    def __qnncTacchi(self, n, nc, k, phi):
        """Calculate the q_{n,nc}."""
        return -self.wM / 2 * np.sin(phi) * self.__QnncTacchi(n, nc, k)

    def __OmegankTacchi(self, n, k):
        """Calculate the w_{n,k}."""
        return self.w0 + self.wM * self.A * (k**2 + (n * np.pi / self.d) ** 2)

    def __ankTacchi(self, n, k):
        """Calculate the a_{n,k}."""
        return self.__OmegankTacchi(n, k) + self.wM / 2 - self.wU / 2

    def __bTacchi(self):
        """Calculate the b."""
        return self.wM / 2 - self.wU / 2

    def __PnncTacchi(self, n, nc, kxi):
        """Gives dimensionless propagation vector.
        The boundary condition is chosen based on the object property.

        Parameters
        ----------
        n : int
            Quantization number.
        nc : int
            Second quantization number, used for hybridization.
        kxi : float
            (rad/m) wavenumber.
        """
        kappa = n * np.pi / self.d
        kappac = nc * np.pi / self.d
        k = np.sqrt(np.power(kxi, 2) + kappa**2)
        kc = np.sqrt(np.power(kxi, 2) + kappac**2)
        # Totally unpinned boundary condition
        if self.boundary_cond == 1:
            Fn = 2 / (kxi * self.d) * (1 - (-1) ** n * np.exp(-kxi * self.d))
            if n == 0 and nc == 0:
                Pnn = (kxi**2) / (kc**2) - (kxi**4) / (
                    k**2 * kc**2
                ) * 1 / 2 * ((1 + (-1) ** (n + nc)) / 2) * Fn
            elif n == 0 and nc != 0 or nc == 0 and n != 0:
                Pnn = (
                    -(kxi**4)
                    / (k**2 * kc**2)
                    * 1
                    / np.sqrt(2)
                    * ((1 + (-1) ** (n + nc)) / 2)
                    * Fn
                )
            elif n == nc:
                Pnn = (kxi**2) / (kc**2) - (kxi**4) / (k**2 * kc**2) * (
                    (1 + (-1) ** (n + nc)) / 2
                ) * Fn
            else:
                Pnn = -(kxi**4) / (k**2 * kc**2) * ((1 + (-1) ** (n + nc)) / 2) * Fn
        # Totally pinned boundary condition
        elif self.boundary_cond == 2:
            if n == nc:
                Pnn = (kxi**2) / (kc**2) + (kxi**2) / (k**2) * (
                    kappa * kappac
                ) / (kc**2) * (1 + (-1) ** (n + nc) / 2) * 2 / (kxi * self.d) * (
                    1 - (-1) ** n * np.exp(-kxi * self.d)
                )
            else:
                Pnn = (
                    (kxi**2)
                    / (k**2)
                    * (kappa * kappac)
                    / (kc**2)
                    * (1 + (-1) ** (n + nc) / 2)
                    * 2
                    / (kxi * self.d)
                    * (1 - (-1) ** n * np.exp(-kxi * self.d))
                )
        else:
            raise ValueError(
                "Sorry, there is no boundary condition with this number for"
                + "the Tacchi numeric solution."
            )

        return Pnn

    def __QnncTacchi(self, n, nc, kxi):
        """Gives dimensionless propagation vector Q.
        This vector accounts for interaction between odd and even
        spin wave modes.

        Parameters
        ----------
        n : int
            Quantization number.
        nc : int
            Second quantization number, used for hybridization.
        kxi : float
            (rad/m) wavenumber.
        """
        # ### The totally pinned BC should be added
        kappa = n * np.pi / self.d
        kappac = nc * np.pi / self.d
        if kappa == 0:
            kappa = 1
        if kappac == 0:
            kappac = 1
        k = np.sqrt(np.power(kxi, 2) + kappa**2)
        kc = np.sqrt(np.power(kxi, 2) + kappac**2)
        # Totally unpinned boundary condition
        if self.boundary_cond == 1:
            Fn = 2 / (kxi * self.d) * (1 - (-1) ** n * np.exp(-kxi * self.d))
            Qnn = (
                kxi**2
                / kc**2
                * (
                    kappac**2 / (kappac**2 - kappa**2) * 2 / (kxi * self.d)
                    - kxi**2 / (2 * k**2) * Fn
                )
                * ((1 - (-1) ** (n + nc)) / 2)
            )
        elif self.boundary_cond == 4:
            dp = self.dp
            kappa = self.GetPartiallyPinnedKappa(n)
            kappac = self.GetPartiallyPinnedKappa(nc)
            if kappa == 0:
                kappa = 1
            if kappac == 0:
                kappac = 1
            An = np.sqrt(
                2
                * (
                    (kappa**2 + dp**2) / kappa**2
                    + np.sin(kappa * self.d)
                    / (kappa * self.d)
                    * (
                        (kappa**2 - dp**2) / kappa**2 * np.cos(kappa * self.d)
                        + 2 * dp / kappa * np.sin(kappa * self.d)
                    )
                )
                ** -1
            )
            Anc = np.sqrt(
                2
                * (
                    (kappac**2 + dp**2) / kappac**2
                    + np.sin(kappac * self.d)
                    / (kappac * self.d)
                    * (
                        (kappac**2 - dp**2) / kappac**2 * np.cos(kappac * self.d)
                        + 2 * dp / kappac * np.sin(kappac * self.d)
                    )
                )
                ** -1
            )
            Qnn = (
                kxi
                * An
                * Anc
                / (2 * self.d * k**2 * kc**2)
                * (
                    (kxi**2 - dp**2)
                    * np.exp(-kxi * self.d)
                    * (np.cos(kappa * self.d) - np.cos(kappac * self.d))
                    + (kxi - dp)
                    * np.exp(-kxi * self.d)
                    * (
                        (dp * kxi - kappa**2) * np.sin(kappa * self.d) / kappa
                        - (dp * kxi - kappac**2) * np.sin(kappac * self.d) / kappac
                    )
                    + (kxi - dp)
                    * (
                        (dp * kxi - kappac**2)
                        * np.cos(kappa * self.d)
                        * np.sin(kappac * self.d)
                        / kappac
                        - (dp * kxi - kappa**2)
                        * np.cos(kappac * self.d)
                        * np.sin(kappa * self.d)
                        / kappa
                    )
                    + (
                        1
                        - np.cos(kappac * self.d)
                        * np.cos(kappa * self.d)
                        * 2
                        * (
                            kxi**2 * dp**2
                            + kappa**2 * kappac**2
                            + (kappac**2 + kappa**2) * (kxi**2 + dp**2)
                        )
                        / (kappac**2 - kappa**2)
                        - np.sin(kappa * self.d)
                        * np.sin(kappac**2 * self.d)
                        / (kappa * kappac * (kappac**2 - kappa**2))
                        * (
                            dp * kxi * (kappa**4 + kappac**4)
                            + (dp**2 * kxi**2 - kappa**2 * kappac**2)
                            * (kappa**2 + kappac**2)
                            - 2 * kappa**2 * kappac**2 * (dp**2 + kxi**2 - dp * kxi)
                        )
                    )
                )
            )
        else:
            raise ValueError(
                "Sorry, there is no boundary condition with this number for "
                + "the Tacchi numeric solution."
            )
        return Qnn

    def GetPartiallyPinnedKappa(self, n):
        """Gives kappa from the transverse equation (in rad/m).

        Parameters
        ----------
        n : int
            Quantization number.
        """

        def trans_eq(kappa, d, dp):
            e = (kappa**2 - dp**2) * np.tan(kappa * d) - kappa * dp * 2
            return e

        kappa0 = roots(
            trans_eq,
            n * np.pi / self.d,
            (n + 1) * np.pi / self.d,
            np.pi / self.d * 4e-4,
            # try decreasing dx if an error occurs
            np.pi / self.d * 1e-9,
            args=(self.d, self.dp),
        )
        for i in range(n + 1):
            # omit singularities at tan(kappa*d) when kappa*d = (n+0.5)pi
            kappa0[np.isclose(kappa0, np.pi / self.d * (i + 0.5))] = np.nan
            kappa0[kappa0 == 0.0] = np.nan  # omit 0 (probably only first is 0)
        kappa0 = kappa0[~np.isnan(kappa0)]  # remove NaNs
        return kappa0[0]

    def GetDispersion(self):
        """Gives frequencies for defined k (Dispersion relation).
        Based on the model in:
        https://doi.org/10.1103/PhysRevB.100.104406

        The model formulates a system matrix and then numerically solves
        its eigenvalues and eigenvectors. The eigenvalues represent the
        dispersion relation (as the matrix is 6x6 it has 6 eigenvalues).
        The eigen values represent 3 lowest spin-wave modes
        (3 with negative and positive frequency).  The eigenvectors
        represent the amplitude of the individual spin-wave modes and
        can be used to calculate spin-wave profile (see example
        NumericCalculationofDispersionModeProfiles.py).
        ### Update correct example.

        The returned modes are sorted from low to high frequencies,
        omitting the negative-frequency modes.

        Returns
        -------
        wV : ndarray
            (rad*Hz) frequencies of the 3 lowest spin-wave modes.
            Has a shape of `(3, N)`, where `N = kxi.shape[0]`.
        vV : ndarray
            Mode profiles of corresponding eigenfrequencies,
            given as Fourier coefficients for IP and OOP profiles.
            Has a shape of `(6, 3, N)`, where `N = kxi.shape[0]`.
        """
        ks = np.sqrt(np.power(self.kxi, 2))  # can this be just np.abs(kxi)?
        phi = self.phi
        wV = np.zeros((3, np.size(ks, 0)))
        vV = np.zeros((6, 3, np.size(ks, 0)))
        for idx, k in enumerate(ks):
            Ck = np.array(
                [
                    [
                        -(self.__ankTacchi(0, k) + self.__CnncTacchi(0, 0, k, phi)),
                        -(self.__bTacchi() + self.__pnncTacchi(0, 0, k, phi)),
                        0,
                        -self.__qnncTacchi(1, 0, k, phi),
                        -self.__CnncTacchi(2, 0, k, phi),
                        -self.__pnncTacchi(2, 0, k, phi),
                    ],
                    [
                        (self.__bTacchi() + self.__pnncTacchi(0, 0, k, phi)),
                        (self.__ankTacchi(0, k) + self.__CnncTacchi(0, 0, k, phi)),
                        -self.__qnncTacchi(1, 0, k, phi),
                        0,
                        self.__pnncTacchi(2, 0, k, phi),
                        self.__CnncTacchi(2, 0, k, phi),
                    ],
                    [
                        0,
                        -self.__qnncTacchi(0, 1, k, phi),
                        -(self.__ankTacchi(1, k) + self.__CnncTacchi(1, 1, k, phi)),
                        -(self.__bTacchi() + self.__pnncTacchi(1, 1, k, phi)),
                        0,
                        -self.__qnncTacchi(2, 1, k, phi),
                    ],
                    [
                        -self.__qnncTacchi(0, 1, k, phi),
                        0,
                        (self.__bTacchi() + self.__pnncTacchi(1, 1, k, phi)),
                        (self.__ankTacchi(1, k) + self.__CnncTacchi(1, 1, k, phi)),
                        -self.__qnncTacchi(2, 1, k, phi),
                        0,
                    ],
                    [
                        -self.__CnncTacchi(0, 2, k, phi),
                        -self.__pnncTacchi(0, 2, k, phi),
                        0,
                        -self.__qnncTacchi(1, 2, k, phi),
                        -(self.__ankTacchi(2, k) + self.__CnncTacchi(2, 2, k, phi)),
                        -(self.__bTacchi() + self.__pnncTacchi(2, 2, k, phi)),
                    ],
                    [
                        self.__pnncTacchi(0, 2, k, phi),
                        self.__CnncTacchi(0, 2, k, phi),
                        -self.__qnncTacchi(1, 2, k, phi),
                        0,
                        (self.__bTacchi() + self.__pnncTacchi(2, 2, k, phi)),
                        (self.__ankTacchi(2, k) + self.__CnncTacchi(2, 2, k, phi)),
                    ],
                ],
                dtype=float,
            )
            w, v = linalg.eig(Ck)
            indi = np.argsort(w)[3:]  # sort low-to-high and crop to positive
            wV[:, idx] = w[indi]  # eigenvalues (dispersion)
            vV[:, :, idx] = v[:, indi]  # eigenvectors (mode profiles)
        return wV, vV

    def GetGroupVelocity(self, n=0):
        """Gives (tangential) group velocities for defined k.
        The group velocity is computed as vg = dw/dk.
        The result is given in m/s.

        .. warning::
            Works only when `kxi.shape[0] >= 2`.

        Parameters
        ----------
        n : {-1, 0, 1, 2}, default 0
            Quantization number.  If -1, data
            for all (positive) calculated modes are returned.

        Returns
        -------
        vg : ndarray
            (m/s) tangential group velocity.
        """
        w, _ = self.GetDispersion()
        if n == -1:
            vg = np.zeros(w.shape)
            for i in range(w.shape[0]):
                vg[i] = np.gradient(w[i]) / np.gradient(self.kxi)
        else:
            vg = np.gradient(w[n]) / np.gradient(self.kxi)
        return vg

    def GetLifetime(self, n=0):
        """Gives lifetimes for defined k.
        lifetime is computed as tau = (alpha*w*dw/dw0)^-1.
        The output is in s.

        Parameters
        ----------
        n : {-1, 0, 1, 2}, default 0
            Quantization number.  If -1, data
            for all (positive) calculated modes are returned.

        Returns
        -------
        lifetime : ndarray
            (s) lifetime.
        """
        w0_ori = self.w0
        step = 1e-5
        self.w0 = w0_ori * (1 - step)
        dw_lo, _ = self.GetDispersion()
        self.w0 = w0_ori * (1 + step)
        dw_hi, _ = self.GetDispersion()
        self.w0 = w0_ori
        w_mid, _ = self.GetDispersion()
        lifetime = (
            (self.alpha * w_mid + self.gamma * self.mu0dH0)
            * (dw_hi - dw_lo)
            / (w0_ori * 2 * step)
        ) ** -1
        if n != -1:
            return lifetime[n]
        return lifetime

    def GetDecLen(self, n=0):
        """Give decay lengths for defined k.
        Decay length is computed as lambda = v_g*tau.
        Output is given in m.

        .. warning::
            Works only when `kxi.shape[0] >= 2`.

        Parameters
        ----------
        n : {-1, 0, 1, 2}, default 0
            Quantization number.  If -1, data
            for all (positive) calculated modes are returned.

        Returns
        -------
        declen : ndarray
            (m) decay length.
        """
        return self.GetLifetime(n=n) * self.GetGroupVelocity(n=n)

    def GetDensityOfStates(self, n=0):
        """Give density of states for given mode.
        Density of states is computed as DoS = 1/v_g.
        Output is density of states in 1D for given dispersion
        characteristics.

        .. warning::
            Works only when `kxi.shape[0] >= 2`.

        Parameters
        ----------
        n : {-1, 0, 1, 2}, default 0
            Quantization number.  If -1, data
            for all (positive) calculated modes are returned.

        Returns
        -------
        dos : ndarray
            (s/m) value proportional to density of states.
        """
        return 1 / self.GetGroupVelocity(n=n)

    def GetExchangeLen(self):
        """Calculate exchange length in meters from the parameter `A`."""
        return np.sqrt(self.A)
