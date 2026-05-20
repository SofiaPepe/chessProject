import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Percorsi file risultati
base_dir = os.path.dirname(os.path.abspath(__file__))
file_eta = os.path.join(base_dir, 'lmm_risultati_eta.xlsx')
file_classe = os.path.join(base_dir, 'lmm_risultati_classe.xlsx')

# Funzione per grafico interaction plot

def plot_interaction(data, var, group_col='gruppo', time_col='tempo', value_col='valore', out_dir=None):
    plt.figure(figsize=(6,4))
    sns.pointplot(
        data=data,
        x=time_col,
        y=value_col,
        hue=group_col,
        dodge=True,
        markers=['o', 's', 'D', '^'],
        capsize=.1,
        errwidth=1,
        palette='Set1'
    )
    plt.title(f'Interaction plot: {var}')
    plt.tight_layout()
    if out_dir:
        plt.savefig(os.path.join(out_dir, f'interaction_{var}.png'), dpi=300)
    plt.close()

# Funzione per processare un file risultati

def process_file(file_path, df_orig, out_dir):
    xls = pd.ExcelFile(file_path)
    # NON generare grafici SIMPLE SLOPES
    if 'LMM' not in xls.sheet_names:
        print(f'Nessun foglio LMM in {file_path}')
        return
    lmm = pd.read_excel(xls, sheet_name='LMM')
    if 'POST-HOC' in xls.sheet_names:
        posthoc = pd.read_excel(xls, sheet_name='POST-HOC')
    else:
        posthoc = None
    # Filtra solo interazioni significative
    for var in lmm['Variabile'].unique():
        lm_var = lmm[lmm['Variabile'] == var]
        if 'interazione' in lm_var['names'].values:
            p_inter = lm_var.loc[lm_var['names'] == 'interazione', 'pval'].values[0]
            if p_inter < 0.05:
                # Ricostruisci i dati long per il grafico
                col_pre = None
                col_post = None
                for c in df_orig.columns:
                    if c.upper().startswith(var.upper().replace('_LN','')) and c.upper().endswith('_PRE'):
                        col_pre = c
                    if c.upper().startswith(var.upper().replace('_LN','')) and c.upper().endswith('_POST'):
                        col_post = c
                if col_pre and col_post:
                    subset_cols = ['ID', 'gruppo', col_pre, col_post]
                    temp_df = df_orig[subset_cols].dropna()
                    long_df = pd.melt(temp_df, id_vars=['ID', 'gruppo'], value_vars=[col_pre, col_post], var_name='tempo', value_name='valore')
                    plot_interaction(long_df, var, out_dir=out_dir)
                    print(f'Creato interaction plot per {var}')
    # Grafici post-hoc significativi
    if posthoc is not None:
        for idx, row in posthoc.iterrows():
            if 'p-corr' in row and row['p-corr'] < 0.05:
                var = row['Variabile']
                group1 = row['A'] if 'A' in row else row.get('Group1', None)
                group2 = row['B'] if 'B' in row else row.get('Group2', None)
                if group1 and group2:
                    # Barplot dei valori medi per i due gruppi
                    col_pre = None
                    col_post = None
                    for c in df_orig.columns:
                        if c.upper().startswith(var.upper().replace('_LN','')) and c.upper().endswith('_PRE'):
                            col_pre = c
                        if c.upper().startswith(var.upper().replace('_LN','')) and c.upper().endswith('_POST'):
                            col_post = c
                    if col_pre and col_post:
                        subset_cols = ['ID', 'gruppo', col_pre, col_post]
                        temp_df = df_orig[subset_cols].dropna()
                        long_df = pd.melt(temp_df, id_vars=['ID', 'gruppo'], value_vars=[col_pre, col_post], var_name='tempo', value_name='valore')
                        # Barplot
                        plt.figure(figsize=(5,4))
                        sns.barplot(
                            data=long_df[long_df['gruppo'].isin([group1, group2])],
                            x='tempo', y='valore', hue='gruppo', ci='sd', palette='Set2'
                        )
                        plt.title(f'Post-hoc: {var} ({group1} vs {group2})')
                        plt.tight_layout()
                        plt.savefig(os.path.join(out_dir, f'posthoc_{var}_{group1}_vs_{group2}.png'), dpi=300)
                        plt.close()
                        print(f'Creato post-hoc plot per {var} ({group1} vs {group2})')


# Carica dati originali con controllo esistenza file
db_path = r'C:\Users\spepe\Desktop\progetto_scacchi\descrittive\database_compositi.xlsx'
if not os.path.exists(db_path):
    print(f"ERRORE: Il file dei dati non esiste: {db_path}")
    print("Controlla il percorso e il nome del file. Script interrotto.")
    exit(1)
df_orig = pd.read_excel(db_path)

# Crea cartella output se non esiste
out_dir = os.path.join(base_dir, 'grafici_lmm')
os.makedirs(out_dir, exist_ok=True)

# Processa entrambi i file
process_file(file_eta, df_orig, out_dir)
process_file(file_classe, df_orig, out_dir)

print('Fatto! Grafici salvati in', out_dir)
