import sys
import os
import pandas as pd
import pingouin as pg
import openpyxl
import numpy as np
from openpyxl.styles import PatternFill
from openpyxl.formatting.rule import CellIsRule

# --- CONFIGURAZIONE ---
dir_base = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(dir_base, '../descrittive/database_compositi.xlsx')
out_path_eta = os.path.join(dir_base, 'lmm_risultati_eta.xlsx')
out_path_classe = os.path.join(dir_base, 'lmm_risultati_classe.xlsx')

# 1. CARICAMENTO DATI
df = pd.read_excel(db_path)
df.columns = df.columns.str.strip()
id_col = 'ID'

# --- RICODIFICA MANUALE CLASSE ---
if 'classe' in df.columns:
    df['classe_clean'] = df['classe'].astype(str).str.strip().str.upper()
    mapping_classe = {
        'INF': 0, '1': 1, '1A': 1, '1B': 1, '2': 2, '2A': 2, '2B': 2
    }
    df['classe_num'] = df['classe_clean'].map(mapping_classe)
    df['classe_num'] = df['classe_num'].fillna(pd.to_numeric(df['classe_clean'], errors='coerce'))

if 'sesso' in df.columns:
    df['sesso'] = pd.factorize(df['sesso'])[0]

if 'età' in df.columns:
    df['età'] = pd.to_numeric(df['età'], errors='coerce')

# 2. IDENTIFICAZIONE VARIABILI (Inclusi i casi _LN)
cols = list(df.columns)
analisi_pairs = []

for c in cols:
    c_up = c.upper()
    if c_up.endswith('_PRE_LN'):
        base = c[:-7]
        col_post = next((x for x in cols if x.upper() == (base + "_POST_LN").upper()), None)
        if col_post:
            analisi_pairs.append((base + "_ln", c, col_post))
    elif c_up.endswith('_PRE') and not c_up.endswith('_LN'):
        base = c[:-4]
        col_post = next((x for x in cols if x.upper() == (base + "_POST").upper()), None)
        if col_post:
            analisi_pairs.append((base, c, col_post))

def esegui_analisi_lmm(covariates, output_file):
    lmm_list = []
    ph_list = []
    print(f"\nAnalisi con {len(analisi_pairs)} variabili e covariate: {covariates}")
    
    for base_name, col_pre, col_post in analisi_pairs:
        # Pulizia dati
        df[col_pre] = pd.to_numeric(df[col_pre], errors='coerce')
        df[col_post] = pd.to_numeric(df[col_post], errors='coerce')
        
        subset_cols = [id_col, 'gruppo', col_pre, col_post] + covariates
        temp_df = df[subset_cols].dropna()
        
        if temp_df.empty or temp_df['gruppo'].nunique() < 2: 
            continue
        
        # Formato LONG
        long_df = pd.melt(temp_df, id_vars=[id_col, 'gruppo'] + covariates, 
                          value_vars=[col_pre, col_post], var_name='tempo', value_name='valore')
        
        # Codifica tempo (0=PRE, 1=POST)
        long_df['tempo_num'] = long_df['tempo'].str.upper().str.contains('POST').astype(int)
        long_df['interazione'] = long_df['gruppo'] * long_df['tempo_num']

        try:
            # Modello Lineare
            predictors = ['gruppo', 'tempo_num', 'interazione'] + covariates
            lm = pg.linear_regression(long_df[predictors], long_df['valore'])
            lm.insert(0, 'Variabile', base_name)
            lmm_list.append(lm)
            
            # Post-hoc se interazione significativa
            p_inter = lm.loc[lm['names'] == 'interazione', 'pval'].values[0]
            if p_inter < 0.05:
                ph = pg.pairwise_tests(data=long_df, dv='valore', within='tempo', 
                                       between='gruppo', subject=id_col, padjust='bonf')
                ph.insert(0, 'Variabile', base_name)
                ph_list.append(ph)
        except Exception as e:
            print(f"Errore su {base_name}: {e}")

    # Salvataggio Excel e Formattazione
    if lmm_list:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            pd.concat(lmm_list).to_excel(writer, sheet_name='LMM', index=False)
            if ph_list:
                pd.concat(ph_list).to_excel(writer, sheet_name='POST-HOC', index=False)
        
        # Formattazione condizionale (Verde)
        wb = openpyxl.load_workbook(output_file)
        green_fill = PatternFill(start_color='90EE90', end_color='90EE90', fill_type='solid')
        p_targets = ['pval', 'p-unc', 'p-corr', 'p-adj']

        for sheetname in wb.sheetnames:
            ws = wb[sheetname]
            for col in ws.iter_cols(1, ws.max_column):
                header = str(col[0].value).lower()
                if any(x in header for x in p_targets):
                    col_let = col[0].column_letter
                    ws.conditional_formatting.add(f'{col_let}2:{col_let}{ws.max_row}',
                        CellIsRule(operator='lessThan', formula=['0.05'], fill=green_fill))
                    for cell in col[1:]: cell.number_format = '0.00000'
        wb.save(output_file)
        print(f"SUCCESSO! Creato: {output_file}")

# --- ESECUZIONE ---
# Analisi 1: Età e Sesso
esegui_analisi_lmm(['età', 'sesso'], out_path_eta)

# Analisi 2: Classe e Sesso
if 'classe_num' in df.columns:
    esegui_analisi_lmm(['classe_num', 'sesso'], out_path_classe)