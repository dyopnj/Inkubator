"""
inkubator_train.py
==================
Multi-model trainer untuk Kontrol Inkubator Telur
Dataset: temperature_humidity_data.csv (dari Kaggle)

Model: lr, ridge, lasso, huber, glm, svr, rf, et, gb, ada, dt, mlp

Cara pakai:
    pip install pandas numpy scikit-learn matplotlib
    python inkubator_train.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.tree import DecisionTreeRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.linear_model import (
    LinearRegression, Ridge, Lasso, HuberRegressor,
    PoissonRegressor, GammaRegressor, TweedieRegressor
)
from sklearn.svm import SVR
from sklearn.ensemble import (
    RandomForestRegressor, ExtraTreesRegressor,
    GradientBoostingRegressor, AdaBoostRegressor
)
import os, sys
from datetime import datetime

# ============================================================
#  KONFIGURASI
# ============================================================

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
CSV_PATH      = os.path.join(SCRIPT_DIR, "temperature_humidity_data.csv")
SAMPLE_SIZE   = 60000

# ===== Pilihan Model =====
# "lr"    — Linear Regression         y = w·x + b,           ~12B RAM
# "ridge" — Ridge Regression          y = w·x + b + L2,      ~12B RAM
# "lasso" — Lasso Regression          y = w·x + b + L1,      ~12B RAM
# "huber" — Huber Regression          robust to outliers,    ~12B RAM
# "glm"   — GLM (Poisson/Gamma)       g(y) = w·x + b,        ~12B RAM
# "svr"   — SVR (linear)              y = w·x + b,            ~12B RAM
# "rf"    — Random Forest             n_tree × if-else,       0 RAM
# "et"    — Extra Trees               sama RF, split acak
# "gb"    — Gradient Boosting         sequential trees,       0 RAM
# "ada"   — AdaBoost                  weighted trees,         0 RAM
# "dt"    — Decision Tree (default)   nested if-else,         0 RAM
# "mlp"   — Neural Network (MLP)      butuh scaler,           ~2KB
# "all"   — Train all models + save comparison to model_comparison.txt
MODEL_TYPE    = "all"

# Konfigurasi GLM
GLM_FAMILY    = "poisson"
GLM_POWER     = 1.5

# Konfigurasi SVR
SVR_KERNEL    = "linear"
SVR_C         = 1.0
SVR_EPSILON   = 0.1

# Konfigurasi Ensemble (rf/et/gb/ada)
EN_N_ESTIMATORS = 10
EN_MAX_DEPTH    = 4
EN_MIN_LEAF     = 5
EN_LR           = 0.1

# Konfigurasi DT
DT_MAX_DEPTH  = 5
DT_MIN_LEAF   = 5

# Konfigurasi MLP
HIDDEN_LAYERS = (8, 8)
MAX_ITER      = 1000

# Konfigurasi Umum
TEST_SIZE     = 0.2
RANDOM_SEED   = 42

# ============================================================
#  MEMBERSHIP FUNCTIONS
# ============================================================

def triMF(x, a, b, c):
    if x <= a or x >= c: return 0.0
    elif x <= b: return (x - a) / (b - a)
    else:        return (c - x) / (c - b)

def trapMF(x, a, b, c, d):
    if x <= a or x >= d: return 0.0
    elif x <= b: return (x - a) / (b - a)
    elif x <= c: return 1.0
    else:        return (d - x) / (d - c)

# ============================================================
#  LABEL GENERATOR (Fuzzy Rule-Based)
# ============================================================

def generate_label(t, h):
    dingin  = trapMF(t, 30.0, 33.0, 36.0, 37.2)
    normalT = triMF (t, 36.5, 37.5, 38.5)
    panas   = trapMF(t, 38.0, 39.0, 42.0, 43.0)

    kering  = trapMF(h,  0.0, 10.0, 40.0, 52.0)
    normalH = triMF (h, 48.0, 60.0, 72.0)
    lembap  = trapMF(h, 68.0, 75.0,100.0,101.0)

    R = {
        'dc': min(dingin,  kering ),
        'dn': min(dingin,  normalH),
        'dl': min(dingin,  lembap ),
        'nc': min(normalT, kering ),
        'nn': min(normalT, normalH),
        'nl': min(normalT, lembap ),
        'pc': min(panas,   kering ),
        'pn': min(panas,   normalH),
        'pl': min(panas,   lembap ),
    }

    HEAT = {'dc':95, 'dn':85, 'dl':80, 'nc':65, 'nn':50, 'nl':40, 'pc':20, 'pn':15, 'pl':5}
    FAN  = {'dc':15, 'dn':20, 'dl':30, 'nc':40, 'nn':50, 'nl':55, 'pc':75, 'pn':85, 'pl':95}

    den = sum(R.values())
    if den == 0: return 50, 50

    heater = int(np.clip(sum(R[k] * HEAT[k] for k in R) / den, 0, 100))
    fan    = int(np.clip(sum(R[k] * FAN[k]  for k in R) / den, 0, 100))

    if t > 41.5: return 0,   100
    if t < 34.0: return 100, 10
    return heater, fan

# ============================================================
#  MODEL METADATA
# ============================================================

M = {
    "lr":    {"label": "Linear Regression",        "pfx": "lr"},
    "ridge": {"label": "Ridge Regression",          "pfx": "ridge"},
    "lasso": {"label": "Lasso Regression",          "pfx": "lasso"},
    "huber": {"label": "Huber Regression",          "pfx": "huber"},
    "glm":   {"label": f"GLM ({GLM_FAMILY})",       "pfx": "glm"},
    "svr":   {"label": f"SVR ({SVR_KERNEL})",       "pfx": "svr"},
    "rf":    {"label": "Random Forest",             "pfx": "rf"},
    "et":    {"label": "Extra Trees",               "pfx": "et"},
    "gb":    {"label": "Gradient Boosting",         "pfx": "gb"},
    "ada":   {"label": "AdaBoost",                  "pfx": "ada"},
    "dt":    {"label": "Decision Tree",             "pfx": "dt"},
    "mlp":   {"label": "Neural Network (MLP)",      "pfx": "nn"},
    "all":   {"label": "All Models Comparison",      "pfx": "all"},
}

# ============================================================
#  EXPORT HELPERS — shared template + writers
# ============================================================

INFER_ENGINE = """/**
 * {fname}  —  {label} untuk Inkubator ESP32
 * Generated : {date}
 * Dataset   : temperature_humidity_data.csv (Kaggle)
 *
 * Input  : suhu (°C), kelembapan (%)
 * Output : heater_pct (0-100), fan_pct (0-100)
 */

