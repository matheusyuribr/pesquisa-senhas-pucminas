"""
Etapa 5 da metodologia: análise estatística dos resultados do zxcvbn.

Lê o results.csv gerado pelo process_passwords.py (só valores derivados, sem senhas) e gera:
- analysis_report.txt     -> relatório com todos os números para a seção de Resultados
- score_frequency.csv     -> frequência absoluta e relativa dos 5 níveis de score
- crack_times.csv         -> mediana e quartis do tempo de quebra nos 4 cenários
- feature_tests.csv       -> Mann-Whitney e Fisher para classes de caracteres e padrões
- score_table.tex         -> tabela de frequência pronta para o LaTeX
- score_distribution.png  -> gráfico de barras da distribuição dos scores

Uso:
    python analyze_results.py
    python analyze_results.py --input results.csv --output-dir output
"""

import argparse
import math
import os
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats

SCORE_LABELS = {0: "Muito Fraca", 1: "Fraca", 2: "Razoável", 3: "Forte", 4: "Muito Forte"}

# Cenários do zxcvbn, em tentativas por segundo
ATTACK_SCENARIOS = {
    "online_throttled": ("Online com limitação (100/h)", 100 / 3600),
    "online_unthrottled": ("Online sem limitação (10/s)", 10),
    "offline_slow_hash": ("Offline, hash lento (10^4/s)", 1e4),
    "offline_fast_hash": ("Offline, hash rápido (10^10/s)", 1e10),
}

FEATURE_LABELS = {
    "has_lower": "Minúsculas",
    "has_upper": "Maiúsculas",
    "has_digit": "Dígitos",
    "has_symbol": "Símbolos",
    "pattern_dictionary": "Padrão: dicionário",
    "pattern_sequence": "Padrão: sequência",
    "pattern_repeat": "Padrão: repetição",
    "pattern_keyboard": "Padrão: teclado",
    "pattern_date": "Padrão: data",
    "pattern_none": "Padrão: nenhum",
}

ALPHA = 0.05


def wilson_interval(successes, total, z=1.96):
    if total == 0:
        return float("nan"), float("nan")
    proportion = successes / total
    denominator = 1 + z ** 2 / total
    center = (proportion + z ** 2 / (2 * total)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z ** 2 / (4 * total ** 2)) / denominator
    return center - margin, center + margin


def human_time(seconds):
    units = [("anos", 365 * 24 * 3600), ("dias", 24 * 3600), ("horas", 3600), ("minutos", 60), ("segundos", 1)]
    if seconds < 1:
        return "menos de 1 segundo"
    if seconds > 100 * 365 * 24 * 3600:
        return "mais de 100 anos"
    for name, size in units:
        if seconds >= size:
            return f"{seconds / size:.1f} {name}"
    return f"{seconds:.1f} segundos"


def fmt_p(value):
    return "< 0.001" if value < 0.001 else f"{value:.3f}"


def describe_scores(df, lines):
    total = len(df)
    counts = df["score"].value_counts().reindex(range(5), fill_value=0)
    frequency = pd.DataFrame({
        "score": counts.index,
        "level": [SCORE_LABELS[s] for s in counts.index],
        "absolute": counts.values,
        "relative_pct": (counts.values / total * 100).round(2),
    })

    q1, median, q3 = df["score"].quantile([0.25, 0.5, 0.75], interpolation="nearest")
    mode = int(df["score"].mode().iloc[0])

    lines.append("== Distribuição dos scores ==")
    lines.append(f"Total de senhas analisadas: {total}")
    for _, row in frequency.iterrows():
        lines.append(f"  {row['score']} ({row['level']}): {row['absolute']} ({row['relative_pct']:.2f}%)")
    lines.append(f"Mediana: {int(median)} | Q1: {int(q1)} | Q3: {int(q3)} | Moda: {mode}")
    lines.append("")

    weak = int((df["score"] <= 1).sum())
    strong = int((df["score"] >= 3).sum())
    lines.append("== Proporções com IC 95% (Wilson) ==")
    for name, count in [("Fracas (score 0 ou 1)", weak), ("Fortes (score 3 ou 4)", strong)]:
        low, high = wilson_interval(count, total)
        lines.append(f"  {name}: {count / total * 100:.2f}% [IC 95%: {low * 100:.2f}% a {high * 100:.2f}%]")
    lines.append("")
    return frequency


