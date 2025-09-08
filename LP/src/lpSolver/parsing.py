# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    parsing.py                                         :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: Jvasseur <jvasseur@student.42.fr>          +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2025/09/08 12:38:17 by Jvasseur          #+#    #+#              #
#    Updated: 2025/09/08 14:56:35 by Jvasseur         ###   ########.fr        #
#                                                                              #
# **************************************************************************** #

from __future__ import annotations
import sys
import csv
import os
import re
from typing import Dict, List, Tuple, Any

# ---------------------------
# Exceptions dédiées parsing
# ---------------------------
class ParseError(Exception):
    pass

# ---------------------------
# Helpers généraux
# ---------------------------
def _require_file(path: str) -> None:
    if not os.path.isfile(path):
        raise ParseError(f"Fichier introuvable: {path}")

def _first_existing(*paths: str) -> str:
    """
    Retourne le premier chemin existant parmi 'paths'.
    Lève une ParseError avec la liste attendue sinon.
    """
    for p in paths:
        if os.path.isfile(p):
            return p
    raise ParseError("Aucun des fichiers suivants n'a été trouvé: " + ", ".join(paths))

def _read_csv_dicts(path: str, required_headers: List[str]) -> List[Dict[str, str]]:
    """
    Lit un CSV (Comma-Separated Values) en dictionnaire et vérifie les en-têtes.
    Retourne une liste de lignes (dict) avec suppression des espaces superflus.
    """
    try:
        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ParseError(f"{path}: en-têtes manquantes.")
            headers = [h.strip() for h in reader.fieldnames]
            # Remap DictReader pour trim headers
            reader.fieldnames = headers

            missing = [h for h in required_headers if h not in headers]
            if missing:
                raise ParseError(f"{path}: en-têtes manquantes: {missing} ; attendues: {required_headers}")

            rows: List[Dict[str, str]] = []
            for i, row in enumerate(reader, start=2):  # start=2 car ligne 1 = headers
                clean = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                rows.append(clean)
            return rows
    except csv.Error as e:
        raise ParseError(f"{path}: CSV invalide ({e})")

def _parse_float(field: str, value: str, path: str, line_no: int, allow_empty: bool = False) -> float | None:
    if value == "" and allow_empty:
        return None
    try:
        return float(value)
    except ValueError:
        raise ParseError(f"{path}:{line_no}: '{field}' doit être un nombre (reçu: '{value}')")

# ---------------------------------------------------
# Parsing des expressions linéaires (LHS) de contraintes
# Supporte:  x + 2y - 3*z + 5  (la constante 5 sera déplacée du LHS vers le RHS)
#            2*x + y,  -x + 1.5*y,  2.0e-3*z
# ---------------------------------------------------
_VAR_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

def parse_linear_expr(expr: str) -> Tuple[Dict[str, float], float]:
    """
    Parse une expression linéaire du LHS (Left-Hand Side) et retourne:
      - coeffs: dict {var_name: coeff}
      - const_sum: constante présente sur le LHS (sera soustraite au RHS ensuite)
    Autorise les formes: 'x', '2x', '2*x', '- y', '+3*z', '1.2e3*a'
    Autorise aussi des constantes isolées: '+ 5', '-10' (elles iront dans const_sum)
    """
    if expr is None:
        raise ParseError("Expression vide")
    s = expr.replace("−", "-")  # normalise le signe moins unicode
    s = s.replace("-", "+-")    # facilite le split sur '+'
    parts = [p.strip() for p in s.split("+") if p.strip() != ""]
    if not parts:
        raise ParseError(f"Expression invalide: '{expr}'")

    coeffs: Dict[str, float] = {}
    const_sum: float = 0.0

    for term in parts:
        m = _VAR_NAME_RE.search(term)
        if m:
            var = m.group(0)
            coeff_str = term[:m.start()].replace("*", "").strip()
            if coeff_str in ("", "+"):
                coeff = 1.0
            elif coeff_str == "-":
                coeff = -1.0
            else:
                try:
                    coeff = float(coeff_str)
                except ValueError:
                    raise ParseError(f"Terme invalide '{term}' (coeff non numérique)")
            coeffs[var] = coeffs.get(var, 0.0) + coeff
        else:
            # constante pure
            try:
                const = float(term.replace("*", ""))
            except ValueError:
                raise ParseError(f"Terme invalide '{term}' (ni variable ni constante)")
            const_sum += const

    coeffs = {v: c for v, c in coeffs.items() if abs(c) > 0.0}
    if not coeffs and const_sum == 0.0:
        raise ParseError(f"Expression sans variables ni constantes: '{expr}'")
    return coeffs, const_sum

