import os
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Folder containing moderation_analysis_*.xlsx files
ROOT = Path(__file__).resolve().parents[4]
base_dir = ROOT / "output" / "repeated_anova" / "lmm_moderation"
input_dir = base_dir
output_dir = os.path.join(base_dir, 'moderation_plots')
os.makedirs(output_dir, exist_ok=True)

# Simple-slope plot

def plot_simple_slope(df_slopes, var, out_dir):
    # Create a bar plot of simple-slope coefficients
    level_col = 'Moderator_Level' if 'Moderator_Level' in df_slopes.columns else 'Livello_Moderatore'
    plt.figure(figsize=(5,4))
    sns.barplot(
        data=df_slopes,
        x=level_col, y='coef',
        hue=level_col,
        palette='Set2',
        errorbar=None,
        legend=False,
    )
    plt.axhline(0, color='gray', linestyle='--')
    plt.title(f'Simple Slope: {var}')
    plt.ylabel('Slope (coef)')
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f'simple_slope_{var}.png'), dpi=300)
    plt.close()

# Post-hoc plot

def plot_posthoc(df_posthoc, var, out_dir):
    # Bar plot of means for compared groups
    for idx, row in df_posthoc.iterrows():
        if 'p-corr' in row and row['p-corr'] < 0.05:
            group1 = row['A'] if 'A' in row else row.get('Group1', None)
            group2 = row['B'] if 'B' in row else row.get('Group2', None)
            if group1 and group2:
                plt.figure(figsize=(4,3))
                sns.barplot(x=['Group1','Group2'], y=[row['mean(A)'], row['mean(B)']], palette='Set1')
                plt.title(f'Post-hoc: {var} ({group1} vs {group2})')
                plt.ylabel('Mean')
                plt.tight_layout()
                plt.savefig(os.path.join(out_dir, f'posthoc_{var}_{group1}_vs_{group2}.png'), dpi=300)
                plt.close()

# Loop over all moderation_analysis_*.xlsx files
for fname in os.listdir(input_dir):
    if fname.startswith('moderation_analysis_') and fname.endswith('.xlsx'):
        fpath = os.path.join(input_dir, fname)
        xls = pd.ExcelFile(fpath)
        var = fname.replace('moderation_analysis_','').replace('.xlsx','')
        # Simple slopes
        if 'SIMPLE_SLOPES' in xls.sheet_names:
            df_slopes = pd.read_excel(xls, sheet_name='SIMPLE_SLOPES')
            # Significant rows only
            df_slopes_sig = df_slopes[df_slopes['pval'] < 0.05]
            if not df_slopes_sig.empty:
                plot_simple_slope(df_slopes_sig, var, output_dir)
                print(f'Created simple slope plot for {var}')
        # Post-hoc
        if 'POST-HOC' in xls.sheet_names:
            df_posthoc = pd.read_excel(xls, sheet_name='POST-HOC')
            plot_posthoc(df_posthoc, var, output_dir)
            print(f'Created post-hoc plot for {var}')

print('Done! Moderation plots saved to', output_dir)
