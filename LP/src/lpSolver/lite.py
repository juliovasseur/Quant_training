from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from tqdm import tqdm
from .model_arrays import LPModelData
from pulp import LpMinimize, LpMaximize, LpProblem, lpDot, LpVariable, COIN_CMD, LpStatus, value


def _normalize_sense(s: str) -> str:
    s = (s or "").strip().lower()
    if s in {"min", "minimize", "minimiser"}:
        return "min"
    if s in {"max", "maximize", "maximiser"}:
        return "max"
    return "min"

def _normalize_constr_sense(op: str) -> str:
    op = (op or "").strip()
    # tolère les signes unicode
    if op in ("<=", "≤"):
        return "<="
    if op in (">=", "≥"):
        return ">="
    if op in ("==", "="):
        return "=="
    raise ValueError(f"Operateur de contrainte non supporté: {op!r}")

def _normalize_vtype(t: str) -> str:
    t = (t or "continuous").strip().lower()
    if t in {"cont", "continuous", "real"}:
        return "continuous"
    if t in {"int", "integer"}:
        return "integer"
    if t in {"bin", "binary", "bool"}:
        return "binary"
    return "continuous"

def solve_lp_with_progress(
    data: LPModelData,
    *,
    msg: bool = True,
    time_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Résout un LP/MILP avec PuLP (CBC) à partir d'un LPModelData.
    Retourne un dict avec:
      - status: str (ex: "Optimal", "Infeasible", ...)
      - objective: float | None
      - var_values: Dict[str, float]
      - details: str (récap lisible)
      - constraints: List[Dict] (slack, dual si dispo)
      - reduced_costs: Dict[str, float] (si dispo)
    """
   

    # 1) Problème
    sense = _normalize_sense(data.sense)
    prob_sense = LpMinimize if sense == "min" else LpMaximize
    prob = LpProblem("LPModel", prob_sense)

    # 2) Variables
    lp_vars: List[LpVariable] = []
    for i, name in enumerate(tqdm(data.var_names, desc="Création des variables")):
        vtype = _normalize_vtype(data.vtypes[i] if i < len(data.vtypes) else "continuous")
        low = float(data.low[i]) if i < len(data.low) and data.low[i] is not None else None
        up = float(data.up[i]) if i < len(data.up) and data.up[i] is not None else None

        if vtype == "binary":
            var = LpVariable(name, lowBound=0, upBound=1, cat="Binary")
        elif vtype == "integer":
            var = LpVariable(name, lowBound=low, upBound=up, cat="Integer")
        else:
            var = LpVariable(name, lowBound=low, upBound=up, cat="Continuous")
        lp_vars.append(var)

    # 3) Objectif
    # lpDot gère les vecteurs alignés
    prob += lpDot(data.c, lp_vars), "Objective"

    # 4) Contraintes
    constr_infos: List[Tuple[str, Any]] = []
    for j, row in enumerate(tqdm(data.A, desc="Ajout des contraintes")):
        lhs = lpDot(row, lp_vars)
        rhs = float(data.b[j])
        op = _normalize_constr_sense(data.senses[j])
        name = data.constr_names[j] if j < len(data.constr_names) and data.constr_names[j] else f"c{j}"
        if op == "<=":
            c = (lhs <= rhs)
        elif op == ">=":
            c = (lhs >= rhs)
        else:
            c = (lhs == rhs)
        prob += c, name
        constr_infos.append((name, c))

    # 5) Solveur CBC
    solver = COIN_CMD(msg=False, timeLimit=time_limit, path="/opt/homebrew/bin/cbc")
    status_code = prob.solve(solver)
    status = LpStatus.get(status_code, str(status_code))

    # 6) Récupération des résultats
    var_values = {v.name: (v.value() if v.value() is not None else float("nan")) for v in lp_vars}
    objective_value = None
    try:
        objective_value = float(value(prob.objective))
    except Exception:
        objective_value = None

    # Coûts réduits (dj) et duals/slacks si supportés (LP continu)
    reduced_costs: Dict[str, float] = {}
    for v in lp_vars:
        try:
            # v.dj n'est pas défini pour MIP; on ignore silencieusement
            rc = getattr(v, "dj")
            if rc is not None:
                reduced_costs[v.name] = float(rc)
        except Exception:
            pass

    constraints_report = []
    for name, _c in constr_infos:
        c = prob.constraints.get(name)
        if c is None:
            continue
        entry = {"name": name}
        # slack
        try:
            entry["slack"] = float(c.slack)
        except Exception:
            entry["slack"] = None
        # dual (pi) – dispo pour LP continu avec CBC
        try:
            pi = getattr(c, "pi", None)
            entry["dual"] = float(pi) if pi is not None else None
        except Exception:
            entry["dual"] = None
        constraints_report.append(entry)

    # 7) Détails lisibles
    lines = []
    lines.append("=== Résultat solveur (PuLP/CBC) ===")
    lines.append(f"Statut: {status}")
    if objective_value is not None:
        sensestr = "min" if sense == "min" else "max"
        lines.append(f"Objectif ({sensestr}): {objective_value:.6g}")
    lines.append("")
    lines.append("Variables:")
    for v in lp_vars:
        lb = v.lowBound if v.lowBound is not None else float("-inf")
        ub = v.upBound if v.upBound is not None else float("inf")
        vv = v.value()
        lines.append(f"  - {v.name} = {vv:.6g}  [lb={lb}, ub={ub}]")
    if reduced_costs:
        lines.append("")
        lines.append("Coûts réduits (si disponibles):")
        for name, rc in reduced_costs.items():
            lines.append(f"  - {name}: {rc:.6g}")
    if constraints_report:
        lines.append("")
        lines.append("Contraintes (slack / dual si dispo):")
        for e in constraints_report:
            slack = "None" if e["slack"] is None else f"{e['slack']:.6g}"
            dual = "None" if e["dual"] is None else f"{e['dual']:.6g}"
            lines.append(f"  - {e['name']}: slack={slack}, dual={dual}")

    details = "\n".join(lines)

    return {
        "status": status,
        "objective": objective_value,
        "var_values": var_values,
        "details": details,
        "constraints": constraints_report,
        "reduced_costs": reduced_costs,
        "solver": "CBC",
    }