def describe_guesses(df, lines):
    q1, median, q3 = df["guesses_log10"].quantile([0.25, 0.5, 0.75])
    lines.append("== guesses_log10 ==")
    lines.append(f"  Mediana: {median:.2f} | Q1: {q1:.2f} | Q3: {q3:.2f}")
    lines.append("")

    rows = []
    lines.append("== Tempo estimado de quebra (mediana e quartis) ==")
    for key, (label, rate) in ATTACK_SCENARIOS.items():
        seconds = (10 ** df["guesses_log10"]) / rate
        s_q1, s_median, s_q3 = seconds.quantile([0.25, 0.5, 0.75])
        under_one_day = (seconds < 24 * 3600).mean() * 100
        rows.append({
            "scenario": key,
            "label": label,
            "median_seconds": s_median,
            "q1_seconds": s_q1,
            "q3_seconds": s_q3,
            "pct_under_1_day": round(under_one_day, 2),
        })
        lines.append(f"  {label}")
        lines.append(f"    mediana: {human_time(s_median)} | Q1: {human_time(s_q1)} | Q3: {human_time(s_q3)}")
        lines.append(f"    quebráveis em menos de 1 dia: {under_one_day:.2f}%")
    lines.append("")
    return pd.DataFrame(rows)


def correlation_tests(df, lines):
    lines.append("== Correlação de Spearman ==")
    for target in ["score", "guesses_log10"]:
        rho, p_value = stats.spearmanr(df["length"], df[target])
        lines.append(f"  comprimento x {target}: rho = {rho:.3f}, p = {fmt_p(p_value)}")
    lines.append("")


def feature_tests(df, lines):
    weak = df["score"] <= 1
    rows = []
    lines.append("== Mann-Whitney (score com x sem a característica) e Fisher (característica x senha fraca) ==")
    lines.append("  r > 0: característica associada a score MAIOR | OR > 1: característica associada a senha FRACA")

    for column, label in FEATURE_LABELS.items():
        present = df[column] == 1
        n_with, n_without = int(present.sum()), int((~present).sum())
        row = {"feature": column, "label": label, "n_with": n_with, "n_without": n_without}

        if n_with == 0 or n_without == 0:
            lines.append(f"  {label}: teste não aplicável (grupo vazio)")
            rows.append(row)
            continue

        scores_with = df.loc[present, "score"]
        scores_without = df.loc[~present, "score"]
        u_stat, mw_p = stats.mannwhitneyu(scores_with, scores_without, alternative="two-sided")
        rank_biserial = 2 * u_stat / (n_with * n_without) - 1

        table = [
            [int((present & weak).sum()), int((present & ~weak).sum())],
            [int((~present & weak).sum()), int((~present & ~weak).sum())],
        ]
        odds_ratio, fisher_p = stats.fisher_exact(table)

        row.update({
            "median_score_with": float(scores_with.median()),
            "median_score_without": float(scores_without.median()),
            "mann_whitney_u": float(u_stat),
            "mann_whitney_p": float(mw_p),
            "rank_biserial_r": round(rank_biserial, 4),
            "pct_weak_with": round(table[0][0] / n_with * 100, 2),
            "pct_weak_without": round(table[1][0] / n_without * 100, 2),
            "fisher_odds_ratio": float(odds_ratio),
            "fisher_p": float(fisher_p),
            "significant_mw": mw_p < ALPHA,
            "significant_fisher": fisher_p < ALPHA,
        })
        rows.append(row)
        lines.append(
            f"  {label} (n com = {n_with}): mediana {row['median_score_with']:.0f} x {row['median_score_without']:.0f}, "
            f"r = {rank_biserial:.3f}, p = {fmt_p(mw_p)} | fracas {row['pct_weak_with']:.1f}% x {row['pct_weak_without']:.1f}%, "
            f"OR = {odds_ratio:.2f}, p = {fmt_p(fisher_p)}"
        )
    lines.append("")
    return pd.DataFrame(rows)


