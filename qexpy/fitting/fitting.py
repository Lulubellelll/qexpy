"""This module contains curve fitting functions"""

from typing import List, Callable, Tuple, Union
from enum import Enum

import functools
import numpy as np
import scipy.optimize as opt
import qexpy.settings.literals as lit
import qexpy.data.data as data
import qexpy.data.operations as op
import qexpy.data.datasets as datasets
import qexpy.utils.utils as utils
from qexpy.utils.exceptions import InvalidArgumentTypeError


class FitModel(Enum):
    """Some preset fit models"""
    LINEAR = "linear"
    QUADRATIC = "quadratic"
    POLYNOMIAL = "polynomial"
    GAUSSIAN = "gaussian"
    EXPONENTIAL = "exponential"


class XYFit:
    """Stores the results of a curve fit"""

    def __init__(self, dataset, model_name, fit_func, result_func, result_params):
        self._dataset = dataset
        self._model_name = model_name
        self._fit_func = fit_func
        self._result_func = result_func
        self._result_params = result_params

        y_fit_res = self.fit_function(self.dataset.xdata)
        y_err = self.dataset.ydata - y_fit_res

        valid_residual_error_pairs = filter(lambda errors: errors[1] != 0, zip(y_err, self.dataset.yerr))
        chi2 = sum((res.value / err) ** 2 for res, err in valid_residual_error_pairs)

        self._residuals = y_err
        self._chi2 = chi2
        self._ndof = len(y_fit_res) - len(result_params) - 1

    def __getitem__(self, index):
        return self._result_params[index]

    def __str__(self):
        header = "----------------- Fit Results -------------------"
        return "{}\n".format(header)

    @property
    def dataset(self) -> "datasets.XYDataSet":
        """The dataset used for this fit"""
        return self._dataset

    @property
    def fit_function(self) -> Callable:
        """The function that fits to this data set"""
        return self._result_func

    @property
    def params(self) -> List[str]:
        """The fit parameters of the fit function"""
        return self._result_params

    @property
    def residuals(self) -> List:
        """The residuals of the fit"""
        return self._residuals

    @property
    def chi_squared(self) -> "data.DerivedValue":
        """The goodness of fit represented as chi^2"""
        return self._chi2

    @property
    def ndof(self) -> int:
        """The degree of freedom of this fit function"""
        return self._ndof


def fit(xdata: List, ydata: List, model: Union[Callable, str, FitModel], **kwargs) -> XYFit:
    """Perform a fit for an xy data set

    Args:
        xdata: the x-data
        ydata: the y-data
        model: the fit model given as the string or enum representation of a pre-set model
            or a callable function as a custom fit model

    Keyword Args:
        xrange (tuple|list): a pair of numbers indicating the domain of the function
        degrees(int): the degree of the polynomial if polynomial fit were chosen
        parguess(list): initial guess for the parameters
        parnames(list): the names of each parameter
        parunits(list): the units for each parameter

    """

    dataset = datasets.XYDataSet(xdata, ydata, **kwargs)
    return fit_to_xy_dataset(dataset, model, **kwargs)


def fit_to_xy_dataset(dataset, model, **kwargs) -> XYFit:  # pylint: disable = too-many-locals
    """Perform a fit on an XYDataSet"""

    model_name, fit_func = _wrap_fit_func(model)
    num_of_params, is_variable = __check_fit_func_and_get_number_of_params(fit_func)

    if model_name == lit.POLY:
        # default degree of polynomial is 3 because for degree 2 polynomials,
        # a quadratic fit would've been chosen
        num_of_params = kwargs.get("degrees", 3) + 1

    parguess = kwargs.get("parguess", None)
    __check_type_and_len_of_params(num_of_params, is_variable, parguess, "parguess")
    parnames = kwargs.get("parnames", _get_param_names(model, num_of_params))
    __check_type_and_len_of_params(num_of_params, is_variable, parnames, "parnames")
    parunits = kwargs.get("parunits", [""] * num_of_params)
    __check_type_and_len_of_params(num_of_params, is_variable, parunits, "parunits")

    xrange = kwargs.get("xrange", None)

    xdata_to_fit = dataset.xdata
    ydata_to_fit = dataset.ydata

    if xrange:
        if isinstance(xrange, (tuple, list)) and len(xrange) == 2 and xrange[0] < xrange[1]:
            indices = (xrange[0] <= dataset.xdata) & (dataset.xdata < xrange[1])
            xdata_to_fit = dataset.xdata[indices]
            ydata_to_fit = dataset.ydata[indices]
        else:
            raise ValueError("invalid fit range for xdata: {}".format(xrange))

    yerr = ydata_to_fit.errors if any(err > 0 for err in ydata_to_fit.errors) else None

    if model_name == lit.POLY:
        popt, perr = _linear_fit(xdata_to_fit, ydata_to_fit, num_of_params - 1, yerr)
    else:
        popt, perr = _non_linear_fit(fit_func, xdata_to_fit, ydata_to_fit, parguess, yerr)

    # wrap the parameters in MeasuredValue objects
    params = [data.MeasuredValue(param, err, unit=parunit, name=name)
              for param, err, parunit, name in zip(popt, perr, parunits, parnames)]

    # wrap the result function
    result_func = _combine_fit_func_and_fit_params(fit_func, params)

    return XYFit(dataset, model_name, fit_func, result_func, params)


