import pandas as pd
import os
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import ttest_rel
from pathlib import Path
import sys

def kaiser_rule(pca):
    return [i for i, eig in enumerate(pca.explained_variance_) if eig > 1]

def get_pc_names(indices):
    return [f'PC{i+1}' for i in indices]

def plot_scree(pca, title, out_path):
    plt.figure(figsize=(8, 5))
    plt.plot(np.arange(1, len(pca.explained_variance_)+1), pca.explained_variance_, marker='o')
    plt.axhline(1, color='red', linestyle='--', label='Kaiser (eigenvalue=1)')
    plt.title(f'Scree Plot - {title}')
    plt.xlabel('Component')
    plt.ylabel('Eigenvalue')
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()

# --- CONFIG ---
ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "output" / "pca"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
dir_base = str(OUTPUT_DIR)
sys.path.append(str(ROOT / "analysis" / "descriptives"))
from add_composites import build_composite_dataframe  # noqa: E402

df = build_composite_dataframe()

# --- PLANNING ---
planning_pre_cols = [
    'PLANNING_TR_PRE_ln', 'PLANNING_span_PRE', 'PLANNING_trial_PRE', 'PLANNING_ACC_PRE',
    'PLANNING_OST_PRE', 'PLANNING_PERC_PRE', 'planning_mattonelle_diff_pre'
]
planning_post_cols = [
    'PLANNING_TR_POST_ln', 'PLANNING_span_POST', 'PLANNING_trial_POST', 'PLANNING_ACC_POST',
    'PLANNING_OST_POST', 'PLANNING_PERC_POST', 'planning_mattonelle_diff_post'
]
all_planning_cols = planning_pre_cols + planning_post_cols
df_planning_clean = df.dropna(subset=all_planning_cols)
X_planning_pre = df_planning_clean[planning_pre_cols]
X_planning_post = df_planning_clean[planning_post_cols]

scaler_planning = StandardScaler().fit(X_planning_pre)
X_planning_pre_std = scaler_planning.transform(X_planning_pre)
pca_planning = PCA()
pca_planning.fit(X_planning_pre_std)
loadings_planning = pd.DataFrame(pca_planning.components_.T, index=planning_pre_cols, columns=[f'PC{i+1}' for i in range(len(planning_pre_cols))])
scores_planning_pre = pd.DataFrame(pca_planning.transform(X_planning_pre_std), columns=[f'PC{i+1}' for i in range(len(planning_pre_cols))], index=X_planning_pre.index)
X_planning_post_renamed = X_planning_post.copy(); X_planning_post_renamed.columns = planning_pre_cols
X_planning_post_std = scaler_planning.transform(X_planning_post_renamed)
scores_planning_post = pd.DataFrame(pca_planning.transform(X_planning_post_std), columns=[f'PC{i+1}' for i in range(len(planning_pre_cols))], index=X_planning_post.index)
loadings_planning.to_excel(os.path.join(dir_base, 'loadings_planning_pre.xlsx'))
scores_planning_pre.to_excel(os.path.join(dir_base, 'scores_planning_pre.xlsx'))
scores_planning_post.to_excel(os.path.join(dir_base, 'scores_planning_post.xlsx'))
if 'PC1' in scores_planning_pre.columns and 'PC1' in scores_planning_post.columns:
    t_stat, p_val = ttest_rel(scores_planning_pre['PC1'], scores_planning_post['PC1'])
    print(f"T-test PC1 planning pre vs post: t={t_stat:.3f}, p={p_val:.3g}")

kaiser_idx_planning = kaiser_rule(pca_planning)
kaiser_pc_planning = get_pc_names(kaiser_idx_planning)
plot_scree(pca_planning, 'Planning', os.path.join(dir_base, 'scree_planning.png'))
if kaiser_pc_planning:
    scores_planning_pre_filt = scores_planning_pre[kaiser_pc_planning]
    scores_planning_post_filt = scores_planning_post[kaiser_pc_planning]
    scores_planning_pre_filt.to_excel(os.path.join(dir_base, 'scores_planning_pre_filt.xlsx'))
    scores_planning_post_filt.to_excel(os.path.join(dir_base, 'scores_planning_post_filt.xlsx'))