def save_latex_table(frequency, path):
    # Ajusta separadores para o padrão brasileiro: milhar com ponto, decimal com vírgula
    body_lines = []
    for row in frequency.itertuples():
        absolute = f"{row.absolute:,}".replace(",", ".")
        relative = f"{row.relative_pct:.2f}".replace(".", "{,}")
        body_lines.append(f"{row.score} & {row.level} & {absolute} & {relative}\\% \\\\")
    body = "\n".join(body_lines)
    total = f"{int(frequency['absolute'].sum()):,}".replace(",", ".")

    latex = (
        "\\begin{table}[htbp]\n"
        "\\centering\n"
        "\\caption{Distribuição dos \\textit{scores} do \\textit{zxcvbn} na amostra}\n"
        "\\label{tab:score_frequency}\n"
        "\\begin{tabular}{clrr}\n"
        "\\hline\n"
        "\\textit{Score} & Nível & Frequência absoluta & Frequência relativa \\\\\n"
        "\\hline\n"
        f"{body}\n"
        "\\hline\n"
        f" & Total & {total} & 100\\% \\\\\n"
        "\\hline\n"
        "\\end{tabular}\n"
        "\\\\[2pt] {\\small Fonte: Elaborado pelo autor.}\n"
        "\\end{table}\n"
    )
    with open(path, "w", encoding="utf-8") as file:
        file.write(latex)


def save_score_chart(frequency, path):
    fig, ax = plt.subplots(figsize=(7, 4), dpi=200)
    labels = [f"{s}\n{SCORE_LABELS[s]}" for s in frequency["score"]]
    bars = ax.bar(labels, frequency["relative_pct"], color="#3b6fb6", width=0.6)

    for bar, pct in zip(bars, frequency["relative_pct"]):
        ax.annotate(f"{pct:.1f}%".replace(".", ","), (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=9, color="#333333")

    ax.set_ylabel("Senhas (%)")
    ax.set_xlabel("Score do zxcvbn")
    ax.set_ylim(0, max(frequency["relative_pct"]) * 1.15)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#999999")
    ax.tick_params(colors="#333333")
    ax.yaxis.grid(True, color="#e5e5e5", linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Análise estatística dos resultados do zxcvbn.")
    parser.add_argument("--input", default="results.csv")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    start = time.perf_counter()
    os.makedirs(args.output_dir, exist_ok=True)
    df = pd.read_csv(args.input)

    lines = ["RELATÓRIO DE ANÁLISE - força das senhas dos estudantes (zxcvbn)", ""]
    frequency = describe_scores(df, lines)
    crack_times = describe_guesses(df, lines)
    correlation_tests(df, lines)
    tests = feature_tests(df, lines)

    frequency.to_csv(os.path.join(args.output_dir, "score_frequency.csv"), index=False)
    crack_times.to_csv(os.path.join(args.output_dir, "crack_times.csv"), index=False)
    tests.to_csv(os.path.join(args.output_dir, "feature_tests.csv"), index=False)
    save_latex_table(frequency, os.path.join(args.output_dir, "score_table.tex"))
    save_score_chart(frequency, os.path.join(args.output_dir, "score_distribution.png"))

    elapsed = time.perf_counter() - start
    lines.append(f"Tempo da análise estatística: {elapsed:.1f} s ({elapsed / 60:.2f} min)")
    report = "\n".join(lines)
    with open(os.path.join(args.output_dir, "analysis_report.txt"), "w", encoding="utf-8") as file:
        file.write(report + "\n")

    print(report)
    print(f"\nArquivos gerados em: {args.output_dir}/")


if __name__ == "__main__":
    main()