def _linear_fit(xdata_to_fit, ydata_to_fit, degrees, yerr):
    """perform a linear fit with numpy.polyfit"""

    # noinspection PyTupleAssignmentBalance
    popt, v_matrix = np.polyfit(xdata_to_fit.values, ydata_to_fit.values, degrees, cov=True, w=1/yerr)
    perr = np.sqrt(np.diag(np.flipud(np.fliplr(v_matrix))))
    return popt, perr


def _non_linear_fit(fit_func, xdata_to_fit, ydata_to_fit, parguess, yerr):
    """perform a non-linear fit with scipy.optimize.curve_fit"""

    try:
        popt, pcov = opt.curve_fit(fit_func, xdata_to_fit.values, ydata_to_fit.values, p0=parguess, sigma=yerr)

        # adjust the fit by factoring in the uncertainty on x
        if any(err > 0 for err in xdata_to_fit.errors):
            tmp_func = _combine_fit_func_and_fit_params(fit_func, popt)
            adjusted_yerr = np.sqrt(yerr ** 2 + xdata_to_fit.errors * utils.numerical_derivative(tmp_func, xdata_to_fit.errors))

            # re-calculate the fit with adjusted uncertainties for ydata
            popt, pcov = opt.curve_fit(fit_func, xdata_to_fit.values, ydata_to_fit.values, p0=parguess, sigma=adjusted_yerr)

    except RuntimeError:

        # re-write the error message so that it can be more easily understood by the user
        raise RuntimeError("Fit could not converge. Please check that the fit model is defined, "
                           "and that the parameter guess and y errors are appropriate")

    # the error on the parameters
    perr = np.sqrt(np.diag(pcov))

    return popt, perr


def _wrap_fit_func(model: Union[str, FitModel, Callable]) -> Tuple[str, Callable]:
    """gets the callable fit function for a model

    Args:
        model: the name of a pre-set model as a string or enum, or a callable fit function

    Returns:
        the name of the fit model and the callable fit function

    """

    from inspect import signature

    if isinstance(model, str) and model in [lit.LIN, lit.QUAD, lit.POLY, lit.GAUSS, lit.EXPO]:
        return model, FITTERS[model]
    if isinstance(model, FitModel):
        return model.value, FITTERS[model.value]
    if callable(model) and len(signature(model).parameters) > 1:
        return "custom", model

    raise TypeError("model function should be one of the presets or a custom function in the form: "
                    "def model(x, *pars) where \"pars\" is the fit parameters")


def _get_param_names(model: Union[str, FitModel, Callable], num_of_params: int) -> List:
    """gets the name of fit parameters for a model if applicable"""

    fitter = model if isinstance(model, str) else model.value if isinstance(model, FitModel) else ""

    default_parnames = {
        lit.GAUSS: ["normalization", "mean", "std"],
        lit.EXPO: ["amplitude", "decay constant"],
        lit.LIN: ["slope", "intercept"]
    }

    return default_parnames[fitter] if fitter in default_parnames else [""] * num_of_params


def _combine_fit_func_and_fit_params(func: Callable, params) -> Callable:
    """wraps a function with params to a function of x"""
    return np.vectorize(lambda x: func(x, *params))


def __check_fit_func_and_get_number_of_params(func: Callable) -> Tuple[int, bool]:
    """checks the validity of a fit function and figure out the expected number of arguments

    Args:
        func: the fit function to be checked

    Returns:
        The number of parameters for this fit function, and a flag indicating if the number
        of parameters is variable

    """

    from inspect import signature, Parameter

    parameters = signature(func).parameters

    param_count = 0
    is_variable = False

    for param in parameters.values():
        if param.kind in [Parameter.KEYWORD_ONLY, Parameter.VAR_KEYWORD]:
            raise ValueError("The fit function should not have keyword arguments")
        if param.kind == Parameter.VAR_POSITIONAL:
            is_variable = True
        else:
            param_count = param_count + 1

    # the first argument of the fit function is the variable, only the rest are parameters
    param_count = param_count - 1

    return param_count, is_variable


def __check_type_and_len_of_params(expected: int, is_variable: bool, param_ref: List, param_name: str):
    """helper function to check the validity of parameter guess and names

    Args:
        expected: the expected number of parameters
        param_ref: the input to validate. e.g. "parname", "parguess", ...
        param_name: the name of the input

    Raises:
        InvalidArgumentTypeError if the input is of an invalid type
        ValueError if the number of parameter associated properties are wrong

    """

    if not param_ref:
        return  # skip if the argument is not provided

    if not isinstance(param_ref, (list, tuple)):
        raise InvalidArgumentTypeError(param_name, got=param_ref, expected="list or tuple")
    if len(param_ref) < expected if is_variable else len(param_ref) != expected:
        expected_string = "{}{}".format(expected, " or higher" if is_variable else "")
        raise ValueError("The length of {} doesn't match the number of parameters of the fit function. "
                         "Got: {}, Expected: {}".format(param_name, len(param_ref), expected_string))


FITTERS = {
    lit.LIN: lambda x, a, b: a * x + b,
    lit.QUAD: lambda x, a, b, c: a * x ** 2 + b * x + c,
    lit.POLY: lambda x, *coeffs: functools.reduce(lambda a, b: a * x + b, reversed(coeffs)),
    lit.EXPO: lambda x, c, a: c * op.exp(-a * x),
    lit.GAUSS: lambda x, norm, mean, std: norm / op.sqrt(2 * op.pi * std ** 2) * op.exp(
        -1 / 2 * (x - mean) ** 2 / std ** 2)
}