# --- PWM ---
pwm_pre_cols = [
    'PWM_ TR_PRE_ln', 'PWM_ TRIAL_PRE', 'PWM_ ACC_PRE', 'PWM_ OST_PRE', 'PWM_ PERC_PRE', 'pwm_mattonelle_diff_pre'
]
pwm_post_cols = [
    'PWM_ TR_POST_ln', 'PWM_ TRIAL_POST', 'PWM_ ACC_POST', 'PWM_ OST_POST', 'PWM_ PERC_POST', 'pwm_mattonelle_diff_post'
]
all_pwm_cols = pwm_pre_cols + pwm_post_cols
df_pwm_clean = df.dropna(subset=all_pwm_cols)
X_pwm_pre = df_pwm_clean[pwm_pre_cols]
X_pwm_post = df_pwm_clean[pwm_post_cols]
scaler_pwm = StandardScaler().fit(X_pwm_pre)
X_pwm_pre_std = scaler_pwm.transform(X_pwm_pre)
pca_pwm = PCA()
pca_pwm.fit(X_pwm_pre_std)
loadings_pwm = pd.DataFrame(pca_pwm.components_.T, index=pwm_pre_cols, columns=[f'PC{i+1}' for i in range(len(pwm_pre_cols))])
scores_pwm_pre = pd.DataFrame(pca_pwm.transform(X_pwm_pre_std), columns=[f'PC{i+1}' for i in range(len(pwm_pre_cols))], index=X_pwm_pre.index)
X_pwm_post_renamed = X_pwm_post.copy(); X_pwm_post_renamed.columns = pwm_pre_cols
X_pwm_post_std = scaler_pwm.transform(X_pwm_post_renamed)
scores_pwm_post = pd.DataFrame(pca_pwm.transform(X_pwm_post_std), columns=[f'PC{i+1}' for i in range(len(pwm_pre_cols))], index=X_pwm_post.index)
loadings_pwm.to_excel(os.path.join(dir_base, 'loadings_pwm_pre.xlsx'))
scores_pwm_pre.to_excel(os.path.join(dir_base, 'scores_pwm_pre.xlsx'))
scores_pwm_post.to_excel(os.path.join(dir_base, 'scores_pwm_post.xlsx'))
if 'PC1' in scores_pwm_pre.columns and 'PC1' in scores_pwm_post.columns:
    t_stat, p_val = ttest_rel(scores_pwm_pre['PC1'], scores_pwm_post['PC1'])
    print(f"T-test PC1 pwm pre vs post: t={t_stat:.3f}, p={p_val:.3g}")

kaiser_idx_pwm = kaiser_rule(pca_pwm)
kaiser_pc_pwm = get_pc_names(kaiser_idx_pwm)
plot_scree(pca_pwm, 'PWM', os.path.join(dir_base, 'scree_pwm.png'))
if kaiser_pc_pwm:
    scores_pwm_pre_filt = scores_pwm_pre[kaiser_pc_pwm]
    scores_pwm_post_filt = scores_pwm_post[kaiser_pc_pwm]
    scores_pwm_pre_filt.to_excel(os.path.join(dir_base, 'scores_pwm_pre_filt.xlsx'))
    scores_pwm_post_filt.to_excel(os.path.join(dir_base, 'scores_pwm_post_filt.xlsx'))

# --- WM ---
wm_pre_cols = ['WM_span_PRE', 'WM_trial_PRE', 'WM_acc_PRE']
wm_post_cols = ['WM_span_POST', 'WM_trial_POST', 'WM_acc_POST']
all_wm_cols = wm_pre_cols + wm_post_cols
df_wm_clean = df.dropna(subset=all_wm_cols)
X_wm_pre = df_wm_clean[wm_pre_cols]
X_wm_post = df_wm_clean[wm_post_cols]
scaler_wm = StandardScaler().fit(X_wm_pre)
X_wm_pre_std = scaler_wm.transform(X_wm_pre)
pca_wm = PCA()
pca_wm.fit(X_wm_pre_std)
loadings_wm = pd.DataFrame(pca_wm.components_.T, index=wm_pre_cols, columns=[f'PC{i+1}' for i in range(len(wm_pre_cols))])
scores_wm_pre = pd.DataFrame(pca_wm.transform(X_wm_pre_std), columns=[f'PC{i+1}' for i in range(len(wm_pre_cols))], index=X_wm_pre.index)
X_wm_post_renamed = X_wm_post.copy(); X_wm_post_renamed.columns = wm_pre_cols
X_wm_post_std = scaler_wm.transform(X_wm_post_renamed)
scores_wm_post = pd.DataFrame(pca_wm.transform(X_wm_post_std), columns=[f'PC{i+1}' for i in range(len(wm_pre_cols))], index=X_wm_post.index)
loadings_wm.to_excel(os.path.join(dir_base, 'loadings_wm_pre.xlsx'))
scores_wm_pre.to_excel(os.path.join(dir_base, 'scores_wm_pre.xlsx'))
scores_wm_post.to_excel(os.path.join(dir_base, 'scores_wm_post.xlsx'))
if 'PC1' in scores_wm_pre.columns and 'PC1' in scores_wm_post.columns:
    t_stat, p_val = ttest_rel(scores_wm_pre['PC1'], scores_wm_post['PC1'])
    print(f"T-test PC1 wm pre vs post: t={t_stat:.3f}, p={p_val:.3g}")

