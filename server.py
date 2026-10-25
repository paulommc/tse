import os
import json
import time
import threading
import requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder='static', template_folder='templates')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASELINE_FILE = os.path.join(BASE_DIR, 'baseline_1t_2026.json')

# Load 1T Baseline
BASELINE_1T = {}
if os.path.exists(BASELINE_FILE):
    with open(BASELINE_FILE, 'r', encoding='utf-8') as f:
        BASELINE_1T = json.load(f)

# Global Configuration
CONFIG = {
    'mode': 'simulation',  # 'simulation' or 'live'
    'election_code': '6258', # 2026 2º Turno Oficial
    'election_cycle': 'ele2026',
    'poll_interval': 15,
    'last_tse_poll': None,
    'last_tse_status': 'Não iniciado',
    'last_tse_data': None,
    'last_tse_error': None
}

UFS = ['ac', 'al', 'ap', 'am', 'ba', 'ce', 'df', 'es', 'go', 'ma', 'mt', 'ms', 'mg', 'pa', 'pb', 'pr', 'pe', 'pi', 'rj', 'rn', 'rs', 'ro', 'rr', 'sc', 'sp', 'se', 'to', 'zz']

UF_NAMES = {
    'ac': 'Acre', 'al': 'Alagoas', 'ap': 'Amapá', 'am': 'Amazonas', 'ba': 'Bahia', 'ce': 'Ceará',
    'df': 'Distrito Federal', 'es': 'Espírito Santo', 'go': 'Goiás', 'ma': 'Maranhão', 'mt': 'Mato Grosso',
    'ms': 'Mato Grosso do Sul', 'mg': 'Minas Gerais', 'pa': 'Pará', 'pb': 'Paraíba', 'pr': 'Paraná',
    'pe': 'Pernambuco', 'pi': 'Piauí', 'rj': 'Rio de Janeiro', 'rn': 'Rio Grande do Norte',
    'rs': 'Rio Grande do Sul', 'ro': 'Rondônia', 'rr': 'Roraima', 'sc': 'Santa Catarina',
    'sp': 'São Paulo', 'se': 'Sergipe', 'to': 'Tocantins', 'zz': 'Exterior'
}

REGIONS = {
    'Norte': ['ac', 'ap', 'am', 'pa', 'ro', 'rr', 'to'],
    'Nordeste': ['al', 'ba', 'ce', 'ma', 'pb', 'pe', 'pi', 'rn', 'se'],
    'Centro-Oeste': ['df', 'go', 'mt', 'ms'],
    'Sudeste': ['es', 'mg', 'rj', 'sp'],
    'Sul': ['pr', 'rs', 'sc'],
    'Exterior': ['zz']
}

# Counting progression speed factor relative to national average:
# >1 means finishes earlier, <1 means counts later
UF_SPEED_FACTORS = {
    'zz': 2.8, 'df': 2.2, 'sc': 1.6, 'pr': 1.5, 'rs': 1.4,
    'ms': 1.3, 'mt': 1.25, 'go': 1.2, 'es': 1.15, 'sp': 1.05,
    'mg': 0.95, 'rj': 0.95, 'ro': 1.0, 'ac': 0.9, 'to': 0.9,
    'se': 0.9, 'al': 0.88, 'pb': 0.85, 'rn': 0.85, 'pe': 0.82,
    'ce': 0.80, 'pi': 0.80, 'ba': 0.78, 'ma': 0.75, 'pa': 0.72,
    'am': 0.70, 'ap': 0.75, 'rr': 0.85
}

def get_region(uf_lower):
    for reg, ufs in REGIONS.items():
        if uf_lower in ufs:
            return reg
    return 'Outros'

