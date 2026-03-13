import pandas as pd
import os
import numpy as np

# --- 1. CONFIG ---
dir_base = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(dir_base, '../descrittive/database.xlsx')
out_path = os.path.join(dir_base, '../descrittive/database_compositi.xlsx')

# 1. CARICA DATABASE
df = pd.read_excel(db_path)
# Pulizia nomi colonne per evitare problemi con spazi extra
df.columns = df.columns.str.strip()

# --- 2. CREA COMPOSITI ABAS (Sottoscale, Totale Standard e Totale Suppongo) ---
sottoscale_abas = ['amb', 'comscol', 'vitascuola', 'sal_sic', 'tempo_libero', 'curadisè', 'autocontrollo', 'soc']

# Calcolo ABAS_TOT (Standard)
colonne_std_abas = [f'ABAS_{s}' for s in sottoscale_abas if f'ABAS_{s}' in df.columns]
df['ABAS_TOT'] = df[colonne_std_abas].sum(axis=1, min_count=1)

# Calcolo Sottoscale "Suppongo" e Totale Suppongo
colonne_s = []
for sub in sottoscale_abas:
    c_base = f'ABAS_{sub}'
    c_supp = f'ABAS_{sub}_suppongo'
    if c_base in df.columns and c_supp in df.columns:
        nome_s = f'abas_s_{sub}'
        df[nome_s] = df[[c_base, c_supp]].sum(axis=1, min_count=1)
        colonne_s.append(nome_s)

df['abas_suppongo_tot'] = df[colonne_s].sum(axis=1, min_count=1)

# --- 3. CREA COMPOSITO BRIEF_TOT ---
brief_subscales = [c for c in df.columns if 'BRIEF_' in c and not any(x in c.upper() for x in ['PRE', 'POST', 'TOT'])]
if brief_subscales:
    df['BRIEF_TOT'] = df[brief_subscales].sum(axis=1, min_count=1)

# --- 4. CALCOLO DIFFERENZA MATTONELLE (Solo valori grezzi) ---
def calc_diff(matt, mini):
    try:
        res = matt - mini
        return res if res >= 0 else 0 
    except:
        return np.nan

# PLANNING
if 'PLANNING_MATT_PRE' in df.columns and 'PLANNING_MATTI_MIN_PRE' in df.columns:
    df['planning_mattonelle_diff_pre'] = df.apply(lambda r: calc_diff(r['PLANNING_MATT_PRE'], r['PLANNING_MATTI_MIN_PRE']), axis=1)

if 'PLANNING_MATT_POST' in df.columns and 'PLANNING_MATTI_MIN_POST' in df.columns:
    df['planning_mattonelle_diff_post'] = df.apply(lambda r: calc_diff(r['PLANNING_MATT_POST'], r['PLANNING_MATTI_MIN_POST']), axis=1)

# PWM
pwm_matt_pre = next((c for c in df.columns if 'PWM' in c and 'MATT' in c and 'PRE' in c and 'MIN' not in c), None)
pwm_min_pre = next((c for c in df.columns if 'PWM' in c and 'MATT' in c and 'PRE' in c and 'MIN' in c), None)
pwm_matt_post = next((c for c in df.columns if 'PWM' in c and 'MATT' in c and 'POST' in c and 'MIN' not in c), None)
pwm_min_post = next((c for c in df.columns if 'PWM' in c and 'MATT' in c and 'POST' in c and 'MIN' in c), None)

if pwm_matt_pre and pwm_min_pre:
    df['pwm_mattonelle_diff_pre'] = df.apply(lambda r: calc_diff(r[pwm_matt_pre], r[pwm_min_pre]), axis=1)
if pwm_matt_post and pwm_min_post:
    df['pwm_mattonelle_diff_post'] = df.apply(lambda r: calc_diff(r[pwm_matt_post], r[pwm_min_post]), axis=1)

# --- 5. TRASFORMAZIONI LOGARITMICHE (ln) ---
# Ho rimosso le mattonelle da questa lista come richiesto
ln_vars = [
    'TOL_TP_PRE', 'TOL_TP_POST', 'TOL_TE_PRE', 'TOL_TE_POST', 'TOL16-T_tot_PRE', 'TOL16-T_tot_POST',
    'PLANNING_TP_PRE', 'PLANNING_TP_POST', 'PLANNING_TE_PRE', 'PLANNING_TE_POST', 'PLANNING_TR_PRE', 'PLANNING_TR_POST',
    'PWM_ TP_PRE', 'PWM_ TP_POST', 'PWM_ TE_PRE', 'PWM_ TE_POST', 'PWM_ TR_PRE', 'PWM_ TR_POST'
]

for col in ln_vars:
    if col in df.columns:
        df[f'{col}_ln'] = df[col].apply(lambda x: np.nan if pd.isna(x) or x <= 0 else np.log(x))

# --- 6. SALVATAGGIO ---
df.to_excel(out_path, index=False)
print(f"Database salvato con BRIEF_TOT, ABAS_TOT e Diff Mattonelle (senza LN) in: {out_path}")