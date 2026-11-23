"""
Converte a exportação do D1 (JSON do wrangler) em results.csv, no formato que o analyze_results.py espera.

1) Exporte o banco:
    npx.cmd wrangler d1 execute pesquisa-senhas-pucminas-db --remote --json --command "SELECT * FROM responses ORDER BY id" > export.json
2) Converta:
    python export_results.py export.json
"""

import argparse
import csv
import json

OUTPUT_COLUMNS = [
    "score",
    "guesses_log10",
    "length",
    "has_lower",
    "has_upper",
    "has_digit",
    "has_symbol",
    "pattern_dictionary",
    "pattern_sequence",
    "pattern_repeat",
    "pattern_keyboard",
    "pattern_date",
    "pattern_none",
]


def load_rows(path):
    # O PowerShell às vezes grava o redirecionamento ">" em UTF-16, então tentamos as duas codificações
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            with open(path, encoding=encoding) as file:
                data = json.load(file)
            break
        except (UnicodeError, json.JSONDecodeError):
            continue
    else:
        raise SystemExit(f"Não consegui ler {path} como JSON.")

    # O wrangler devolve uma lista de blocos [{"results": [...], "success": true, ...}]
    blocks = data if isinstance(data, list) else [data]
    rows = []
    for block in blocks:
        rows.extend(block.get("results", []))
    return rows


def main():
    parser = argparse.ArgumentParser(description="Converte a exportação do D1 em results.csv")
    parser.add_argument("input", help="arquivo JSON exportado pelo wrangler")
    parser.add_argument("--output", default="results.csv")
    args = parser.parse_args()

    rows = load_rows(args.input)
    with open(args.output, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} respostas gravadas em {args.output}")


if __name__ == "__main__":
    main()