# ---------------------------------------------------
# Parsing du dossier ./data (variables.csv, objective(s).csv, constraints.csv)
# ---------------------------------------------------
def parse_data_dir(data_dir: str) -> Dict[str, Any]:
    """
    Parse le dossier de données contenant:
      - variables.csv : name, low, up, type
      - objective.csv (ou objectives.csv) : var, coeff, sense
      - constraints.csv: name, expr, sense, rhs
    Vérifications:
      - variables uniques, types valides, low <= up
      - objectif: sense constant (min|max), var déclarées, coeff numériques
      - contraintes: sense ∈ {<=,>=,==}, rhs numérique, expr linéaire, vars déclarées
      - déplacement des constantes LHS vers RHS
    """
    if not os.path.isdir(data_dir):
        raise ParseError(f"Dossier introuvable: {data_dir}")

    var_path = os.path.join(data_dir, "variables.csv")
    obj_path = _first_existing(
        os.path.join(data_dir, "objective.csv"),
        os.path.join(data_dir, "objectives.csv"),
    )
    con_path = os.path.join(data_dir, "constraints.csv")

    _require_file(var_path)
    _require_file(con_path)

    # --- variables.csv ---
    vars_rows = _read_csv_dicts(var_path, ["name", "low", "up", "type"])
    variables: Dict[str, Dict[str, Any]] = {}
    allowed_types = {"continuous", "integer", "binary"}
    for i, row in enumerate(vars_rows, start=2):
        name = row["name"]
        if not name:
            raise ParseError(f"{var_path}:{i}: 'name' vide")
        if name in variables:
            raise ParseError(f"{var_path}:{i}: variable dupliquée: '{name}'")

        vtype = row["type"].lower() if row["type"] else "continuous"
        if vtype not in allowed_types:
            raise ParseError(f"{var_path}:{i}: type inconnu '{row['type']}' (attendu: {sorted(allowed_types)})")

        low = _parse_float("low", row["low"], var_path, i, allow_empty=True)
        up = _parse_float("up", row["up"], var_path, i, allow_empty=True)
        if low is None:
            low = 0.0  # défaut utile en LP (Linear Programming / Programmation Linéaire): x >= 0
        if up is not None and up < low:
            raise ParseError(f"{var_path}:{i}: up ({up}) < low ({low}) pour '{name}'")

        variables[name] = {"low": low, "up": up, "type": vtype}

    if not variables:
        raise ParseError(f"{var_path}: aucune variable déclarée")

    # --- objective.csv / objectives.csv ---
    obj_rows = _read_csv_dicts(obj_path, ["var", "coeff", "sense"])
    obj_coeffs: Dict[str, float] = {}
    senses = set()
    for i, row in enumerate(obj_rows, start=2):
        var = row["var"]
        if not var:
            raise ParseError(f"{obj_path}:{i}: 'var' vide")
        if var not in variables:
            raise ParseError(f"{obj_path}:{i}: variable '{var}' non déclarée dans variables.csv")
        coeff = _parse_float("coeff", row["coeff"], obj_path, i)
        sense = row["sense"].lower() if row["sense"] else ""
        if sense not in {"min", "max"}:
            raise ParseError(f"{obj_path}:{i}: 'sense' doit être 'min' ou 'max' (reçu '{row['sense']}')")
        if var in obj_coeffs:
            raise ParseError(f"{obj_path}:{i}: variable '{var}' dupliquée dans l'objectif")
        obj_coeffs[var] = coeff
        senses.add(sense)

    if not obj_coeffs:
        raise ParseError(f"{obj_path}: objectif vide")
    if len(senses) != 1:
        raise ParseError(f"{obj_path}: 'sense' doit être constant (tout 'min' ou tout 'max')")
    objective = {"sense": senses.pop(), "coeffs": obj_coeffs}

    # --- constraints.csv ---
    con_rows = _read_csv_dicts(con_path, ["name", "expr", "sense", "rhs"])
    constraints: List[Dict[str, Any]] = []
    seen_names = set()
    for i, row in enumerate(con_rows, start=2):
        orig_name = (row["name"] or "").strip()
        if not orig_name:
            orig_name = f"c_{i}"

        # auto-rename en cas de doublon
        name = orig_name
        if name in seen_names:
            k = 2
            base = name
            while name in seen_names:
                name = f"{base}#{k}"
                k += 1
            print(
                f"AVERTISSEMENT: {con_path}:{i}: nom de contrainte dupliqué '{orig_name}' "
                f"→ renommé en '{name}'",
                file=sys.stderr,
            )
        seen_names.add(name)

        expr = row["expr"]
        sense = (row["sense"] or "").strip()
        if sense not in {"<=", ">=", "=="}:
            raise ParseError(f"{con_path}:{i}: sense doit être <=, >= ou == (reçu '{row['sense']}')")
        rhs = _parse_float("rhs", row["rhs"], con_path, i)

        # Parse LHS (Left-Hand Side)
        coeffs, const_sum = parse_linear_expr(expr)

        # Vérifier que toutes les variables utilisées existent
        for v in coeffs:
            if v not in variables:
                raise ParseError(f"{con_path}:{i}: variable '{v}' utilisée dans expr mais non déclarée")

        # Déplacer la constante du LHS vers le RHS
        adj_rhs = rhs - const_sum

        constraints.append(
            {
                "name": name,
                "original_name": orig_name,
                "sense": sense,
                "rhs": adj_rhs,
                "coeffs": coeffs,
                "raw_expr": expr,
                "raw_rhs": rhs,
                "moved_const": const_sum,
            }
        )

    if not constraints:
        raise ParseError(f"{con_path}: aucune contrainte fournie")

    return {
        "variables": variables,
        "objective": objective,
        "constraints": constraints,
    }