# ----------------- PARSING TSE RESPONSES -----------------
def parse_tse_u_payload(data):
    """Parses TSE -u.json payload"""
    s_info = data.get('s', {})
    secoes_tot = int(s_info.get('ts', 0) or 0)
    secoes_ap = int(s_info.get('st', 0) or 0)
    pst_str = s_info.get('pst', '0,00').replace(',', '.')
    pct_secoes = float(pst_str) if pst_str else 0.0

    v_info = data.get('v', {})
    tv = int(v_info.get('tv', 0) or 0)
    vb = int(v_info.get('vb', 0) or 0)
    vn = int(v_info.get('vn', 0) or 0)

    cands_map = {}
    carg = data.get('carg', [])
    if carg:
        carg0 = carg[0]
        for agr in carg0.get('agr', []):
            for par in agr.get('par', []):
                for c in par.get('cand', []):
                    num = int(c.get('n', 0))
                    nome = c.get('nm', '').strip()
                    vap = int(c.get('vap', 0) or 0)
                    pvap = float(c.get('pvap', '0').replace(',', '.'))
                    st = c.get('st', '')
                    cands_map[num] = {
                        'n': num,
                        'nm': nome,
                        'vap': vap,
                        'pvap': pvap,
                        'st': st,
                        'seq': int(c.get('seq', 99) or 99)
                    }

    votos_validos = sum(c['vap'] for c in cands_map.values())
    if tv == 0:
        tv = votos_validos + vb + vn

    return {
        'secoes_tot': secoes_tot,
        'secoes_ap': secoes_ap,
        'pct_secoes': pct_secoes,
        'votos_validos': votos_validos,
        'votos_totais': tv,
        'votos_brancos': vb,
        'votos_nulos': vn,
        'candidatos': cands_map,
        'dg': data.get('dg', ''),
        'hg': data.get('hg', '')
    }

