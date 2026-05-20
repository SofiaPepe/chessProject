import sys
import os
import pandas as pd
import pingouin as pg
import openpyxl
import numpy as np
from openpyxl.styles import PatternFill

# --- 1. CONFIGURAZIONE PERCORSI ---
output_dir = r'C:\Users\spepe\Desktop\progetto_scacchi\rANOVA\lmm moderazione'
# Percorso assoluto del database compositi
db_path = r'C:\Users\spepe\Desktop\progetto_scacchi\descrittive\database_compositi.xlsx'

if not os.path.exists(db_path):
    print(f"ERRORE: Il file {db_path} non esiste. Generalo prima con l'altro script.")
    sys.exit()

df = pd.read_excel(db_path)
df.columns = df.columns.str.strip()

# Pulizia veloce covariate (necessaria per i calcoli statistici)
if 'sesso' in df.columns: df['sesso'] = pd.factorize(df['sesso'])[0]
if 'età' in df.columns: df['età'] = pd.to_numeric(df['età'], errors='coerce')

# --- 2. FUNZIONE ANALISI MODERAZIONE (LOGICA ORIGINALE) ---
def analisi_completa_moderazione(moderatore, output_file):
    if moderatore not in df.columns:
        print(f"Salto {moderatore}: non trovato nel file.")
        return

    lmm_list, ph_list, slopes_list = [], [], []
    
    # Identificazione automatica coppie Pre/Post (Grezzi e Log)
    cols = list(df.columns)
    pairs = []
    for c in cols:
        if c.upper().endswith('_PRE_LN'):
            base = c[:-7]
            post = next((x for x in cols if x.upper() == (base + "_POST_LN").upper()), None)
            if post: pairs.append((base + "_ln", c, post))
        elif c.upper().endswith('_PRE') and not c.upper().endswith('_LN'):
            base = c[:-4]
            post = next((x for x in cols if x.upper() == (base + "_POST").upper()), None)
            if post: pairs.append((base, c, post))

    for base_name, col_pre, col_post in pairs:
        subset = ['ID', 'gruppo', col_pre, col_post, 'età', 'sesso', moderatore]
        temp_df = df[subset].dropna()
        if temp_df.empty or temp_df['gruppo'].nunique() < 2: continue
            
        long_df = pd.melt(temp_df, id_vars=['ID', 'gruppo', 'età', 'sesso', moderatore], 
                          value_vars=[col_pre, col_post], var_name='tempo', value_name='valore')
        long_df['tempo_num'] = long_df['tempo'].str.upper().str.contains('POST').astype(int)
        
        # Centratura e Interazioni per il modello
        mod_mean, mod_std = long_df[moderatore].mean(), long_df[moderatore].std()
        long_df['interazione'] = long_df['gruppo'] * long_df['tempo_num']
        long_df['mod_gruppo'] = long_df['gruppo'] * long_df[moderatore]
        long_df['mod_tempo'] = long_df['tempo_num'] * long_df[moderatore]
        long_df['mod_3vie'] = long_df['gruppo'] * long_df['tempo_num'] * long_df[moderatore]
        
        try:
            # A. Regressione Lineare (Moderazione)
            preds = ['gruppo', 'tempo_num', 'interazione', 'età', 'sesso', moderatore, 'mod_gruppo', 'mod_tempo', 'mod_3vie']
            lm = pg.linear_regression(long_df[preds], long_df['valore'])
            lm.insert(0, 'Variabile', base_name)
            lmm_list.append(lm)
            
            # B. Post-Hoc e Simple Slopes se l'interazione a 3 vie è significativa (p < 0.05)
            p_3vie = lm.loc[lm['names'] == 'mod_3vie', 'pval'].values[0]
            if p_3vie < 0.05:
                # Pairwise tests
                ph = pg.pairwise_tests(data=long_df, dv='valore', within='tempo', between='gruppo', subject='ID', padjust='holm')
                ph.insert(0, 'Variabile', base_name)
                ph_list.append(ph)
                
                # Simple Slopes (-1SD e +1SD)
                for label, val in [('Basso (-1SD)', mod_mean - mod_std), ('Alto (+1SD)', mod_mean + mod_std)]:
                    long_df['mod_sh'] = long_df[moderatore] - val
                    long_df['int_sh'] = long_df['gruppo'] * long_df['tempo_num']
                    long_df['mod_g_sh'] = long_df['gruppo'] * long_df['mod_sh']
                    long_df['mod_t_sh'] = long_df['tempo_num'] * long_df['mod_sh']
                    long_df['mod_3v_sh'] = long_df['gruppo'] * long_df['tempo_num'] * long_df['mod_sh']
                    
                    preds_sh = ['gruppo', 'tempo_num', 'int_sh', 'età', 'sesso', 'mod_sh', 'mod_g_sh', 'mod_t_sh', 'mod_3v_sh']
                    lm_sh = pg.linear_regression(long_df[preds_sh], long_df['valore'])
                    
                    slope_row = lm_sh.loc[lm_sh['names'] == 'int_sh'].copy()
                    slope_row.insert(0, 'Livello_Moderatore', label)
                    slope_row.insert(0, 'Variabile', base_name)
                    slopes_list.append(slope_row)
        except: continue

    # Salvataggio file Excel con i 3 fogli
    if lmm_list:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            pd.concat(lmm_list, ignore_index=True).to_excel(writer, sheet_name='LMM', index=False)
            if ph_list: pd.concat(ph_list, ignore_index=True).to_excel(writer, sheet_name='POST-HOC', index=False)
            if slopes_list: pd.concat(slopes_list, ignore_index=True).to_excel(writer, sheet_name='SIMPLE_SLOPES', index=False)
        
        # Formattazione condizionale (Verde per p < 0.05)
        wb = openpyxl.load_workbook(output_file)
        green = PatternFill(start_color='90EE90', end_color='90EE90', fill_type='solid')
        for sn in wb.sheetnames:
            ws = wb[sn]
            for col in ws.iter_cols(1, ws.max_column):
                header = str(col[0].value).lower()
                if any(x in header for x in ['pval', 'p-unc', 'p-corr', 'p_corr']):
                    for cell in col[1:]:
                        if cell.value is not None and isinstance(cell.value, (int, float)) and cell.value < 0.05:
                            cell.fill = green
        wb.save(output_file)
        print(f"Generato: {os.path.basename(output_file)}")

