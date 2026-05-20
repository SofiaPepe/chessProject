import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Cartella dove si trovano i file Analisi_Mod_*.xlsx
base_dir = os.path.dirname(os.path.abspath(__file__))
input_dir = base_dir
output_dir = os.path.join(base_dir, 'grafici_moderazione')
os.makedirs(output_dir, exist_ok=True)

# Funzione per grafico simple slope

def plot_simple_slope(df_slopes, var, out_dir):
    # Crea un barplot dei coefficienti simple slope
    plt.figure(figsize=(5,4))
    sns.barplot(
        data=df_slopes,
        x='Livello_Moderatore', y='coef',
        palette='Set2',
        ci=None
    )
    plt.axhline(0, color='gray', linestyle='--')
    plt.title(f'Simple Slope: {var}')
    plt.ylabel('Slope (coef)')
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f'simpleslope_{var}.png'), dpi=300)
    plt.close()

# Funzione per grafico post-hoc

def plot_posthoc(df_posthoc, var, out_dir):
    # Barplot delle medie per i gruppi confrontati
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

# Cicla su tutti i file Analisi_Mod_*.xlsx
for fname in os.listdir(input_dir):
    if fname.startswith('Analisi_Mod_') and fname.endswith('.xlsx'):
        fpath = os.path.join(input_dir, fname)
        xls = pd.ExcelFile(fpath)
        var = fname.replace('Analisi_Mod_','').replace('.xlsx','')
        # Simple slopes
        if 'SIMPLE_SLOPES' in xls.sheet_names:
            df_slopes = pd.read_excel(xls, sheet_name='SIMPLE_SLOPES')
            # Solo quelli significativi
            df_slopes_sig = df_slopes[df_slopes['pval'] < 0.05]
            if not df_slopes_sig.empty:
                plot_simple_slope(df_slopes_sig, var, output_dir)
                print(f'Creato simple slope plot per {var}')
        # Post-hoc
        if 'POST-HOC' in xls.sheet_names:
            df_posthoc = pd.read_excel(xls, sheet_name='POST-HOC')
            plot_posthoc(df_posthoc, var, output_dir)
            print(f'Creato post-hoc plot per {var}')

print('Fatto! Grafici di moderazione salvati in', output_dir)