# ----------------- LIVE POLLING THREAD -----------------
def poll_tse_live():
    """Polls TSE live endpoints in the background"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    cycle = CONFIG['election_cycle']
    code = CONFIG['election_code']

    while True:
        if CONFIG['mode'] == 'live':
            try:
                # 1. Fetch BR
                url_br = f'https://resultados.tse.jus.br/oficial/{cycle}/{code}/dados/br/br-c0001-e00{code}-u.json'
                r_br = requests.get(url_br, headers=headers, timeout=10)
                if r_br.status_code == 200:
                    br_parsed = parse_tse_u_payload(r_br.json())
                    
                    # 2. Fetch UFs
                    ufs_parsed = {}
                    for uf in UFS:
                        url_uf = f'https://resultados.tse.jus.br/oficial/{cycle}/{code}/dados/{uf}/{uf}-c0001-e00{code}-u.json'
                        try:
                            r_uf = requests.get(url_uf, headers=headers, timeout=5)
                            if r_uf.status_code == 200:
                                parsed = parse_tse_u_payload(r_uf.json())
                                parsed['nome'] = UF_NAMES.get(uf, uf.upper())
                                parsed['regiao'] = get_region(uf)
                                ufs_parsed[uf.upper()] = parsed
                        except Exception:
                            pass

                    CONFIG['last_tse_data'] = {
                        'brasil': br_parsed,
                        'estados': ufs_parsed,
                        'timestamp': time.time(),
                        'dg': br_parsed.get('dg'),
                        'hg': br_parsed.get('hg')
                    }
                    CONFIG['last_tse_status'] = f"Atualizado em {time.strftime('%H:%M:%S')} - {br_parsed['pct_secoes']}% apurado"
                    CONFIG['last_tse_error'] = None
                else:
                    CONFIG['last_tse_status'] = f"Aguardando início / HTTP {r_br.status_code}"
            except Exception as e:
                CONFIG['last_tse_error'] = str(e)
                CONFIG['last_tse_status'] = f"Erro de conexão: {str(e)[:50]}"

        time.sleep(CONFIG['poll_interval'])

# Start polling thread
poll_thread = threading.Thread(target=poll_tse_live, daemon=True)
poll_thread.start()

# ----------------- SIMULATION GENERATOR -----------------
def generate_simulation_data(progress_pct, c3_to_13=40.0, c3_to_22=50.0, c3_blank=10.0, turnout_delta=0.0, regional_bias=None):
    """
    Generates realistic 2nd round election data progression based on 1T 2026 baseline.
    progress_pct: float 0.0 to 100.0
    c3_to_13: % of 3rd party votes migrating to Lula (13)
    c3_to_22: % of 3rd party votes migrating to Bolsonaro (22)
    turnout_delta: % shift in total valid votes vs 1T (-5% to +5%)
    regional_bias: dict with adjustment for specific regions
    """
    if regional_bias is None:
        regional_bias = {}

    baseline_br = BASELINE_1T.get('brasil', {})
    baseline_ufs = BASELINE_1T.get('estados', {})

    progress_ratio = max(0.0, min(100.0, float(progress_pct))) / 100.0

    total_secoes_br = baseline_br.get('secoes_tot', 499248)
    
    # Track aggregates
    tot_secoes_ap = 0
    tot_votos_val = 0
    tot_votos_tot = 0
    tot_votos_13 = 0
    tot_votos_22 = 0
    tot_brancos = 0
    tot_nulos = 0

    estados_res = {}
    regioes_res = {r: {
        'secoes_tot': 0, 'secoes_ap': 0, 'pct_secoes': 0.0,
        'votos_totais': 0, 'votos_validos': 0,
        'cand13_votos': 0, 'cand13_pct': 0.0,
        'cand22_votos': 0, 'cand22_pct': 0.0
    } for r in REGIONS}

    for uf_low in UFS:
        uf_up = uf_low.upper()
        uf_base = baseline_ufs.get(uf_up, {})
        regiao = uf_base.get('regiao', get_region(uf_low))
        
        s_tot = uf_base.get('secoes_tot', 1000)
        speed = UF_SPEED_FACTORS.get(uf_low, 1.0)

        # Non-linear logistic curve per state based on speed factor
        # At progress_ratio = 1.0, all states reach 1.0
        # At progress_ratio = 0.0, all states are 0.0
        if progress_ratio <= 0.0:
            uf_prog = 0.0
        elif progress_ratio >= 1.0:
            uf_prog = 1.0
        else:
            # Curve formulation
            scaled = (progress_ratio ** (1.0 / speed))
            # Smooth clamping
            uf_prog = max(0.0, min(1.0, scaled * (1.1 if speed > 1.2 else 0.95)))
            # When near end (>90%), converge together
            if progress_ratio > 0.85:
                blend = (progress_ratio - 0.85) / 0.15
                uf_prog = uf_prog * (1 - blend) + progress_ratio * blend

        s_ap = int(round(s_tot * uf_prog))
        pct_ap = round((s_ap / s_tot * 100), 2) if s_tot > 0 else 0.0

        # Calculate 2T target in this state
        v_val_1t = uf_base.get('votos_validos', 100000)
        cands_1t = {c['n']: c['vap'] for c in uf_base.get('candidatos', [])}
        v13_1t = cands_1t.get(13, 0)
        v22_1t = cands_1t.get(22, 0)
        v_others_1t = max(0, v_val_1t - (v13_1t + v22_1t))

        # Migration of 3rd party votes
        m13 = v_others_1t * (c3_to_13 / 100.0)
        m22 = v_others_1t * (c3_to_22 / 100.0)

        # Regional bias adjustment
        reg_adj = regional_bias.get(regiao, 0.0) / 100.0  # e.g. +1% to Lula, -1% to Bolsonaro
        
        # Total expected 2T votes in this state
        t_mult = (1.0 + (turnout_delta / 100.0))
        target_v13_state = int((v13_1t + m13) * (1.0 + reg_adj) * t_mult)
        target_v22_state = int((v22_1t + m22) * (1.0 - reg_adj) * t_mult)
        target_vval_state = target_v13_state + target_v22_state

        # Current counted votes in this state at current progress
        cur_v13 = int(round(target_v13_state * uf_prog))
        cur_v22 = int(round(target_v22_state * uf_prog))
        cur_vval = cur_v13 + cur_v22
        
        p13 = round((cur_v13 / cur_vval * 100), 2) if cur_vval > 0 else 0.0
        p22 = round((cur_v22 / cur_vval * 100), 2) if cur_vval > 0 else 0.0

        # 1T reference percentages
        p13_1t = round((v13_1t / v_val_1t * 100), 2) if v_val_1t > 0 else 0.0
        p22_1t = round((v22_1t / v_val_1t * 100), 2) if v_val_1t > 0 else 0.0

        # Swing vs 1T (percentage points)
        swing_13 = round(p13 - p13_1t, 2) if cur_vval > 0 else 0.0
        swing_22 = round(p22 - p22_1t, 2) if cur_vval > 0 else 0.0

        cur_tot = int(cur_vval * 1.05) # incl brancos/nulos
        cur_vb = int(cur_vval * 0.02)
        cur_vn = int(cur_vval * 0.03)

        estados_res[uf_up] = {
            'uf': uf_up,
            'nome': uf_base.get('nome', uf_up),
            'regiao': regiao,
            'secoes_tot': s_tot,
            'secoes_ap': s_ap,
            'pct_secoes': pct_ap,
            'votos_totais': cur_tot,
            'votos_validos': cur_vval,
            'cand13_votos': cur_v13,
            'cand13_pct': p13,
            'cand22_votos': cur_v22,
            'cand22_pct': p22,
            'cand13_1t_pct': p13_1t,
            'cand22_1t_pct': p22_1t,
            'cand13_1t_votos': v13_1t,
            'cand22_1t_votos': v22_1t,
            'swing_13': swing_13,
            'swing_22': swing_22,
            'votos_brancos': cur_vb,
            'votos_nulos': cur_vn,
            'proj_v13': target_v13_state,
            'proj_v22': target_v22_state,
            'proj_p13': round((target_v13_state / target_vval_state * 100), 2) if target_vval_state > 0 else 0.0,
            'proj_p22': round((target_v22_state / target_vval_state * 100), 2) if target_vval_state > 0 else 0.0
        }

        # Update region aggregate
        r_item = regioes_res[regiao]
        r_item['secoes_tot'] += s_tot
        r_item['secoes_ap'] += s_ap
        r_item['votos_totais'] += cur_tot
        r_item['votos_validos'] += cur_vval
        r_item['cand13_votos'] += cur_v13
        r_item['cand22_votos'] += cur_v22

        # Update national aggregate
        tot_secoes_ap += s_ap
        tot_votos_val += cur_vval
        tot_votos_tot += cur_tot
        tot_votos_13 += cur_v13
        tot_votos_22 += cur_v22
        tot_brancos += cur_vb
        tot_nulos += cur_vn

    # Compute region percentages
    for reg, r_item in regioes_res.items():
        v_val = r_item['votos_validos']
        s_tot = r_item['secoes_tot']
        r_item['pct_secoes'] = round((r_item['secoes_ap'] / s_tot * 100), 2) if s_tot > 0 else 0.0
        r_item['cand13_pct'] = round((r_item['cand13_votos'] / v_val * 100), 2) if v_val > 0 else 0.0
        r_item['cand22_pct'] = round((r_item['cand22_votos'] / v_val * 100), 2) if v_val > 0 else 0.0

    nat_pct_ap = round((tot_secoes_ap / total_secoes_br * 100), 2) if total_secoes_br > 0 else 0.0
    p13_br = round((tot_votos_13 / tot_votos_val * 100), 2) if tot_votos_val > 0 else 0.0
    p22_br = round((tot_votos_22 / tot_votos_val * 100), 2) if tot_votos_val > 0 else 0.0

    # 1T National reference
    base_cands = {c['n']: c for c in baseline_br.get('candidatos', [])}
    v13_1t_br = base_cands.get(13, {}).get('vap', 0)
    v22_1t_br = base_cands.get(22, {}).get('vap', 0)
    vval_1t_br = baseline_br.get('votos_validos', 119300788)
    p13_1t_br = round((v13_1t_br / vval_1t_br * 100), 2) if vval_1t_br > 0 else 0.0
    p22_1t_br = round((v22_1t_br / vval_1t_br * 100), 2) if vval_1t_br > 0 else 0.0

    # Projection calculation (Aggregated across state projections)
    proj_tot_13 = sum(e['proj_v13'] for e in estados_res.values())
    proj_tot_22 = sum(e['proj_v22'] for e in estados_res.values())
    proj_tot_val = proj_tot_13 + proj_tot_22
    proj_p13 = round((proj_tot_13 / proj_tot_val * 100), 2) if proj_tot_val > 0 else 0.0
    proj_p22 = round((proj_tot_22 / proj_tot_val * 100), 2) if proj_tot_val > 0 else 0.0

    # Mathematical thresholds
    votos_restantes = max(0, proj_tot_val - tot_votos_val)
    maioria_simples = (proj_tot_val // 2) + 1
    
    needed_13 = max(0, maioria_simples - tot_votos_13)
    needed_22 = max(0, maioria_simples - tot_votos_22)

    pct_needed_13 = round((needed_13 / votos_restantes * 100), 2) if votos_restantes > 0 else (0.0 if tot_votos_13 >= maioria_simples else 100.0)
    pct_needed_22 = round((needed_22 / votos_restantes * 100), 2) if votos_restantes > 0 else (0.0 if tot_votos_22 >= maioria_simples else 100.0)

    # Determine status / winner
    vencedor_matematico = None
    if tot_votos_13 >= maioria_simples:
        vencedor_matematico = 13
    elif tot_votos_22 >= maioria_simples:
        vencedor_matematico = 22

    return {
        'origem': 'simulacao',
        'progress_pct': progress_pct,
        'secoes_tot': total_secoes_br,
        'secoes_ap': tot_secoes_ap,
        'pct_secoes': nat_pct_ap,
        'votos_validos': tot_votos_val,
        'votos_totais': tot_votos_tot,
        'votos_brancos': tot_brancos,
        'votos_nulos': tot_nulos,
        'candidatos': [
            {
                'n': 13,
                'nm': 'LUIZ INÁCIO LULA DA SILVA',
                'apelido': 'Lula',
                'partido': 'PT',
                'vap': tot_votos_13,
                'pvap': p13_br,
                'cor': '#ff2a4b',
                'pvap_1t': p13_1t_br,
                'vap_1t': v13_1t_br,
                'swing': round(p13_br - p13_1t_br, 2) if tot_votos_val > 0 else 0.0,
                'proj_votos': proj_tot_13,
                'proj_pct': proj_p13,
                'votos_para_vencer': needed_13,
                'pct_restante_necessario': pct_needed_13
            },
            {
                'n': 22,
                'nm': 'FLÁVIO NANTES BOLSONARO',
                'apelido': 'Flávio Bolsonaro',
                'partido': 'PL',
                'vap': tot_votos_22,
                'pvap': p22_br,
                'cor': '#2563eb',
                'pvap_1t': p22_1t_br,
                'vap_1t': v22_1t_br,
                'swing': round(p22_br - p22_1t_br, 2) if tot_votos_val > 0 else 0.0,
                'proj_votos': proj_tot_22,
                'proj_pct': proj_p22,
                'votos_para_vencer': needed_22,
                'pct_restante_necessario': pct_needed_22
            }
        ],
        'projecao': {
            'lider_projetado': 13 if proj_p13 > proj_p22 else 22,
            'vencedor_matematico': vencedor_matematico,
            'votos_restantes': votos_restantes,
            'proj_tot_13': proj_tot_13,
            'proj_p13': proj_p13,
            'proj_tot_22': proj_tot_22,
            'proj_p22': proj_p22,
            'proj_tot_val': proj_tot_val
        },
        'regioes': regioes_res,
        'estados': estados_res,
        'comparativo_1t': {
            'votos_validos_1t': vval_1t_br,
            'cand13_1t_pct': p13_1t_br,
            'cand22_1t_pct': p22_1t_br,
            'cand13_1t_votos': v13_1t_br,
            'cand22_1t_votos': v22_1t_br,
            'dif_1t': v22_1t_br - v13_1t_br,
            'dif_atual': tot_votos_13 - tot_votos_22
        }
    }

# ----------------- REAL-TIME LIVE DATA PROCESSOR -----------------
def process_live_tse_data():
    """Processes cached live data from TSE into complete dashboard format with projections"""
    raw = CONFIG.get('last_tse_data')
    if not raw or not raw.get('brasil'):
        return None

    br = raw['brasil']
    estados_raw = raw.get('estados', {})
    baseline_br = BASELINE_1T.get('brasil', {})
    baseline_ufs = BASELINE_1T.get('estados', {})

    total_secoes_br = br.get('secoes_tot', 499248)
    tot_secoes_ap = br.get('secoes_ap', 0)
    pct_secoes = br.get('pct_secoes', 0.0)
    votos_validos = br.get('votos_validos', 0)
    votos_totais = br.get('votos_totais', 0)
    votos_brancos = br.get('votos_brancos', 0)
    votos_nulos = br.get('votos_nulos', 0)

    cands_br = br.get('candidatos', {})
    cand13_br = cands_br.get(13, {'vap': 0, 'pvap': 0.0, 'nm': 'LULA'})
    cand22_br = cands_br.get(22, {'vap': 0, 'pvap': 0.0, 'nm': 'FLÁVIO BOLSONARO'})

    # Baseline 1T
    base_cands = {c['n']: c for c in baseline_br.get('candidatos', [])}
    v13_1t_br = base_cands.get(13, {}).get('vap', 0)
    v22_1t_br = base_cands.get(22, {}).get('vap', 0)
    vval_1t_br = baseline_br.get('votos_validos', 119300788)
    p13_1t_br = round((v13_1t_br / vval_1t_br * 100), 2) if vval_1t_br > 0 else 0.0
    p22_1t_br = round((v22_1t_br / vval_1t_br * 100), 2) if vval_1t_br > 0 else 0.0

    # Process all states & compute swings + projections
    estados_res = {}
    regioes_res = {r: {
        'secoes_tot': 0, 'secoes_ap': 0, 'pct_secoes': 0.0,
        'votos_totais': 0, 'votos_validos': 0,
        'cand13_votos': 0, 'cand13_pct': 0.0,
        'cand22_votos': 0, 'cand22_pct': 0.0
    } for r in REGIONS}

    proj_tot_13 = 0
    proj_tot_22 = 0
    proj_tot_val = 0

    for uf_low in UFS:
        uf_up = uf_low.upper()
        uf_live = estados_raw.get(uf_up, {})
        uf_base = baseline_ufs.get(uf_up, {})
        regiao = uf_base.get('regiao', get_region(uf_low))

        s_tot = uf_live.get('secoes_tot') or uf_base.get('secoes_tot', 1000)
        s_ap = uf_live.get('secoes_ap', 0)
        pct_ap = uf_live.get('pct_secoes', 0.0)

        cands_uf = uf_live.get('candidatos', {})
        c13 = cands_uf.get(13, {'vap': 0, 'pvap': 0.0})
        c22 = cands_uf.get(22, {'vap': 0, 'pvap': 0.0})

        cur_v13 = c13.get('vap', 0)
        cur_v22 = c22.get('vap', 0)
        cur_vval = cur_v13 + cur_v22
        p13 = c13.get('pvap', 0.0)
        p22 = c22.get('pvap', 0.0)

        # Baseline 1T for this state
        v_val_1t = uf_base.get('votos_validos', 100000)
        cands_1t = {c['n']: c['vap'] for c in uf_base.get('candidatos', [])}
        v13_1t = cands_1t.get(13, 0)
        v22_1t = cands_1t.get(22, 0)
        p13_1t = round((v13_1t / v_val_1t * 100), 2) if v_val_1t > 0 else 0.0
        p22_1t = round((v22_1t / v_val_1t * 100), 2) if v_val_1t > 0 else 0.0

        # Swing
        swing_13 = round(p13 - p13_1t, 2) if cur_vval > 0 else 0.0
        swing_22 = round(p22 - p22_1t, 2) if cur_vval > 0 else 0.0

        # State Projection:
        # If pct_ap is 0, expect baseline with slight national swing
        # As pct_ap increases, rely on the observed state swing
        expected_total_state_val = v_val_1t # baseline expected valid votes
        remaining_val = max(0, expected_total_state_val - cur_vval)

        if pct_ap >= 5.0 and cur_vval > 0:
            # High confidence in state swing
            proj_rem_p13 = max(10.0, min(90.0, p13))
            proj_rem_p22 = 100.0 - proj_rem_p13
        elif pct_ap > 0.0 and cur_vval > 0:
            # Low confidence blend
            blend = pct_ap / 5.0
            proj_rem_p13 = (p13 * blend) + ((p13_1t + (cand13_br['pvap'] - p13_1t_br)) * (1 - blend))
            proj_rem_p22 = 100.0 - proj_rem_p13
        else:
            # 0% apurado: project from 1T + national swing so far
            nat_swing_13 = (cand13_br['pvap'] - p13_1t_br) if votos_validos > 0 else 0.0
            proj_rem_p13 = max(10.0, min(90.0, p13_1t + nat_swing_13))
            proj_rem_p22 = 100.0 - proj_rem_p13

        proj_state_v13 = cur_v13 + int(remaining_val * (proj_rem_p13 / 100.0))
        proj_state_v22 = cur_v22 + int(remaining_val * (proj_rem_p22 / 100.0))
        proj_state_tot = proj_state_v13 + proj_state_v22

        proj_tot_13 += proj_state_v13
        proj_tot_22 += proj_state_v22
        proj_tot_val += proj_state_tot

        estados_res[uf_up] = {
            'uf': uf_up,
            'nome': uf_base.get('nome', uf_up),
            'regiao': regiao,
            'secoes_tot': s_tot,
            'secoes_ap': s_ap,
            'pct_secoes': pct_ap,
            'votos_totais': uf_live.get('votos_totais', cur_vval),
            'votos_validos': cur_vval,
            'cand13_votos': cur_v13,
            'cand13_pct': p13,
            'cand22_votos': cur_v22,
            'cand22_pct': p22,
            'cand13_1t_pct': p13_1t,
            'cand22_1t_pct': p22_1t,
            'cand13_1t_votos': v13_1t,
            'cand22_1t_votos': v22_1t,
            'swing_13': swing_13,
            'swing_22': swing_22,
            'votos_brancos': uf_live.get('votos_brancos', 0),
            'votos_nulos': uf_live.get('votos_nulos', 0),
            'proj_v13': proj_state_v13,
            'proj_v22': proj_state_v22,
            'proj_p13': round((proj_state_v13 / proj_state_tot * 100), 2) if proj_state_tot > 0 else 0.0,
            'proj_p22': round((proj_state_v22 / proj_state_tot * 100), 2) if proj_state_tot > 0 else 0.0
        }

        # Region Accumulator
        r_item = regioes_res[regiao]
        r_item['secoes_tot'] += s_tot
        r_item['secoes_ap'] += s_ap
        r_item['votos_totais'] += uf_live.get('votos_totais', cur_vval)
        r_item['votos_validos'] += cur_vval
        r_item['cand13_votos'] += cur_v13
        r_item['cand22_votos'] += cur_v22

    # Compute region percentages
    for reg, r_item in regioes_res.items():
        v_val = r_item['votos_validos']
        s_tot = r_item['secoes_tot']
        r_item['pct_secoes'] = round((r_item['secoes_ap'] / s_tot * 100), 2) if s_tot > 0 else 0.0
        r_item['cand13_pct'] = round((r_item['cand13_votos'] / v_val * 100), 2) if v_val > 0 else 0.0
        r_item['cand22_pct'] = round((r_item['cand22_votos'] / v_val * 100), 2) if v_val > 0 else 0.0

    proj_p13 = round((proj_tot_13 / proj_tot_val * 100), 2) if proj_tot_val > 0 else 0.0
    proj_p22 = round((proj_tot_22 / proj_tot_val * 100), 2) if proj_tot_val > 0 else 0.0

    votos_restantes = max(0, proj_tot_val - votos_validos)
    maioria_simples = (proj_tot_val // 2) + 1
    needed_13 = max(0, maioria_simples - cand13_br['vap'])
    needed_22 = max(0, maioria_simples - cand22_br['vap'])

    pct_needed_13 = round((needed_13 / votos_restantes * 100), 2) if votos_restantes > 0 else 0.0
    pct_needed_22 = round((needed_22 / votos_restantes * 100), 2) if votos_restantes > 0 else 0.0

    vencedor_matematico = None
    if cand13_br['vap'] >= maioria_simples:
        vencedor_matematico = 13
    elif cand22_br['vap'] >= maioria_simples:
        vencedor_matematico = 22

    return {
        'origem': 'tse_live',
        'status_msg': CONFIG['last_tse_status'],
        'dg': br.get('dg'),
        'hg': br.get('hg'),
        'secoes_tot': total_secoes_br,
        'secoes_ap': tot_secoes_ap,
        'pct_secoes': pct_secoes,
        'votos_validos': votos_validos,
        'votos_totais': votos_totais,
        'votos_brancos': votos_brancos,
        'votos_nulos': votos_nulos,
        'candidatos': [
            {
                'n': 13,
                'nm': 'LUIZ INÁCIO LULA DA SILVA',
                'apelido': 'Lula',
                'partido': 'PT',
                'vap': cand13_br['vap'],
                'pvap': cand13_br['pvap'],
                'cor': '#ff2a4b',
                'pvap_1t': p13_1t_br,
                'vap_1t': v13_1t_br,
                'swing': round(cand13_br['pvap'] - p13_1t_br, 2) if votos_validos > 0 else 0.0,
                'proj_votos': proj_tot_13,
                'proj_pct': proj_p13,
                'votos_para_vencer': needed_13,
                'pct_restante_necessario': pct_needed_13
            },
            {
                'n': 22,
                'nm': 'FLÁVIO NANTES BOLSONARO',
                'apelido': 'Flávio Bolsonaro',
                'partido': 'PL',
                'vap': cand22_br['vap'],
                'pvap': cand22_br['pvap'],
                'cor': '#2563eb',
                'pvap_1t': p22_1t_br,
                'vap_1t': v22_1t_br,
                'swing': round(cand22_br['pvap'] - p22_1t_br, 2) if votos_validos > 0 else 0.0,
                'proj_votos': proj_tot_22,
                'proj_pct': proj_p22,
                'votos_para_vencer': needed_22,
                'pct_restante_necessario': pct_needed_22
            }
        ],
        'projecao': {
            'lider_projetado': 13 if proj_p13 > proj_p22 else 22,
            'vencedor_matematico': vencedor_matematico,
            'votos_restantes': votos_restantes,
            'proj_tot_13': proj_tot_13,
            'proj_p13': proj_p13,
            'proj_tot_22': proj_tot_22,
            'proj_p22': proj_p22,
            'proj_tot_val': proj_tot_val
        },
        'regioes': regioes_res,
        'estados': estados_res,
        'comparativo_1t': {
            'votos_validos_1t': vval_1t_br,
            'cand13_1t_pct': p13_1t_br,
            'cand22_1t_pct': p22_1t_br,
            'cand13_1t_votos': v13_1t_br,
            'cand22_1t_votos': v22_1t_br,
            'dif_1t': v22_1t_br - v13_1t_br,
            'dif_atual': cand13_br['vap'] - cand22_br['vap']
        }
    }

# ----------------- FLASK ROUTES -----------------
@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/api/apuracao')
def get_apuracao():
    mode = request.args.get('mode', CONFIG['mode'])
    
    if mode == 'live':
        data = process_live_tse_data()
        if data:
            return jsonify(data)
        # Fallback to simulation at 0% with status message if live data not ready
        sim = generate_simulation_data(0.0)
        sim['status_msg'] = CONFIG['last_tse_status'] or 'Aguardando publicação do TSE...'
        sim['origem'] = 'tse_live_standby'
        return jsonify(sim)
    else:
        # Simulation mode
        progress = float(request.args.get('progress', 50.0))
        c3_to_13 = float(request.args.get('c3_to_13', 42.0))
        c3_to_22 = float(request.args.get('c3_to_22', 48.0))
        c3_blank = float(request.args.get('c3_blank', 10.0))
        turnout = float(request.args.get('turnout', 0.0))
        
        reg_bias = {}
        for r in REGIONS:
            b_val = request.args.get(f'bias_{r}')
            if b_val:
                reg_bias[r] = float(b_val)

        data = generate_simulation_data(
            progress_pct=progress,
            c3_to_13=c3_to_13,
            c3_to_22=c3_to_22,
            c3_blank=c3_blank,
            turnout_delta=turnout,
            regional_bias=reg_bias
        )
        return jsonify(data)

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'POST':
        body = request.get_json() or {}
        if 'mode' in body:
            CONFIG['mode'] = body['mode']
        if 'election_code' in body:
            CONFIG['election_code'] = body['election_code']
        if 'election_cycle' in body:
            CONFIG['election_cycle'] = body['election_cycle']
        if 'poll_interval' in body:
            CONFIG['poll_interval'] = int(body['poll_interval'])
        return jsonify({'status': 'ok', 'config': CONFIG})
    return jsonify(CONFIG)

@app.route('/api/baseline')
def get_baseline():
    return jsonify(BASELINE_1T)

@app.route('/api/test_tse_connection')
def test_tse_conn():
    code = request.args.get('code', CONFIG['election_code'])
    cycle = request.args.get('cycle', CONFIG['election_cycle'])
    url = f'https://resultados.tse.jus.br/oficial/{cycle}/{code}/dados/br/br-c0001-e00{code}-u.json'
    start_time = time.time()
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        lat = round((time.time() - start_time) * 1000, 1)
        return jsonify({
            'status': 'ok' if r.status_code == 200 else 'http_error',
            'code': r.status_code,
            'url': url,
            'latency_ms': lat,
            'content_length': len(r.content)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'url': url
        })

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response

if __name__ == '__main__':
    print("=" * 60)
    print("  TSE ELEIÇÕES 2026 - SISTEMA DE APURAÇÃO & PROJEÇÃO  ")
    print("  Servidor local inicializado em: http://127.0.0.1:8080")
    print("=" * 60)
    app.run(host='127.0.0.1', port=8080, debug=False)
