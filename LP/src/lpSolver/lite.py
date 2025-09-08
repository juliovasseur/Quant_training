# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    lite.py                                            :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: Jvasseur <jvasseur@student.42.fr>          +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2025/09/08 12:38:17 by Jvasseur          #+#    #+#              #
#    Updated: 2025/09/08 15:34:01 by Jvasseur         ###   ########.fr        #
#                                                                              #
# **************************************************************************** #

from __future__ import annotations
import sys
from typing import Dict, List, Tuple, Any
from parsing import ParseError, parse_data_dir



def main(argc: int, argv: List[str]) -> int:
    """
    Point d'entrée principal.
    Attendu: chemin d'un dossier contenant data/*.csv
    """
    if argc < 2:
        print("Usage: python lp.py <data_dir>", file=sys.stderr)
        return 1

    data_dir = argv[1]
    try:
        model = parse_data_dir(data_dir)
        print(f"MODEL =", model)

        # Petit récap propre (ne résout rien pour l’instant)
        print("== PARSING OK ==")
        print(f"- Variables ({len(model['variables'])}): " + 
              ", ".join(f"{n}[{v['type']}:{v['low']},{v['up'] if v['up'] is not None else '∞'}]" 
                          for n, v in model['variables'].items()))
        print(f"- Objective: {model['objective']['sense']}  " + 
              " + ".join(f"{c}*{v}" for v, c in model['objective']['coeffs'].items()))
        print(f"- Constraints ({len(model['constraints'])}):")
        for c in model["constraints"]:
            lhs = " + ".join(f"{coef}*{var}" for var, coef in c["coeffs"].items()) or "0"
            moved = f"  (constante déplacée: {c['moved_const']:+g})" if abs(c["moved_const"]) > 0 else ""
            ren = f" [renommée depuis '{c['original_name']}']" if c.get("original_name") and c["original_name"] != c["name"] else ""
            print(f"  · {c['name']}: {lhs} {c['sense']} {c['rhs']:.6g}{moved}{ren}")
        return 0

    except ParseError as e:
        print(f"Erreur de parsing: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Erreur inattendue: {e}", file=sys.stderr)
        return 1
    
    print(model)

if __name__ == "__main__":
    raise SystemExit(main(len(sys.argv), sys.argv))
