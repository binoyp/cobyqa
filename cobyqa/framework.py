import warnings

import numpy as np
from scipy.optimize import lsq_linear

from .models import Models, Quadratic
from .subsolvers import cauchy_geometry, spider_geometry, normal_byrd_omojokun, tangential_byrd_omojokun, constrained_tangential_byrd_omojokun
from .subsolvers.optim import qr_tangential_byrd_omojokun
from .utils import get_arrays_tol


class TrustRegion:
    """
    Trust-region framework.
    """

    def __init__(self, pb, options):
        """
        Initialize the trust-region framework.

        Parameters
        ----------
        pb : Problem
            Problem to solve.
        options : dict
            Options of the solver.
        """
        # Initialize the models.
        self._pb = pb
        self._models = Models(self._pb, options)

        # Set the initial penalty parameter.
        self._penalty = self._get_low_penalty()
        if self._penalty == np.inf:
            self._penalty = 0.0

        # Set the index of the best interpolation point.
        self._best_index = 0
        self.set_best_index()

        # Set the initial Lagrange multipliers.
        self._lm_linear_ub = np.empty(self.m_linear_ub)
        self._lm_linear_eq = np.empty(self.m_linear_eq)
        self._lm_nonlinear_ub = np.empty(self.m_nonlinear_ub)
        self._lm_nonlinear_eq = np.empty(self.m_nonlinear_eq)
        self.set_multipliers()

        # Set the initial trust-region radius and the resolution.
        self._resolution = options['radius_init']
        self._radius = self.resolution

    @property
    def n(self):
        """
        Number of variables.

        Returns
        -------
        int
            Number of variables.
        """
        return self._pb.n

    @property
    def m_linear_ub(self):
        """
        Number of linear inequality constraints.

        Returns
        -------
        int
            Number of linear inequality constraints.
        """
        return self._pb.m_linear_ub

    @property
    def m_linear_eq(self):
        """
        Number of linear equality constraints.

        Returns
        -------
        int
            Number of linear equality constraints.
        """
        return self._pb.m_linear_eq

    @property
    def m_nonlinear_ub(self):
        """
        Number of nonlinear inequality constraints.

        Returns
        -------
        int
            Number of nonlinear inequality constraints.
        """
        return self._pb.m_nonlinear_ub

    @property
    def m_nonlinear_eq(self):
        """
        Number of nonlinear equality constraints.

        Returns
        -------
        int
            Number of nonlinear equality constraints.
        """
        return self._pb.m_nonlinear_eq

    @property
    def radius(self):
        """
        Trust-region radius.

        Returns
        -------
        float
            Trust-region radius.
        """
        return self._radius

    @radius.setter
    def radius(self, radius):
        """
        Set the trust-region radius.

        Parameters
        ----------
        radius : float
            New trust-region radius.
        """
        self._radius = radius
        if self.radius <= 1.4 * self.resolution:
            self._radius = self.resolution

    @property
    def resolution(self):
        """
        Resolution of the trust-region framework.

        The resolution is a lower bound on the trust-region radius.

        Returns
        -------
        float
            Resolution of the trust-region framework.
        """
        return self._resolution

    @resolution.setter
    def resolution(self, resolution):
        """
        Set the resolution of the trust-region framework.

        Parameters
        ----------
        resolution : float
            New resolution of the trust-region framework.
        """
        self._resolution = resolution

    @property
    def models(self):
        """
        Models of the objective function and constraints.

        Returns
        -------
        Models
            Models of the objective function and constraints.
        """
        return self._models

    @property
    def best_index(self):
        """
        Index of the best interpolation point.

        Returns
        -------
        int
            Index of the best interpolation point.
        """
        return self._best_index

    @property
    def x_best(self):
        """
        Best interpolation point.

        Its value is interpreted as relative to the origin, not the base point.

        Returns
        -------
        numpy.ndarray
            Best interpolation point.
        """
        return self.models.interpolation.point(self.best_index)

    @property
    def fun_best(self):
        """
        Value of the objective function at `x_best`.

        Returns
        -------
        float
            Value of the objective function at `x_best`.
        """
        return self.models.fun_val[self.best_index]

    @property
    def cub_best(self):
        """
        Values of the nonlinear inequality constraints at `x_best`.

        Returns
        -------
        numpy.ndarray, shape (m_nonlinear_ub,)
            Values of the nonlinear inequality constraints at `x_best`.
        """
        return self.models.cub_val[self.best_index, :]

    @property
    def ceq_best(self):
        """
        Values of the nonlinear equality constraints at `x_best`.

        Returns
        -------
        numpy.ndarray, shape (m_nonlinear_eq,)
            Values of the nonlinear equality constraints at `x_best`.
        """
        return self.models.ceq_val[self.best_index, :]

    def lag_model(self, x):
        """
        Evaluate the Lagrangian model at a given point.

        Parameters
        ----------
        x : numpy.ndarray, shape (n,)
            Point at which the Lagrangian model is evaluated.

        Returns
        -------
        float
            Value of the Lagrangian model at `x`.
        """
        return self.models.fun(x) + self._lm_linear_ub @ (self._pb.linear_ub.a @ x - self._pb.linear_ub.b) + + self._lm_linear_eq @ (self._pb.linear_eq.a @ x - self._pb.linear_eq.b) + self._lm_nonlinear_ub @ self.models.cub(x) + self._lm_nonlinear_eq @ self.models.ceq(x)

    def lag_model_grad(self, x):
        """
        Evaluate the gradient of the Lagrangian model at a given point.

        Parameters
        ----------
        x : numpy.ndarray, shape (n,)
            Point at which the gradient of the Lagrangian model is evaluated.

        Returns
        -------
        float
            Gradient of the Lagrangian model at `x`.
        """
        return self.models.fun_grad(x) + self._lm_linear_ub @ self._pb.linear_ub.a + self._lm_linear_eq @ self._pb.linear_eq.a + self._lm_nonlinear_ub @ self.models.cub_grad(x) + self._lm_nonlinear_eq @ self.models.ceq_grad(x)

    def lag_model_hess(self):
        """
        Evaluate the Hessian matrix of the Lagrangian model at a given point.

        Parameters
        ----------
        x : numpy.ndarray, shape (n,)
            Point at which the Hessian matrix of the Lagrangian model is
            evaluated.

        Returns
        -------
        float
            Hessian matrix of the Lagrangian model at `x`.
        """
        return self.models.fun_hess() + self._lm_nonlinear_ub @ self.models.cub_hess() + self._lm_nonlinear_eq @ self.models.ceq_hess()

    def lag_model_hess_prod(self, v):
        """
        Evaluate the right product of the Hessian matrix of the Lagrangian model
        with a given vector.

        Parameters
        ----------
        v : numpy.ndarray, shape (n,)
            Vector with which the Hessian matrix of the Lagrangian model is
            multiplied from the right.

        Returns
        -------
        float
            Right product of the Hessian matrix of the Lagrangian model with
            `v`.
        """
        return self.models.fun_hess_prod(v) + self._lm_nonlinear_ub @ self.models.cub_hess_prod(v) + self._lm_nonlinear_eq @ self.models.ceq_hess_prod(v)

    def lag_model_curv(self, v):
        """
        Evaluate the curvature of the Lagrangian model along a given direction.

        Parameters
        ----------
        v : numpy.ndarray, shape (n,)
            Direction along which the curvature of the Lagrangian model is
            evaluated.

        Returns
        -------
        float
            Curvature of the Lagrangian model along `v`.
        """
        return self.models.fun_curv(v) + self._lm_nonlinear_ub @ self.models.cub_curv(v) + self._lm_nonlinear_eq @ self.models.ceq_curv(v)

    def sqp_fun(self, step):
        """
        Evaluate the objective function of the SQP subproblem.

        Parameters
        ----------
        step : numpy.ndarray, shape (n,)
            Step along which the objective function of the SQP subproblem is
            evaluated.

        Returns
        -------
        float
            Value of the objective function of the SQP subproblem along `step`.
        """
        return step @ (self.models.fun_grad(self.x_best) + 0.5 * self.lag_model_hess_prod(step))

    def sqp_cub(self, step):
        """
        Evaluate the linearization of the nonlinear inequality constraints.

        Parameters
        ----------
        step : numpy.ndarray, shape (n,)
            Step along which the linearization of the nonlinear inequality
            constraints is evaluated.

        Returns
        -------
        numpy.ndarray, shape (m_nonlinear_ub,)
            Value of the linearization of the nonlinear inequality constraints
            along `step`.
        """
        return self.models.cub(self.x_best) + self.models.cub_grad(self.x_best) @ step

    def sqp_ceq(self, step):
        """
        Evaluate the linearization of the nonlinear equality constraints.

        Parameters
        ----------
        step : numpy.ndarray, shape (n,)
            Step along which the linearization of the nonlinear equality
            constraints is evaluated.

        Returns
        -------
        numpy.ndarray, shape (m_nonlinear_ub,)
            Value of the linearization of the nonlinear equality constraints
            along `step`.
        """
        return self.models.ceq(self.x_best) + self.models.ceq_grad(self.x_best) @ step

    def merit(self, x, fun_val=None, cub_val=None, ceq_val=None):
        """
        Evaluate the merit function at a given point.

        Parameters
        ----------
        x : numpy.ndarray, shape (n,)
            Point at which the merit function is evaluated.
        fun_val : float, optional
            Value of the objective function at `x`. If not provided, the
            objective function is evaluated at `x`.
        cub_val : numpy.ndarray, shape (m_nonlinear_ub,), optional
            Values of the nonlinear inequality constraints. If not provided,
            the nonlinear inequality constraints are evaluated at `x`.
        ceq_val : numpy.ndarray, shape (m_nonlinear_eq,), optional
            Values of the nonlinear equality constraints. If not provided,
            the nonlinear equality constraints are evaluated at `x`.

        Returns
        -------
        float
            Value of the merit function at `x`.
        """
        if fun_val is None:
            fun_val = self._pb.fun(x)
        if cub_val is None:
            cub_val = self._pb.cub(x)
        if ceq_val is None:
            ceq_val = self._pb.ceq(x)
        m_val = fun_val
        if self._penalty > 0.0:
            c_val = np.block([self._pb.bounds.xl - x, x - self._pb.bounds.xu, self._pb.linear_ub.a @ x - self._pb.linear_ub.b, cub_val])
            c_val = np.maximum(c_val, 0.0)
            c_val = np.block([c_val, np.abs(self._pb.linear_eq.a @ x - self._pb.linear_eq.b), np.abs(ceq_val)])
            m_val += self._penalty * np.linalg.norm(c_val)
        return m_val

    def get_constraint_linearizations(self, x):
        """
        Get the linearizations of the constraints at a given point.

        Parameters
        ----------
        x : numpy.ndarray, shape (n,)
            Point at which the linearizations of the constraints are evaluated.

        Returns
        -------
        numpy.ndarray, shape (m_linear_ub + m_nonlinear_ub, n)
            Left-hand side matrix of the linearized inequality constraints.
        numpy.ndarray, shape (m_linear_ub + m_nonlinear_ub,)
            Right-hand side vector of the linearized inequality constraints.
        numpy.ndarray, shape (m_linear_eq + m_nonlinear_eq, n)
            Left-hand side matrix of the linearized equality constraints.
        numpy.ndarray, shape (m_linear_eq + m_nonlinear_eq,)
            Right-hand side vector of the linearized equality constraints.
        """
        cub_grad = self.models.cub_grad(x)
        aub = np.block([[self._pb.linear_ub.a], [cub_grad]])
        bub = np.block([self._pb.linear_ub.b - self._pb.linear_ub.a @ x, -self.models.cub(x)])
        ceq_grad = self.models.ceq_grad(x)
        aeq = np.block([[self._pb.linear_eq.a], [ceq_grad]])
        beq = np.block([self._pb.linear_eq.b - self._pb.linear_eq.a @ x, -self.models.ceq(x)])
        return aub, bub, aeq, beq

    def get_trust_region_step(self, options):
        """
        Get the trust-region step.

        The trust-region step is computed by solving the derivative-free
        trust-region SQP subproblem using a Byrd-Omojokun composite-step
        approach. For more details, see Section 5.2.3 of [1]_.

        Parameters
        ----------
        options : dict
            Options of the solver.

        Returns
        -------
        numpy.ndarray, shape (n,)
            Normal step.
        numpy.ndarray, shape (n,)
            Tangential step.

        References
        ----------
        .. [1] T. M. Ragonneau. *Model-Based Derivative-Free Optimization
           Methods and Software*. PhD thesis, The Hong Kong Polytechnic
           University, Hong Kong, China, 2022.
        """
        # Evaluate the linearizations of the constraints.
        aub, bub, aeq, beq = self.get_constraint_linearizations(self.x_best)
        xl = self._pb.bounds.xl - self.x_best
        xu = self._pb.bounds.xu - self.x_best

        # Evaluate the normal step.
        normal_step = normal_byrd_omojokun(aub, bub, aeq, beq, xl, xu, 0.8 * self.radius, options['debug'])
        if options['debug']:
            tol = get_arrays_tol(xl, xu)
            if np.any(normal_step + tol < xl) or np.any(xu < normal_step - tol):
                warnings.warn('the normal step does not respect the bound constraint.')
            if np.linalg.norm(normal_step) > 1.1 * 0.8 * self.radius:
                warnings.warn('the normal step does not respect the trust-region constraint.')

        # Evaluate the tangential step.
        radius = np.sqrt(self.radius ** 2.0 - normal_step @ normal_step)
        xl -= normal_step
        xu -= normal_step
        bub = np.maximum(bub - np.dot(aub, normal_step), 0.0)
        g_best = self.models.fun_grad(self.x_best) + self.lag_model_hess_prod(normal_step)
        if self._pb.type in ['unconstrained', 'bound-constrained']:
            tangential_step = tangential_byrd_omojokun(g_best, self.lag_model_hess_prod, xl, xu, radius, options['debug'])
        else:
            tangential_step = constrained_tangential_byrd_omojokun(g_best, self.lag_model_hess_prod, xl, xu, aub, bub, aeq, radius, options['debug'])
        if options['debug']:
            tol = get_arrays_tol(xl, xu)
            if np.any(tangential_step + tol < xl) or np.any(xu < tangential_step - tol):
                warnings.warn('The tangential step does not respect the bound constraints.')
            if np.linalg.norm(normal_step + tangential_step) > 1.1 * np.sqrt(2.0) * self.radius:
                warnings.warn('The trial step does not respect the trust-region constraint.')
        return normal_step, tangential_step

    def get_geometry_step(self, k_new, options):
        """
        Get the geometry-improving step.

        Three different geometry-improving steps are computed and the best one
        is returned. For more details, see Section 5.2.7 of [1]_.

        Parameters
        ----------
        k_new : int
            Index of the interpolation point to be modified.
        options : dict
            Options of the solver.

        Returns
        -------
        numpy.ndarray, shape (n,)
            Geometry-improving step.

        References
        ----------
        .. [1] T. M. Ragonneau. *Model-Based Derivative-Free Optimization
           Methods and Software*. PhD thesis, The Hong Kong Polytechnic
           University, Hong Kong, China, 2022.
        """
        # Build the k_new-th Lagrange polynomial.
        coord_vec = np.squeeze(np.eye(1, self.models.npt, k_new))
        lag = Quadratic(self.models.interpolation, coord_vec)
        g_lag = lag.grad(self.models.interpolation.point(k_new), self.models.interpolation)

        # Compute a simple constrained Cauchy step.
        xl = self._pb.bounds.xl - self.x_best
        xu = self._pb.bounds.xu - self.x_best
        step = cauchy_geometry(0.0, g_lag, lambda v: lag.hess_prod(v, self.models.interpolation), xl, xu, self.radius, options['debug'])
        sigma = self.models.denominators(self.x_best + step, k_new)

        # Compute the solution on the straight lines joining the interpolation
        # points to the k-th one, and choose it if it provides a larger value of
        # the denominator of the updating formula.
        xpt = self.models.interpolation.xpt - self.models.interpolation.xpt[:, self.best_index, np.newaxis]
        xpt[:, [0, self.best_index]] = xpt[:, [self.best_index, 0]]
        step_alt = spider_geometry(0.0, g_lag, lambda v: lag.hess_prod(v, self.models.interpolation), xpt[:, 1:], xl, xu, self.radius, options['debug'])
        sigma_alt = self.models.denominators(self.x_best + step_alt, k_new)
        if abs(sigma_alt) >= abs(sigma):
            step = step_alt
            sigma = sigma_alt

        # Compute a Cauchy step on the tangent space of the active constraints.
        if self._pb.type in ['linearly constrained', 'nonlinearly constrained']:
            aub, bub, aeq, beq = self.get_constraint_linearizations(self.x_best)
            tol_bd = get_arrays_tol(xl, xu)
            tol_ub = get_arrays_tol(bub)
            free_xl = xl <= -tol_bd
            free_xu = xu >= tol_bd
            free_ub = bub >= tol_ub

            # Compute the Cauchy step.
            n_act, q = qr_tangential_byrd_omojokun(aub, aeq, free_xl, free_xu, free_ub)
            g_lag_proj = q[:, n_act:] @ (q[:, n_act:].T @ g_lag)
            norm_g_lag_proj = np.linalg.norm(g_lag_proj)
            if 0 < n_act < self._pb.n and norm_g_lag_proj > np.finfo(float).tiny * self.radius:
                step_alt = (self.radius / norm_g_lag_proj) * g_lag_proj
                if lag.curv(step_alt, self.models.interpolation) < 0.0:
                    step_alt = -step_alt

                # Evaluate the constraint violation at the Cauchy step.
                cub = aub @ step_alt - bub
                ceq = aeq @ step_alt - beq
                cbd = np.block([step_alt - xu, xl - step_alt])
                resid = max(np.max(array, initial=0.0) for array in [cub, np.abs(ceq), cbd])

                # Accept the new step if it is nearly feasible and do not
                # drastically worsen the denominator of the updating formula.
                tol = np.max(np.abs(step_alt[~free_xl]), initial=0.0)
                tol = np.max(np.abs(step_alt[~free_xu]), initial=tol)
                tol = np.max(np.abs(np.dot(aub[~free_ub, :], step_alt)), initial=tol)
                tol = min(10.0 * tol, 1e-2 * np.linalg.norm(step_alt))
                if resid <= tol:
                    sigma_alt = self.models.denominators(self.x_best + step_alt, k_new)
                    if abs(sigma_alt) >= 0.1 * abs(sigma):
                        step = np.maximum(xl, np.minimum(step_alt, xu))

        if options['debug']:
            tol = get_arrays_tol(xl, xu)
            if np.any(step + tol < xl) or np.any(xu < step - tol):
                warnings.warn('The geometry step does not respect the bound constraints.')
            if np.linalg.norm(step) > 1.1 * self.radius:
                warnings.warn('The geometry step does not respect the trust-region constraint.')
        return step

    def get_second_order_correction_step(self, step, options):
        """
        Get the second-order correction step.

        Parameters
        ----------
        step : numpy.ndarray, shape (n,)
            Trust-region step.
        options : dict
            Options of the solver.

        Returns
        -------
        numpy.ndarray, shape (n,)
            Second-order correction step.
        """
        # Evaluate the linearizations of the constraints.
        aub, bub, aeq, beq = self.get_constraint_linearizations(self.x_best)
        xl = self._pb.bounds.xl - self.x_best
        xu = self._pb.bounds.xu - self.x_best
        radius = step @ step
        soc_step = normal_byrd_omojokun(aub, bub, aeq, beq, xl, xu, radius, options['debug'])
        if options['debug']:
            tol = get_arrays_tol(xl, xu)
            if np.any(soc_step + tol < xl) or np.any(xu < soc_step - tol):
                warnings.warn('The second-order correction step does not respect the bound constraints.')
            if np.linalg.norm(soc_step) > 1.1 * radius:
                warnings.warn('The second-order correction step does not respect the trust-region constraint.')
        return soc_step

    def get_reduction_ratio(self, step, fun_val, cub_val, ceq_val):
        """
        Get the reduction ratio.

        Parameters
        ----------
        step : numpy.ndarray, shape (n,)
            Trust-region step.
        fun_val : float
            Objective function value at the trial point.
        cub_val : numpy.ndarray, shape (m_nonlinear_ub,)
            Nonlinear inequality constraint values at the trial point.
        ceq_val : numpy.ndarray, shape (m_nonlinear_eq,)
            Nonlinear equality constraint values at the trial point.

        Returns
        -------
        float
            Reduction ratio.
        """
        merit_old = self.merit(self.x_best, self.fun_best, self.cub_best, self.ceq_best)
        merit_new = self.merit(self.x_best + step, fun_val, cub_val, ceq_val)
        merit_model_old = self.merit(self.x_best, 0.0, self.models.cub(self.x_best), self.models.ceq(self.x_best))
        merit_model_new = self.merit(self.x_best + step, self.sqp_fun(step), self.sqp_cub(step), self.sqp_ceq(step))
        if abs(merit_model_old - merit_model_new) > np.finfo(float).tiny * abs(merit_old - merit_new):
            return (merit_old - merit_new) / abs(merit_model_old - merit_model_new)
        else:
            return -1.0

    def increase_penalty(self, step):
        """
        Increase the penalty parameter.

        Parameters
        ----------
        step : numpy.ndarray, shape (n,)
            Trust-region step.
        """
        aub, bub, aeq, beq = self.get_constraint_linearizations(self.x_best)
        viol_diff = np.linalg.norm(np.block([np.maximum(0.0, -bub), beq])) - np.linalg.norm(np.block([np.maximum(0.0, aub @ step - bub), aeq @ step - beq]))
        sqp_var = step @ (self.models.fun_grad(self.x_best) + 0.5 * self.lag_model_hess_prod(step))

        threshold = np.linalg.norm(np.r_[self._lm_linear_ub, self._lm_linear_eq, self._lm_nonlinear_ub, self._lm_nonlinear_eq])
        if abs(viol_diff) > np.finfo(float).tiny * abs(sqp_var):
            threshold = max(threshold, sqp_var / viol_diff)
        best_index_save = self.best_index
        if self._penalty <= 1.5 * threshold:
            self._penalty = 2.0 * threshold
            self.set_best_index()
        return best_index_save == self.best_index

    def decrease_penalty(self):
        """
        Decrease the penalty parameter.
        """
        self._penalty = min(self._penalty, self._get_low_penalty())

    def set_best_index(self):
        """
        Set the index of the best point.
        """
        best_index = self.best_index
        m_best = self.merit(self.x_best, self.models.fun_val[best_index], self.models.cub_val[best_index, :], self.models.ceq_val[best_index, :])
        r_best = self._pb.resid(self.x_best, self.models.cub_val[best_index, :], self.models.ceq_val[best_index, :])
        tol = 10.0 * np.finfo(float).eps * max(self.models.interpolation.xpt.shape) * max(abs(m_best), 1.0)
        for k in range(self.models.npt):
            if k != self.best_index:
                x_val = self.models.interpolation.point(k)
                m_val = self.merit(x_val, self.models.fun_val[k], self.models.cub_val[k, :], self.models.ceq_val[k, :])
                r_val = self._pb.resid(x_val, self.models.cub_val[k, :], self.models.ceq_val[k, :])
                if m_val < m_best or (m_val < m_best + tol and r_val < r_best):
                    best_index = k
                    m_best = m_val
                    r_best = r_val
        self._best_index = best_index

    def get_index_to_remove(self, x_new=None):
        """
        Get the index of the interpolation point to remove.

        If `x_new` is not provided, the index returned should be used during
        the geometry-improvement phase. Otherwise, the index returned is the
        best index for included `x_new` in the interpolation set.

        Parameters
        ----------
        x_new : numpy.ndarray, shape (n,), optional
            New point to be included in the interpolation set.

        Returns
        -------
        int
            Index of the interpolation point to remove.
        float
            Distance between `x_best` and the removed point.
        """
        dist_sq = np.sum(np.square(self.models.interpolation.xpt - self.models.interpolation.xpt[:, self.best_index, np.newaxis]), axis=0)
        if x_new is None:
            sigma = 1.0
            weights = dist_sq
        else:
            sigma = self.models.denominators(x_new)
            weights = np.maximum(1.0, dist_sq / max(0.1 * self.radius, self.resolution) ** 2.0) ** 3.0
        k_max = np.argmax(weights * np.abs(sigma))
        return k_max, np.sqrt(dist_sq[k_max])

    def update_radius(self, step, ratio):
        """
        Update the trust-region radius.

        Parameters
        ----------
        step : numpy.ndarray, shape (n,)
            Trust-region step.
        ratio : float
            Reduction ratio.
        """
        s_norm = np.linalg.norm(step)
        if ratio <= 0.1:
            self.radius *= 0.5
        elif ratio <= 0.7:
            self.radius = max(0.5 * self.radius, s_norm)
        else:
            self.radius = min(np.sqrt(2.0) * self.radius, max(0.5 * self.radius, 2.0 * s_norm))

    def reduce_resolution(self, options):
        """
        Reduce the resolution of the trust-region framework.

        Parameters
        ----------
        options : dict
            Options of the solver.
        """
        if 250.0 * options['radius_final'] < self.resolution:
            self.resolution *= 0.1
        elif 16.0 * options['radius_final'] < self.resolution:
            self.resolution = np.sqrt(self.resolution * options['radius_final'])
        else:
            self.resolution = options['radius_final']

        # Reduce the trust-region radius. The procedure below should not use
        # self.radius as otherwise, it will not be updated correctly.
        self._radius *= 0.5
        self._radius = max(self._radius, self.resolution)

    def shift_x_base(self, options):
        """
        Shift the base point to `x_best`.

        Parameters
        ----------
        options : dict
            Options of the solver.
        """
        self.models.shift_x_base(np.copy(self.x_best), options)

    def _get_low_penalty(self):
        r_val_ub = np.c_[(self.models.interpolation.x_base[np.newaxis, :] + self.models.interpolation.xpt.T) @ self._pb.linear_ub.a.T - self._pb.linear_ub.b[np.newaxis, :], self.models.cub_val]
        r_val_eq = (self.models.interpolation.x_base[np.newaxis, :] + self.models.interpolation.xpt.T) @ self._pb.linear_eq.a.T - self._pb.linear_eq.b[np.newaxis, :]
        r_val_eq = np.c_[r_val_eq, -r_val_eq, self.models.ceq_val, -self.models.ceq_val]
        r_val = np.c_[r_val_ub, r_val_eq]
        c_min = np.min(r_val, axis=0)
        c_max = np.max(r_val, axis=0)
        indices = c_min < 2.0 * c_max
        if np.any(indices):
            f_min = np.min(self.models.fun_val)
            f_max = np.max(self.models.fun_val)
            c_min_neg = np.minimum(0.0, c_min[indices])
            c_diff = np.min(c_max[indices] - c_min_neg)
            if c_diff > np.finfo(float).tiny * (f_max - f_min):
                penalty = (f_max - f_min) / c_diff
            else:
                penalty = np.inf
        else:
            penalty = 0.0
        return penalty

    def set_multipliers(self):
        """
        Set the Lagrange multipliers.

        This method computes and set the Lagrange multipliers of the linear and
        nonlinear constraints to be the QP multipliers.
        """
        # Build the constraints of the least-squares problem.
        incl_linear = self._pb.linear_ub.a @ self.x_best >= self._pb.linear_ub.b
        incl_nonlinear = self.cub_best >= 0.0
        incl_xl = self._pb.bounds.xl >= self.x_best
        incl_xu = self._pb.bounds.xu <= self.x_best
        m_linear = np.count_nonzero(incl_linear)
        m_nonlinear = np.count_nonzero(incl_nonlinear)
        m_xl = np.count_nonzero(incl_xl)
        m_xu = np.count_nonzero(incl_xu)
        identity = np.eye(self._pb.n)
        c_jac = np.r_[
            -identity[incl_xl, :],
            identity[incl_xu, :],
            self._pb.linear_ub.a[incl_linear, :],
            self.models.cub_grad(self.x_best, incl_nonlinear),
            self._pb.linear_eq.a,
            self.models.ceq_grad(self.x_best),
        ]

        # Solve the least-squares problem.
        if c_jac.size > 0:
            # Solve the linear system.
            g_best = self.models.fun_grad(self.x_best)
            xl_lm = np.full(c_jac.shape[0], -np.inf)
            xl_lm[:m_xl + m_xu + m_linear + m_nonlinear] = 0.0
            res = lsq_linear(c_jac.T, -g_best, bounds=(xl_lm, np.inf), method='bvls')

            # Extract the Lagrange multipliers.
            self._lm_linear_ub.fill(0.0)
            self._lm_linear_ub[incl_linear] = res.x[m_xl + m_xu:m_xl + m_xu + m_linear]
            self._lm_nonlinear_ub.fill(0.0)
            self._lm_nonlinear_ub[incl_nonlinear] = res.x[m_xl + m_xu + m_linear:m_xl + m_xu + m_linear + m_nonlinear]
            self._lm_linear_eq[:] = res.x[m_xl + m_xu + m_linear + m_nonlinear:m_xl + m_xu + m_linear + m_nonlinear + self.m_linear_eq]
            self._lm_nonlinear_eq[:] = res.x[m_xl + m_xu + m_linear + m_nonlinear + self.m_linear_eq:]