#ifndef {guard}
#define {guard}

{data}

static void {pfx}_predict(float suhu, float kelembapan, int *heater, int *kipas) {{
    float h_raw = {pfx}_predict_heater(suhu, kelembapan);
    float f_raw = {pfx}_predict_fan(suhu, kelembapan);

    int h = (int)(h_raw + 0.5f);
    int f = (int)(f_raw + 0.5f);
    if (h < 0) h = 0; if (h > 100) h = 100;
    if (f < 0) f = 0; if (f > 100) f = 100;

    if (suhu > 41.5f) {{ h = 0;   f = 100; }}
    if (suhu < 34.0f) {{ h = 100; f = 10;  }}

    *heater = h;
    *kipas  = f;
}}

#endif // {guard}
"""

def _write_model(pfx, label, data):
    path = f"{pfx}_model.h"
    guard = f"{pfx.upper()}_MODEL_H"
    text = INFER_ENGINE.format(
        fname=f"{pfx}_model.h", label=label,
        date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        guard=guard, data=data, pfx=pfx
    )
    with open(path, "w") as f:
        f.write(text)
    print(f"  -> {path}  ({os.path.getsize(path)/1024:.1f} KB)")
    return path

def _write_control(pfx, cap):
    h = f"{pfx}_control.h"
    cpp = f"{pfx}_control.cpp"
    with open(h, "w") as f:
        f.write(f"""#ifndef {cap}_CONTROL_H
#define {cap}_CONTROL_H

typedef struct {{
    int heater;
    int kipas;
}} {cap}Output;

{cap}Output {pfx}Control(float suhu, float kelembapan);

#endif
""")
    print(f"  -> {h}")
    with open(cpp, "w") as f:
        f.write(f"""#include "{h}"
#include "{pfx}_model.h"

{cap}Output {pfx}Control(float suhu, float kelembapan) {{
    {cap}Output out;
    {pfx}_predict(suhu, kelembapan, &out.heater, &out.kipas);
    return out;
}}
""")
    print(f"  -> {cpp}")

# ============================================================
#  EXPORT: LINEAR MODELS (lr/ridge/lasso/huber/glm/svr-linear)
#  C code: y = w0 + w1*suhu + w2*kelembapan
# ============================================================

def export_linear(mh, mf, model_type):
    meta = M[model_type]
    pfx = meta["pfx"]
    hw1, hw2 = float(mh.coef_[0]), float(mh.coef_[1])
    hb = float(mh.intercept_)
    fw1, fw2 = float(mf.coef_[0]), float(mf.coef_[1])
    fb = float(mf.intercept_)
    data = f"""static float {pfx}_predict_heater(float suhu, float kelembapan) {{
    return {hw1:.6f}f * suhu + {hw2:.6f}f * kelembapan + {hb:.6f}f;
}}

