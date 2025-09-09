from typing import NamedTuple, Optional, Dict, List, Any


class LPModelData(NamedTuple):
    """Structure compacte pour manipuler le modèle LP en tableaux.

    - var_names: noms des variables, dans l'ordre utilisé partout
    - c: coefficients de l'objectif alignés sur var_names
    - sense: "min" ou "max"
    - A: matrice des coefficients des contraintes (LHS)
    - senses: opérateurs des contraintes (<=, >=, ==) alignés sur A
    - b: seconds membres (RHS) alignés sur A
    - low/up: bornes inf/sup des variables, alignées sur var_names
    - vtypes: types des variables (continuous/integer/binary)
    - constr_names: noms des contraintes pour le solveur
    - var_index: mapping nom -> index
    """

    var_names: List[str]
    c: List[float]
    sense: str
    A: List[List[float]]
    senses: List[str]
    b: List[float]
    low: List[float]
    up: List[Optional[float]]
    vtypes: List[str]
    constr_names: List[str]
    var_index: Dict[str, int]


def build_model_arrays(model: Dict[str, Any]) -> LPModelData:
    """Convertit la sortie de parsing (dict) en tableaux pour le solveur."""
    # 1) variables & index
    var_names = list(model["variables"].keys())
    var_index = {name: i for i, name in enumerate(var_names)}
    n = len(var_names)

    # 2) bornes & types
    low: List[float] = []
    up: List[Optional[float]] = []
    vtypes: List[str] = []
    for name in var_names:
        meta = model["variables"][name]
        low.append(float(meta["low"]) if meta["low"] is not None else 0.0)
        up.append(float(meta["up"]) if meta["up"] is not None else None)
        vtypes.append(meta["type"])

    # 3) objectif
    sense = str(model["objective"]["sense"]).lower()
    c = [0.0] * n
    for v, coeff in model["objective"]["coeffs"].items():
        c[var_index[v]] = float(coeff)

    # 4) contraintes
    A: List[List[float]] = []
    b: List[float] = []
    senses: List[str] = []
    constr_names: List[str] = []
    for cst in model["constraints"]:
        row = [0.0] * n
        for v, coef in cst["coeffs"].items():
            row[var_index[v]] = float(coef)
        A.append(row)
        b.append(float(cst["rhs"]))
        senses.append(cst["sense"])
        constr_names.append(cst["name"])

    return LPModelData(
        var_names=var_names,
        c=c,
        sense=sense,
        A=A,
        senses=senses,
        b=b,
        low=low,
        up=up,
        vtypes=vtypes,
        constr_names=constr_names,
        var_index=var_index,
    )


__all__ = ["LPModelData", "build_model_arrays"]