# --- 3. ESECUZIONE MASSIVA ---
# Definiamo i nomi delle sottoscale come si trovano nel file già processato
sottoscale_abas = ['amb', 'comscol', 'vitascuola', 'sal_sic', 'tempo_libero', 'curadisè', 'autocontrollo', 'soc']

# Moderatori Principali

# Analisi per tutte le sottoscale BRIEF richieste
brief_subscales = [
    'BRIEF_ini', 'BRIEF_autom', 'BRI', 'BRIEF_shift', 'BRIEF_regem', 'ERI',
    'BRIEF_avvio', 'BRIEF_WM', 'BRIEF_pianific', 'BRIEF_monitoraggiodelcompito', 'BRIEF_organiz', 'CRI'
]
analisi_completa_moderazione('BRIEF_TOT', os.path.join(output_dir, 'Analisi_Mod_BRIEF_TOT.xlsx'))
for sub in brief_subscales:
    out_file = os.path.join(output_dir, f'Analisi_Mod_{sub}.xlsx')
    analisi_completa_moderazione(sub, out_file)
analisi_completa_moderazione('ABAS_TOT', os.path.join(output_dir, 'Analisi_Mod_ABAS_TOT.xlsx'))
analisi_completa_moderazione('abas_suppongo_tot', os.path.join(output_dir, 'Analisi_Mod_ABAS_SUPPONGO_TOT.xlsx'))

# Moderatori Sottoscale
for sub in sottoscale_abas:
    # Standard
    analisi_completa_moderazione(f'ABAS_{sub}', os.path.join(output_dir, f'Analisi_Mod_ABAS_{sub}.xlsx'))
    # Suppongo (già create dall'altro file come abas_s_...)
    analisi_completa_moderazione(f'abas_s_{sub}', os.path.join(output_dir, f'Analisi_Mod_abas_s_{sub}.xlsx'))

print("\nAnalisi completata con successo.")