static float {pfx}_predict_fan(float suhu, float kelembapan) {{
    return {fw1:.6f}f * suhu + {fw2:.6f}f * kelembapan + {fb:.6f}f;
}}"""
    _write_model(pfx, meta["label"], data)
    _write_control(pfx, pfx.upper())
    return f"Coefs H=({hw1:.4f},{hw2:.4f},{hb:.4f}) F=({fw1:.4f},{fw2:.4f},{fb:.4f})"

# ============================================================
#  EXPORT: DECISION TREE
# ============================================================

def _tree_cc(tree, names, nid, indent):
    p = "    " * indent
    if tree.feature[nid] < 0:
        return f"{p}return {tree.value[nid][0][0]:.2f}f;\n"
    feat = names[tree.feature[nid]]
    thr = tree.threshold[nid]
    left = tree.children_left[nid]
    right = tree.children_right[nid]
    c = f"{p}if ({feat} <= {thr:.2f}f) {{\n"
    c += _tree_cc(tree, names, left, indent + 1)
    c += f"{p}}} else {{\n"
    c += _tree_cc(tree, names, right, indent + 1)
    c += f"{p}}}\n"
    return c

def export_dt(mh, mf):
    th = mh.tree_; tf = mf.tree_
    fn = ["suhu", "kelembapan"]
    hc = _tree_cc(th, fn, 0, 1)
    fc = _tree_cc(tf, fn, 0, 1)
    data = f"// Heater DT: depth={th.max_depth}, nodes={th.node_count}\n"
    data += f"static float dt_predict_heater(float suhu, float kelembapan) {{\n{hc}}}\n\n"
    data += f"// Fan DT: depth={tf.max_depth}, nodes={tf.node_count}\n"
    data += f"static float dt_predict_fan(float suhu, float kelembapan) {{\n{fc}}}\n"
    _write_model("dt", "Decision Tree", data)
    _write_control("dt", "DT")
    total_nodes = th.node_count + tf.node_count
    return f"Depth H={th.max_depth}/F={tf.max_depth}, Nodes H={th.node_count}/F={tf.node_count} (~{total_nodes*8}B Flash, 0 RAM)"

# ============================================================
#  EXPORT: ENSEMBLE (rf/et/gb/ada)
# ============================================================

def _ens_trees_code(estimators, pfx, side, is_gb=False):
    fn = ["suhu", "kelembapan"]
    code = ""
    for i, est in enumerate(estimators):
        # GB stores estimators as 2D array (n_estimators, 1)
        tree = est[0] if is_gb else est
        code += f"static float {pfx}_{side}{i}(float suhu, float kelembapan) {{\n"
        code += _tree_cc(tree.tree_, fn, 0, 1)
        code += "}\n\n"
    return code

def export_ensemble(mh, mf, model_type):
    meta = M[model_type]
    pfx = meta["pfx"]
    n = len(mh.estimators_)
    is_gb = model_type == "gb"
    hc = _ens_trees_code(mh.estimators_, pfx, "h", is_gb)
    fc = _ens_trees_code(mf.estimators_, pfx, "f", is_gb)

    if model_type in ("rf", "et"):
        agg_h = f"""static float {pfx}_predict_heater(float suhu, float kelembapan) {{
    float s = 0.0f;
""" + "\n".join(f"    s += {pfx}_h{i}(suhu, kelembapan);" for i in range(n)) + f"""
    return s / {n}.0f;
}}"""
        agg_f = f"""static float {pfx}_predict_fan(float suhu, float kelembapan) {{
    float s = 0.0f;
""" + "\n".join(f"    s += {pfx}_f{i}(suhu, kelembapan);" for i in range(n)) + f"""
    return s / {n}.0f;
}}"""
    elif model_type == "gb":
        lr = mh.learning_rate
        agg_h = f"""static float {pfx}_predict_heater(float suhu, float kelembapan) {{
    float y = 0.0f;
""" + "\n".join(f"    y += {lr}f * {pfx}_h{i}(suhu, kelembapan);" for i in range(n)) + """
    return y;
}"""
        agg_f = f"""static float {pfx}_predict_fan(float suhu, float kelembapan) {{
    float y = 0.0f;
""" + "\n".join(f"    y += {lr}f * {pfx}_f{i}(suhu, kelembapan);" for i in range(n)) + """
    return y;
}"""
    elif model_type == "ada":
        wh = mh.estimator_weights_
        wf = mf.estimator_weights_
        swh = sum(wh)
        swf = sum(wf)
        agg_h = f"""static float {pfx}_predict_heater(float suhu, float kelembapan) {{
    float s = 0.0f;
""" + "\n".join(f"    s += {wh[i]:.6f}f * {pfx}_h{i}(suhu, kelembapan);" for i in range(n)) + f"""
    return s / {swh:.6f}f;
}}"""
        agg_f = f"""static float {pfx}_predict_fan(float suhu, float kelembapan) {{
    float s = 0.0f;
""" + "\n".join(f"    s += {wf[i]:.6f}f * {pfx}_f{i}(suhu, kelembapan);" for i in range(n)) + f"""
    return s / {swf:.6f}f;
}}"""

    data = f"// {meta['label']}: {n} trees, depth~{EN_MAX_DEPTH}\n\n{hc}{fc}{agg_h}\n\n{agg_f}"
    _write_model(pfx, meta["label"], data)
    _write_control(pfx, pfx.upper())
    return f"Trees: {n}, depth~{EN_MAX_DEPTH}"

# ============================================================
#  EXPORT: NEURAL NETWORK (MLP)
# ============================================================

def export_nn(mh, mf, scaler):
    sc_min = scaler.data_min_
    sc_scale = scaler.scale_
    n1 = HIDDEN_LAYERS[0]
    n2 = HIDDEN_LAYERS[1] if len(HIDDEN_LAYERS) > 1 else HIDDEN_LAYERS[0]

    def layer_str(p, idx, W, b):
        r, c = W.shape
        l = [f"// Layer {idx+1}: {r} -> {c}",
             f"static const float {p}_W{idx+1}[{r}][{c}] = {{"]
        for row in W:
            l.append(f"  {{{', '.join(f'{v:.6f}f' for v in row)}}},")
        l.append("};")
        l.append(f"static const float {p}_B{idx+1}[{c}] = {{ {', '.join(f'{v:.6f}f' for v in b)} }};")
        l.append("")
        return "\n".join(l)

    lines = [f"""#ifndef NN_MODEL_H
#define NN_MODEL_H

#include <math.h>

static const float SCALER_MIN[2]   = {{ {sc_min[0]:.6f}f, {sc_min[1]:.6f}f }};
static const float SCALER_SCALE[2] = {{ {sc_scale[0]:.8f}f, {sc_scale[1]:.8f}f }};

// ===== HEATER WEIGHTS ====="""]
    for i, (W, b) in enumerate(zip(mh.coefs_, mh.intercepts_)):
        lines.append(layer_str("H", i, W, b))
    lines.append("// ===== FAN WEIGHTS =====")
    for i, (W, b) in enumerate(zip(mf.coefs_, mf.intercepts_)):
        lines.append(layer_str("F", i, W, b))

    lines.append(f"""
static inline float _relu(float x) {{ return x > 0.0f ? x : 0.0f; }}

static float _mlp_fwd(float x0, float x1,
    const float W1[][{n1}], const float B1[{n1}],
    const float W2[][{n2}], const float B2[{n2}],
    const float W3[][1], const float B3[1]) {{
    float h1[{n1}], h2[{n2}];
    for (int j = 0; j < {n1}; j++)
        h1[j] = _relu(x0 * W1[0][j] + x1 * W1[1][j] + B1[j]);
    for (int j = 0; j < {n2}; j++) {{
        float s = B2[j];
        for (int i = 0; i < {n1}; i++) s += h1[i] * W2[i][j];
        h2[j] = _relu(s);
    }}
    float out = B3[0];
    for (int i = 0; i < {n2}; i++) out += h2[i] * W3[i][0];
    return out;
}}

static void nn_predict(float suhu, float kelembapan, int *heater, int *kipas) {{
    float x0 = (suhu       - SCALER_MIN[0]) * SCALER_SCALE[0];
    float x1 = (kelembapan - SCALER_MIN[1]) * SCALER_SCALE[1];
    if (x0 < 0.0f) x0 = 0.0f; if (x0 > 1.0f) x0 = 1.0f;
    if (x1 < 0.0f) x1 = 0.0f; if (x1 > 1.0f) x1 = 1.0f;

    float h_raw = _mlp_fwd(x0, x1, H_W1, H_B1, H_W2, H_B2, H_W3, H_B3);
    float f_raw = _mlp_fwd(x0, x1, F_W1, F_B1, F_W2, F_B2, F_W3, F_B3);

    int h = (int)(h_raw + 0.5f);
    int f = (int)(f_raw + 0.5f);
    if (h < 0) h = 0; if (h > 100) h = 100;
    if (f < 0) f = 0; if (f > 100) f = 100;

    if (suhu > 41.5f) {{ h = 0;   f = 100; }}
    if (suhu < 34.0f) {{ h = 100; f = 10;  }}

    *heater = h;
    *kipas  = f;
}}

#endif // NN_MODEL_H
""")

    path = "nn_model.h"
    with open(path, "w") as f:
        f.write("\n".join(lines))
    tp = (sum(w.size for w in mh.coefs_) + sum(b.size for b in mh.intercepts_) +
          sum(w.size for w in mf.coefs_) + sum(b.size for b in mf.intercepts_))
    print(f"  -> {path}  ({os.path.getsize(path)/1024:.1f} KB)  params={tp} (~{tp*4}B)")
    _write_control("nn", "NN")
    return f"Arch 2->{HIDDEN_LAYERS}->1, Params: {tp}"

# ============================================================
#  PLOT REPORT
# ============================================================

def plot_report(yh_test, ph, yf_test, pf, T_all, H_all, hl, fl, model_type="dt"):
    ml = M[model_type]["label"]
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle(f"Inkubator {ml} Training Report", fontsize=14, fontweight='bold')
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.4, wspace=0.35)

    ax1 = fig.add_subplot(gs[0, 0])
    ax1.scatter(yh_test[:500], ph[:500], alpha=0.3, s=10, color='tomato')
    ax1.plot([0,100],[0,100],'k--', lw=1)
    ax1.set_xlabel("Label (Fuzzy)"); ax1.set_ylabel("Prediksi")
    ax1.set_title("Heater: Actual vs Predicted")
    mae_h = mean_absolute_error(yh_test, ph)
    r2_h  = r2_score(yh_test, ph)
    ax1.text(5, 88, f"MAE={mae_h:.1f}%\nR\u00b2={r2_h:.3f}", fontsize=9,
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    ax2 = fig.add_subplot(gs[0, 1])
    ax2.scatter(yf_test[:500], pf[:500], alpha=0.3, s=10, color='steelblue')
    ax2.plot([0,100],[0,100],'k--', lw=1)
    ax2.set_xlabel("Label (Fuzzy)"); ax2.set_ylabel("Prediksi")
    ax2.set_title("Fan: Actual vs Predicted")
    mae_f = mean_absolute_error(yf_test, pf)
    r2_f  = r2_score(yf_test, pf)
    ax2.text(5, 88, f"MAE={mae_f:.1f}%\nR\u00b2={r2_f:.3f}", fontsize=9,
             bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

    ax3 = fig.add_subplot(gs[0, 2])
    err_h = ph - yh_test
    ax3.hist(err_h, bins=40, color='tomato', alpha=0.7, edgecolor='white')
    ax3.axvline(0, color='black', lw=1, ls='--')
    ax3.set_xlabel("Error (%)"); ax3.set_ylabel("Frekuensi")
    ax3.set_title("Distribusi Error Heater")

    ax4 = fig.add_subplot(gs[1, 0])
    tg = np.linspace(34, 42, 50)
    hg = np.linspace(25, 80, 50)
    TT, HH = np.meshgrid(tg, hg)
    ZH = np.zeros_like(TT)
    for i in range(TT.shape[0]):
        for j in range(TT.shape[1]):
            lab_h, _ = generate_label(TT[i,j], HH[i,j])
            ZH[i,j] = lab_h
    c4 = ax4.contourf(TT, HH, ZH, levels=20, cmap='RdYlGn_r')
    plt.colorbar(c4, ax=ax4)
    ax4.set_xlabel("Suhu (\u00b0C)"); ax4.set_ylabel("Kelembapan (%)")
    ax4.set_title("Heater Output Map (Fuzzy Label)")
    ax4.axvline(37.5, color='white', ls='--', lw=1, alpha=0.7)

    ax5 = fig.add_subplot(gs[1, 1])
    ZF = np.zeros_like(TT)
    for i in range(TT.shape[0]):
        for j in range(TT.shape[1]):
            _, lab_f = generate_label(TT[i,j], HH[i,j])
            ZF[i,j] = lab_f
    c5 = ax5.contourf(TT, HH, ZF, levels=20, cmap='RdYlGn')
    plt.colorbar(c5, ax=ax5)
    ax5.set_xlabel("Suhu (\u00b0C)"); ax5.set_ylabel("Kelembapan (%)")
    ax5.set_title("Fan Output Map (Fuzzy Label)")
    ax5.axvline(37.5, color='white', ls='--', lw=1, alpha=0.7)

    ax6 = fig.add_subplot(gs[1, 2])
    ax6.scatter(T_all[:2000], H_all[:2000], alpha=0.2, s=5, color='gray')
    ax6.axvline(37.5, color='red', ls='--', lw=1.5, label='Setpoint suhu')
    ax6.axhline(60, color='blue', ls='--', lw=1.5, label='Setpoint humi')
    ax6.set_xlabel("Suhu (\u00b0C)"); ax6.set_ylabel("Kelembapan (%)")
    ax6.set_title("Distribusi Dataset")
    ax6.legend(fontsize=8)

    plt.savefig("training_report.png", dpi=120, bbox_inches='tight')
    print("  -> training_report.png")
    plt.close()

# ============================================================
#  SAVE TRAINING REPORT
# ============================================================

def save_report(mt, mae_h, r2_h, mae_f, r2_f, cases, case_results, extra=""):
    ml = M[mt]["label"]
    lines = []
    lines.append("=" * 55)
    lines.append("  TRAINING REPORT - Inkubator ESP32")
    lines.append("=" * 55)
    lines.append(f"  Model     : {ml}")
    lines.append(f"  Dataset   : temperature_humidity_data.csv (Kaggle)")
    lines.append(f"  Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("-" * 55)
    lines.append("  HASIL TRAINING")
    lines.append("-" * 55)
    lines.append(f"  Heater - MAE = {mae_h:.2f}%   R\u00b2 = {r2_h:.4f}")
    lines.append(f"  Fan    - MAE = {mae_f:.2f}%   R\u00b2 = {r2_f:.4f}")
    if extra:
        lines.append("")
        lines.append(f"  {extra}")
    lines.append("")
    lines.append("-" * 55)
    lines.append("  SANITY CHECK")
    lines.append("-" * 55)
    lines.append(f"  {'Kondisi':<20} {'Suhu':>5} {'Humi':>5} {'Heater':>8} {'Fan':>6}")
    lines.append("  " + "-" * 48)
    for (t, h, label), (ht, fn) in zip(cases, case_results):
        lines.append(f"  {label:<20} {t:>5.1f} {h:>5.1f} {ht:>7.1f}% {fn:>5.1f}%")
    lines.append("")
    lines.append("=" * 55)
    lines.append("  File output:")
    lines.append(f"    {M[mt]['pfx']}_model.h")
    lines.append(f"    {M[mt]['pfx']}_control.h/.cpp")
    lines.append("    training_report.png")
    lines.append("    training_report.txt")
    lines.append("=" * 55)

    with open("training_report.txt", "w") as f:
        f.write("\n".join(lines))
    print("  -> training_report.txt")

# ============================================================
#  MAIN
# ============================================================

def main():
    mt = MODEL_TYPE
    if mt == "all":
        run_all_models()
        return
    meta = M[mt]
    pfx = meta["pfx"]

    print("=" * 55)
    print(f"  Inkubator {meta['label']} Trainer")
    print("=" * 55)

    # --- [1/5] Load ---
    print(f"\n[1/5] Membaca dataset...")
    if not os.path.exists(CSV_PATH):
        print(f"  ERROR: '{CSV_PATH}' tidak ditemukan!")
        sys.exit(1)
    df = pd.read_csv(CSV_PATH)
    print(f"  Total: {len(df):,} rows, columns: {df.columns.tolist()}")
    T_col, H_col = df.columns[1], df.columns[2]
    T_all, H_all = df[T_col].values, df[H_col].values
    print(f"  Suhu: {T_all.min():.1f}-{T_all.max():.1f}C  Humi: {H_all.min():.1f}-{H_all.max():.1f}%")

    # --- [2/5] Label ---
    print(f"\n[2/5] Generate fuzzy labels...")
    hl, fl = [], []
    for t, h in zip(T_all, H_all):
        ht, fn = generate_label(t, h)
        hl.append(ht); fl.append(fn)
    hl = np.array(hl, dtype=float)
    fl = np.array(fl, dtype=float)
    print(f"  Heater mean={hl.mean():.1f}%  Fan mean={fl.mean():.1f}%")

    # --- [3/5] Sampling ---
    print(f"\n[3/5] Siapkan data...")
    N = len(T_all)
    if SAMPLE_SIZE and SAMPLE_SIZE < N:
        idx = np.random.RandomState(RANDOM_SEED).choice(N, SAMPLE_SIZE, replace=False)
        T_s, H_s = T_all[idx], H_all[idx]
        Yh_s, Yf_s = hl[idx], fl[idx]
        print(f"  Sample {SAMPLE_SIZE:,} dari {N:,}")
    else:
        T_s, H_s, Yh_s, Yf_s = T_all, H_all, hl, fl
        print(f"  Pakai semua {N:,}")

    X = np.column_stack([T_s, H_s])
    needs_scale = mt in ("mlp", "svr")
    if mt == "mlp":
        scaler = MinMaxScaler()
        Xs = scaler.fit_transform(X)
    elif mt == "svr":
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
    else:
        scaler = None
        Xs = X.copy()

    X_tr, X_te, yh_tr, yh_te, yf_tr, yf_te = train_test_split(
        Xs, Yh_s, Yf_s, test_size=TEST_SIZE, random_state=RANDOM_SEED
    )
    print(f"  Train: {len(X_tr):,}  Test: {len(X_te):,}")

    # --- [4/5] Training ---
    print(f"\n[4/5] Training {meta['label']}...")

    def _fit(reg, X_tr, y_tr, X_te, y_te, **kw):
        m = reg(**kw)
        m.fit(X_tr, y_tr)
        p = m.predict(X_te)
        return m, p, mean_absolute_error(y_te, p), r2_score(y_te, p)

    cases = [
        (37.5, 60.0, "Ideal (ayam)"),
        (36.0, 35.0, "Dingin + kering"),
        (40.0, 38.0, "Panas + kering"),
        (38.0, 70.0, "Normal + lembap"),
        (42.0, 30.0, "OVERHEAT"),
        (35.0, 55.0, "Agak dingin"),
    ]

    extra = ""

    if mt in ("lr",):
        mh, ph, mae_h, r2_h = _fit(LinearRegression, X_tr, yh_tr, X_te, yh_te)
        mf, pf, mae_f, r2_f = _fit(LinearRegression, X_tr, yf_tr, X_te, yf_te)
        print(f"  Heater MAE={mae_h:.2f}% R\u00b2={r2_h:.4f}")
        print(f"  Fan    MAE={mae_f:.2f}% R\u00b2={r2_f:.4f}")

    elif mt in ("ridge",):
        mh, ph, mae_h, r2_h = _fit(Ridge, X_tr, yh_tr, X_te, yh_te, alpha=1.0, random_state=RANDOM_SEED)
        mf, pf, mae_f, r2_f = _fit(Ridge, X_tr, yf_tr, X_te, yf_te, alpha=1.0, random_state=RANDOM_SEED)
        print(f"  Heater MAE={mae_h:.2f}% R\u00b2={r2_h:.4f}")
        print(f"  Fan    MAE={mae_f:.2f}% R\u00b2={r2_f:.4f}")

    elif mt in ("lasso",):
        mh, ph, mae_h, r2_h = _fit(Lasso, X_tr, yh_tr, X_te, yh_te, alpha=0.01, random_state=RANDOM_SEED)
        mf, pf, mae_f, r2_f = _fit(Lasso, X_tr, yf_tr, X_te, yf_te, alpha=0.01, random_state=RANDOM_SEED)
        print(f"  Heater MAE={mae_h:.2f}% R\u00b2={r2_h:.4f}")
        print(f"  Fan    MAE={mae_f:.2f}% R\u00b2={r2_f:.4f}")

    elif mt in ("huber",):
        mh, ph, mae_h, r2_h = _fit(HuberRegressor, X_tr, yh_tr, X_te, yh_te, epsilon=1.35, max_iter=100)
        mf, pf, mae_f, r2_f = _fit(HuberRegressor, X_tr, yf_tr, X_te, yf_te, epsilon=1.35, max_iter=100)
        print(f"  Heater MAE={mae_h:.2f}% R\u00b2={r2_h:.4f}")
        print(f"  Fan    MAE={mae_f:.2f}% R\u00b2={r2_f:.4f}")

    elif mt in ("glm",):
        reg = {"poisson": PoissonRegressor, "gamma": GammaRegressor,
               "tweedie": lambda: TweedieRegressor(power=GLM_POWER)}[GLM_FAMILY]
        mh, ph, mae_h, r2_h = _fit(reg, X_tr, yh_tr, X_te, yh_te)
        mf, pf, mae_f, r2_f = _fit(reg, X_tr, yf_tr, X_te, yf_te)
        print(f"  Heater MAE={mae_h:.2f}% R\u00b2={r2_h:.4f}")
        print(f"  Fan    MAE={mae_f:.2f}% R\u00b2={r2_f:.4f}")

    elif mt in ("svr",):
        # SVR butuh scaling (dilakukan di atas)
        mh, ph, mae_h, r2_h = _fit(SVR, X_tr, yh_tr, X_te, yh_te, kernel=SVR_KERNEL, C=SVR_C, epsilon=SVR_EPSILON)
        mf, pf, mae_f, r2_f = _fit(SVR, X_tr, yf_tr, X_te, yf_te, kernel=SVR_KERNEL, C=SVR_C, epsilon=SVR_EPSILON)
        n_sv = len(mh.support_vectors_) + len(mf.support_vectors_)
        print(f"  Heater MAE={mae_h:.2f}% R\u00b2={r2_h:.4f}")
        print(f"  Fan    MAE={mae_f:.2f}% R\u00b2={r2_f:.4f}")
        extra += f"SVR kernel={SVR_KERNEL}, total SV={n_sv}"
        if SVR_KERNEL == "rbf":
            extra += " (butuh math.h, tidak recommended)"

    elif mt in ("rf",):
        mh, ph, mae_h, r2_h = _fit(RandomForestRegressor, X_tr, yh_tr, X_te, yh_te,
            n_estimators=EN_N_ESTIMATORS, max_depth=EN_MAX_DEPTH,
            min_samples_leaf=EN_MIN_LEAF, random_state=RANDOM_SEED)
        mf, pf, mae_f, r2_f = _fit(RandomForestRegressor, X_tr, yf_tr, X_te, yf_te,
            n_estimators=EN_N_ESTIMATORS, max_depth=EN_MAX_DEPTH,
            min_samples_leaf=EN_MIN_LEAF, random_state=RANDOM_SEED)
        print(f"  Heater MAE={mae_h:.2f}% R\u00b2={r2_h:.4f}")
        print(f"  Fan    MAE={mae_f:.2f}% R\u00b2={r2_f:.4f}")

    elif mt in ("et",):
        mh, ph, mae_h, r2_h = _fit(ExtraTreesRegressor, X_tr, yh_tr, X_te, yh_te,
            n_estimators=EN_N_ESTIMATORS, max_depth=EN_MAX_DEPTH,
            min_samples_leaf=EN_MIN_LEAF, random_state=RANDOM_SEED)
        mf, pf, mae_f, r2_f = _fit(ExtraTreesRegressor, X_tr, yf_tr, X_te, yf_te,
            n_estimators=EN_N_ESTIMATORS, max_depth=EN_MAX_DEPTH,
            min_samples_leaf=EN_MIN_LEAF, random_state=RANDOM_SEED)
        print(f"  Heater MAE={mae_h:.2f}% R\u00b2={r2_h:.4f}")
        print(f"  Fan    MAE={mae_f:.2f}% R\u00b2={r2_f:.4f}")

    elif mt in ("gb",):
        mh, ph, mae_h, r2_h = _fit(GradientBoostingRegressor, X_tr, yh_tr, X_te, yh_te,
            n_estimators=EN_N_ESTIMATORS, max_depth=EN_MAX_DEPTH,
            min_samples_leaf=EN_MIN_LEAF, learning_rate=EN_LR, random_state=RANDOM_SEED)
        mf, pf, mae_f, r2_f = _fit(GradientBoostingRegressor, X_tr, yf_tr, X_te, yf_te,
            n_estimators=EN_N_ESTIMATORS, max_depth=EN_MAX_DEPTH,
            min_samples_leaf=EN_MIN_LEAF, learning_rate=EN_LR, random_state=RANDOM_SEED)
        print(f"  Heater MAE={mae_h:.2f}% R\u00b2={r2_h:.4f}")
        print(f"  Fan    MAE={mae_f:.2f}% R\u00b2={r2_f:.4f}")

    elif mt in ("ada",):
        mh, ph, mae_h, r2_h = _fit(AdaBoostRegressor, X_tr, yh_tr, X_te, yh_te,
            n_estimators=EN_N_ESTIMATORS, learning_rate=EN_LR, loss='linear', random_state=RANDOM_SEED)
        mf, pf, mae_f, r2_f = _fit(AdaBoostRegressor, X_tr, yf_tr, X_te, yf_te,
            n_estimators=EN_N_ESTIMATORS, learning_rate=EN_LR, loss='linear', random_state=RANDOM_SEED)
        print(f"  Heater MAE={mae_h:.2f}% R\u00b2={r2_h:.4f}")
        print(f"  Fan    MAE={mae_f:.2f}% R\u00b2={r2_f:.4f}")

    elif mt in ("dt",):
        mh, ph, mae_h, r2_h = _fit(DecisionTreeRegressor, X_tr, yh_tr, X_te, yh_te,
            max_depth=DT_MAX_DEPTH, min_samples_leaf=DT_MIN_LEAF, random_state=RANDOM_SEED)
        mf, pf, mae_f, r2_f = _fit(DecisionTreeRegressor, X_tr, yf_tr, X_te, yf_te,
            max_depth=DT_MAX_DEPTH, min_samples_leaf=DT_MIN_LEAF, random_state=RANDOM_SEED)
        print(f"  Heater MAE={mae_h:.2f}% R\u00b2={r2_h:.4f}  depth={mh.get_depth()} leaf={mh.get_n_leaves()}")
        print(f"  Fan    MAE={mae_f:.2f}% R\u00b2={r2_f:.4f}  depth={mf.get_depth()} leaf={mf.get_n_leaves()}")

    elif mt in ("mlp",):
        mh, ph, mae_h, r2_h = _fit(MLPRegressor, X_tr, yh_tr, X_te, yh_te,
            hidden_layer_sizes=HIDDEN_LAYERS, activation='relu', solver='adam',
            max_iter=MAX_ITER, random_state=RANDOM_SEED,
            early_stopping=True, validation_fraction=0.1, n_iter_no_change=30)
        mf, pf, mae_f, r2_f = _fit(MLPRegressor, X_tr, yf_tr, X_te, yf_te,
            hidden_layer_sizes=HIDDEN_LAYERS, activation='relu', solver='adam',
            max_iter=MAX_ITER, random_state=RANDOM_SEED,
            early_stopping=True, validation_fraction=0.1, n_iter_no_change=30)
        print(f"  Heater MAE={mae_h:.2f}% R\u00b2={r2_h:.4f}  iter={mh.n_iter_}")
        print(f"  Fan    MAE={mae_f:.2f}% R\u00b2={r2_f:.4f}  iter={mf.n_iter_}")

    else:
        print(f"  ERROR: MODEL_TYPE='{mt}' tidak dikenal")
        sys.exit(1)

    # --- Sanity check ---
    print("\n  Sanity check:")
    print(f"  {'Kondisi':<20} {'Suhu':>5} {'Humi':>5} {'Heater':>8} {'Fan':>6}")
    print("  " + "-"*48)
    case_results = []
    for t, h, label in cases:
        xi = scaler.transform([[t, h]]) if needs_scale else [[t, h]]
        ht = float(np.clip(mh.predict(xi)[0], 0, 100))
        fn = float(np.clip(mf.predict(xi)[0], 0, 100))
        if t > 41.5: ht = 0; fn = 100
        if t < 34.0: ht = 100; fn = 10
        case_results.append((ht, fn))
        print(f"  {label:<20} {t:>5.1f} {h:>5.1f} {ht:>7.1f}% {fn:>5.1f}%")

    # --- [5/5] Export ---
    print(f"\n[5/5] Export...")

    if mt in ("lr", "ridge", "lasso", "huber", "glm"):
        extra = export_linear(mh, mf, mt)
    elif mt == "svr" and SVR_KERNEL == "rbf":
        print("  SVR rbf — export tidak didukung (butuh SV + exp())")
    elif mt == "svr":
        extra = export_linear(mh, mf, mt)
    elif mt in ("rf", "et", "gb", "ada"):
        extra = export_ensemble(mh, mf, mt)
    elif mt == "dt":
        extra = export_dt(mh, mf)
    elif mt == "mlp":
        extra = export_nn(mh, mf, scaler)

    # --- Plot & Report ---
    print("  Plot...")
    plot_report(yh_te, ph, yf_te, pf, T_all, H_all, hl, fl, mt)
    save_report(mt, mae_h, r2_h, mae_f, r2_f, cases, case_results, extra)

    print("\n" + "=" * 55)
    print(f"  SELESAI! {meta['label']}")
    print("=" * 55)
    print(f"  Heater MAE={mae_h:.2f}%  R\u00b2={r2_h:.4f}")
    print(f"  Fan    MAE={mae_f:.2f}%  R\u00b2={r2_f:.4f}")
    print(f"\n  File:")
    print(f"    {pfx}_model.h")
    print(f"    {pfx}_control.h/.cpp")
    print("    training_report.png")
    print("    training_report.txt")
    print("=" * 55)

# ============================================================
#  RUN ALL MODELS — comparison summary
# ============================================================

def run_all_models():
    """Train semua model, bandingkan, simpan ke model_comparison.txt."""
    import time
    results = []
    models = ["lr", "ridge", "lasso", "huber", "glm", "svr", "rf", "et", "gb", "ada", "dt", "mlp"]

    print("=" * 60)
    print("  TRAINING ALL MODELS — Comparison")
    print("=" * 60)

    # Load data sekali
    print("\n[1/5] Loading dataset...")
    if not os.path.exists(CSV_PATH):
        print(f"  ERROR: '{CSV_PATH}' tidak ditemukan!")
        return
    df = pd.read_csv(CSV_PATH)
    T_all, H_all = df[df.columns[1]].values, df[df.columns[2]].values

    print("[2/5] Generating fuzzy labels...")
    hl, fl = [], []
    for t, h in zip(T_all, H_all):
        ht, fn = generate_label(t, h)
        hl.append(ht); fl.append(fn)
    hl = np.array(hl, dtype=float)
    fl = np.array(fl, dtype=float)

    print("[3/5] Sampling data...")
    N = len(T_all)
    if SAMPLE_SIZE and SAMPLE_SIZE < N:
        idx = np.random.RandomState(RANDOM_SEED).choice(N, SAMPLE_SIZE, replace=False)
        T_s, H_s = T_all[idx], H_all[idx]
        Yh_s, Yf_s = hl[idx], fl[idx]
    else:
        T_s, H_s, Yh_s, Yf_s = T_all, H_all, hl, fl

    X_raw = np.column_stack([T_s, H_s])

    print(f"[4/5] Training {len(models)} models...\n")

    for mt in models:
        print(f"  [{mt}] ", end="", flush=True)
        t0 = time.time()

        # Scaling
        if mt in ("mlp",):
            scaler = MinMaxScaler()
            Xs = scaler.fit_transform(X_raw)
        elif mt in ("svr",):
            scaler = StandardScaler()
            Xs = scaler.fit_transform(X_raw)
        else:
            scaler = None
            Xs = X_raw.copy()

        X_tr, X_te, yh_tr, yh_te, yf_tr, yf_te = train_test_split(
            Xs, Yh_s, Yf_s, test_size=TEST_SIZE, random_state=RANDOM_SEED)

        try:
            if mt == "lr":
                mh = LinearRegression().fit(X_tr, yh_tr)
                mf = LinearRegression().fit(X_tr, yf_tr)
            elif mt == "ridge":
                mh = Ridge(alpha=1.0, random_state=RANDOM_SEED).fit(X_tr, yh_tr)
                mf = Ridge(alpha=1.0, random_state=RANDOM_SEED).fit(X_tr, yf_tr)
            elif mt == "lasso":
                mh = Lasso(alpha=0.01, random_state=RANDOM_SEED).fit(X_tr, yh_tr)
                mf = Lasso(alpha=0.01, random_state=RANDOM_SEED).fit(X_tr, yf_tr)
            elif mt == "huber":
                mh = HuberRegressor(epsilon=1.35, max_iter=100).fit(X_tr, yh_tr)
                mf = HuberRegressor(epsilon=1.35, max_iter=100).fit(X_tr, yf_tr)
            elif mt == "glm":
                reg = {"poisson": PoissonRegressor, "gamma": GammaRegressor,
                       "tweedie": lambda: TweedieRegressor(power=GLM_POWER)}[GLM_FAMILY]
                mh = reg().fit(X_tr, yh_tr)
                mf = reg().fit(X_tr, yf_tr)
            elif mt == "svr":
                mh = SVR(kernel=SVR_KERNEL, C=SVR_C, epsilon=SVR_EPSILON).fit(X_tr, yh_tr)
                mf = SVR(kernel=SVR_KERNEL, C=SVR_C, epsilon=SVR_EPSILON).fit(X_tr, yf_tr)
            elif mt == "rf":
                mh = RandomForestRegressor(n_estimators=EN_N_ESTIMATORS, max_depth=EN_MAX_DEPTH,
                    min_samples_leaf=EN_MIN_LEAF, random_state=RANDOM_SEED).fit(X_tr, yh_tr)
                mf = RandomForestRegressor(n_estimators=EN_N_ESTIMATORS, max_depth=EN_MAX_DEPTH,
                    min_samples_leaf=EN_MIN_LEAF, random_state=RANDOM_SEED).fit(X_tr, yf_tr)
            elif mt == "et":
                mh = ExtraTreesRegressor(n_estimators=EN_N_ESTIMATORS, max_depth=EN_MAX_DEPTH,
                    min_samples_leaf=EN_MIN_LEAF, random_state=RANDOM_SEED).fit(X_tr, yh_tr)
                mf = ExtraTreesRegressor(n_estimators=EN_N_ESTIMATORS, max_depth=EN_MAX_DEPTH,
                    min_samples_leaf=EN_MIN_LEAF, random_state=RANDOM_SEED).fit(X_tr, yf_tr)
            elif mt == "gb":
                mh = GradientBoostingRegressor(n_estimators=EN_N_ESTIMATORS, max_depth=EN_MAX_DEPTH,
                    min_samples_leaf=EN_MIN_LEAF, learning_rate=EN_LR, random_state=RANDOM_SEED,
                    subsample=0.8).fit(X_tr, yh_tr)
                mf = GradientBoostingRegressor(n_estimators=EN_N_ESTIMATORS, max_depth=EN_MAX_DEPTH,
                    min_samples_leaf=EN_MIN_LEAF, learning_rate=EN_LR, random_state=RANDOM_SEED,
                    subsample=0.8).fit(X_tr, yf_tr)
            elif mt == "ada":
                mh = AdaBoostRegressor(n_estimators=EN_N_ESTIMATORS, learning_rate=EN_LR,
                    loss='linear', random_state=RANDOM_SEED).fit(X_tr, yh_tr)
                mf = AdaBoostRegressor(n_estimators=EN_N_ESTIMATORS, learning_rate=EN_LR,
                    loss='linear', random_state=RANDOM_SEED).fit(X_tr, yf_tr)
            elif mt == "dt":
                mh = DecisionTreeRegressor(max_depth=DT_MAX_DEPTH, min_samples_leaf=DT_MIN_LEAF,
                    random_state=RANDOM_SEED).fit(X_tr, yh_tr)
                mf = DecisionTreeRegressor(max_depth=DT_MAX_DEPTH, min_samples_leaf=DT_MIN_LEAF,
                    random_state=RANDOM_SEED).fit(X_tr, yf_tr)
            elif mt == "mlp":
                mh = MLPRegressor(hidden_layer_sizes=HIDDEN_LAYERS, activation='relu', solver='adam',
                    max_iter=MAX_ITER, random_state=RANDOM_SEED, early_stopping=True,
                    validation_fraction=0.1, n_iter_no_change=30).fit(X_tr, yh_tr)
                mf = MLPRegressor(hidden_layer_sizes=HIDDEN_LAYERS, activation='relu', solver='adam',
                    max_iter=MAX_ITER, random_state=RANDOM_SEED, early_stopping=True,
                    validation_fraction=0.1, n_iter_no_change=30).fit(X_tr, yf_tr)

            ph = mh.predict(X_te); pf = mf.predict(X_te)
            mae_h = mean_absolute_error(yh_te, ph)
            r2_h = r2_score(yh_te, ph)
            mae_f = mean_absolute_error(yf_te, pf)
            r2_f = r2_score(yf_te, pf)

            # Estimate resource
            if mt in ("lr", "ridge", "lasso", "huber", "glm"):
                ram = "12 B"
                flash = "<0.1 KB"
            elif mt == "svr":
                if SVR_KERNEL == "linear":
                    ram, flash = "12 B", "<0.1 KB"
                else:
                    n_sv = len(mh.support_vectors_) + len(mf.support_vectors_)
                    ram, flash = f"~{n_sv*16}B", "~2 KB"
            elif mt in ("rf", "et", "gb", "ada"):
                est = mh.estimators_
                # GB: 2D array (n_estimators, 1), RF/ET/Ada: list
                if hasattr(est, 'shape'):
                    est_h = [e[0] for e in est]
                else:
                    est_h = list(est)
                est = mf.estimators_
                if hasattr(est, 'shape'):
                    est_f = [e[0] for e in est]
                else:
                    est_f = list(est)
                total_n = sum(e.tree_.node_count for e in est_h) + sum(e.tree_.node_count for e in est_f)
                ram, flash = "0", f"~{total_n * 8}B"
            elif mt == "dt":
                total_n = mh.tree_.node_count + mf.tree_.node_count
                ram, flash = "0", f"~{total_n * 8}B"
            elif mt == "mlp":
                tp = sum(w.size for w in mh.coefs_) + sum(b.size for b in mh.intercepts_)
                tp += sum(w.size for w in mf.coefs_) + sum(b.size for b in mf.intercepts_)
                ram, flash = f"~{tp*4}B", f"~{tp*4}B"

            dt = time.time() - t0
            results.append((mt, M[mt]["label"], mae_h, r2_h, mae_f, r2_f, ram, flash, dt))
            print(f"MAE_h={mae_h:.2f}% R2_h={r2_h:.4f}  ({dt:.1f}s)")

        except Exception as e:
            print(f"FAILED: {e}")
            results.append((mt, M[mt]["label"], 99, 0, 99, 0, "err", "err", 0))

    # --- Write comparison ---
    print(f"\n[5/5] Writing model_comparison.txt...")

    lines = []
    lines.append("=" * 80)
    lines.append("  MODEL COMPARISON — Inkubator ESP32")
    lines.append("  Dataset: temperature_humidity_data.csv (Kaggle)")
    lines.append(f"  Sample : {SAMPLE_SIZE or N:,} rows")
    lines.append(f"  Date   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"{'Model':<8} {'Name':<22} {'MAE_h%':<8} {'R2_h':<8} {'MAE_f%':<8} {'R2_f':<8} {'RAM':<10} {'Flash':<12} {'Time':<8}")
    lines.append("-" * 80)
    for mt, name, mae_h, r2_h, mae_f, r2_f, ram, flash, dt in results:
        lines.append(f"{mt:<8} {name:<22} {mae_h:<8.2f} {r2_h:<8.4f} {mae_f:<8.2f} {r2_f:<8.4f} {ram:<10} {flash:<12} {dt:<8.1f}")
    lines.append("-" * 80)
    lines.append("")

    # Rank by average R2
    ranked = sorted([r for r in results if r[3] != 0], key=lambda r: (r[3] + r[5]) / 2, reverse=True)
    lines.append("  RANKING (by avg R2)")
    lines.append("  " + "-" * 50)
    for i, r in enumerate(ranked, 1):
        avg_r2 = (r[3] + r[5]) / 2
        lines.append(f"  {i}. {r[0]:<6} {r[1]:<22} avg R2={avg_r2:.4f}  MAE_h={r[2]:.2f}%  MAE_f={r[4]:.2f}%  RAM={r[6]}  Flash={r[7]}")
    lines.append("")
    lines.append("=" * 80)
    lines.append("  NOTES")
    lines.append("=" * 80)
    lines.append("  - All labels generated from fuzzy rules (9 rules: 3 temp x 3 humidity)")
    lines.append("  - R2 ~ 1.0 = almost perfect imitation of fuzzy logic")
    lines.append(f"  - DT config: max_depth={DT_MAX_DEPTH}, min_samples_leaf={DT_MIN_LEAF}")
    lines.append(f"  - Ensemble config: n_estimators={EN_N_ESTIMATORS}, max_depth={EN_MAX_DEPTH}")
    lines.append(f"  - MLP config: hidden_layers={HIDDEN_LAYERS}, max_iter={MAX_ITER}")
    lines.append("  - GPR excluded: O(n^3) training, needs full dataset in RAM for inference")
    lines.append("  - For ESP32: DT or RF recommended (0 RAM, pure if-else, no math.h needed)")
    lines.append("=" * 80)

    with open("model_comparison.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("  -> model_comparison.txt")

    # Also print to console
    print("\n" + "\n".join(lines))
    print(f"\n  Done! {len(results)} models compared.")


if __name__ == "__main__":
    main()