kaiser_idx_wm = kaiser_rule(pca_wm)
kaiser_pc_wm = get_pc_names(kaiser_idx_wm)
plot_scree(pca_wm, 'WM', os.path.join(dir_base, 'scree_wm.png'))
if kaiser_pc_wm:
    scores_wm_pre_filt = scores_wm_pre[kaiser_pc_wm]
    scores_wm_post_filt = scores_wm_post[kaiser_pc_wm]
    scores_wm_pre_filt.to_excel(os.path.join(dir_base, 'scores_wm_pre_filt.xlsx'))
    scores_wm_post_filt.to_excel(os.path.join(dir_base, 'scores_wm_post_filt.xlsx'))

# --- UNISCI I PUNTEGGI PC FILTRATI IN UN UNICO DATAFRAME CON ID ORIGINALE ---
# Use the in-memory analysis dataset and get the ID column
composite_db = build_composite_dataframe()
if 'ID' in composite_db.columns:
    id_col = 'ID'
else:
    id_col = composite_db.columns[0]

# Function to realign scores to true IDs

def align_scores_with_id(scores, db, id_col):
    # If the score index is numeric, use it positionally to retrieve IDs from the database
    if not scores.index.equals(db[id_col]):
        # Try positional realignment
        scores = scores.copy()
        scores[id_col] = db[id_col].values[:len(scores)]
        scores = scores.set_index(id_col)
    return scores

# Load the filtered factor scores
scores_planning_pre = pd.read_excel(os.path.join(dir_base, 'scores_planning_pre_filt.xlsx'), index_col=0)
scores_planning_post = pd.read_excel(os.path.join(dir_base, 'scores_planning_post_filt.xlsx'), index_col=0)
scores_pwm_pre = pd.read_excel(os.path.join(dir_base, 'scores_pwm_pre_filt.xlsx'), index_col=0)
scores_pwm_post = pd.read_excel(os.path.join(dir_base, 'scores_pwm_post_filt.xlsx'), index_col=0)
scores_wm_pre = pd.read_excel(os.path.join(dir_base, 'scores_wm_pre_filt.xlsx'), index_col=0)
scores_wm_post = pd.read_excel(os.path.join(dir_base, 'scores_wm_post_filt.xlsx'), index_col=0)

# Riallinea all i punteggi alle ID originali
db_id = composite_db[[id_col]].reset_index(drop=True)
scores_planning_pre = align_scores_with_id(scores_planning_pre, db_id, id_col)
scores_planning_post = align_scores_with_id(scores_planning_post, db_id, id_col)
scores_pwm_pre = align_scores_with_id(scores_pwm_pre, db_id, id_col)
scores_pwm_post = align_scores_with_id(scores_pwm_post, db_id, id_col)
scores_wm_pre = align_scores_with_id(scores_wm_pre, db_id, id_col)
scores_wm_post = align_scores_with_id(scores_wm_post, db_id, id_col)

# Add suffixes to distinguish pre/post time point and domain
scores_planning_pre = scores_planning_pre.add_suffix('_planning_pre')
scores_planning_post = scores_planning_post.add_suffix('_planning_post')
scores_pwm_pre = scores_pwm_pre.add_suffix('_pwm_pre')
scores_pwm_post = scores_pwm_post.add_suffix('_pwm_post')
scores_wm_pre = scores_wm_pre.add_suffix('_wm_pre')
scores_wm_post = scores_wm_post.add_suffix('_wm_post')

# Join by index, keeping only subjects present in all score tables
df_scores = pd.concat([
    scores_planning_pre, scores_planning_post,
    scores_pwm_pre, scores_pwm_post,
    scores_wm_pre, scores_wm_post
], axis=1, join='inner')

# Mantieni solo gli ID originali
common_ids = df_scores.index.intersection(composite_db[id_col])
df_scores = df_scores.loc[common_ids]
# Add variables from the composite database
final_df = df_scores.join(composite_db.set_index(id_col), how='left')

# Save the unified dataframe for LMM
out_scores_path = os.path.join(dir_base, 'unified_pca_scores.xlsx')
final_df.to_excel(out_scores_path)
print(f"Unified PCA-score dataframe saved to: {out_scores_path}")
