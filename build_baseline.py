import requests
import json
import os
import sys

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

def get_region(uf_lower):
    for reg, ufs in REGIONS.items():
        if uf_lower in ufs:
            return reg
    return 'Outros'

def parse_tse_u_json(data):
    """Parses TSE -u.json file format"""
    s_info = data.get('s', {})
    secoes_tot = int(s_info.get('ts', 0) or 0)
    secoes_ap = int(s_info.get('st', 0) or 0)
    pst_str = s_info.get('pst', '0,00').replace(',', '.')
    pct_secoes = float(pst_str) if pst_str else 0.0

    v_info = data.get('v', {})
    # Look for candidate info in carg[0]
    cands_list = []
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
                    cands_list.append({
                        'n': num,
                        'nm': nome,
                        'vap': vap,
                        'pvap': pvap,
                        'st': st,
                        'seq': int(c.get('seq', 99) or 99)
                    })

    cands_list.sort(key=lambda x: x['vap'], reverse=True)
    votos_validos = sum(c['vap'] for c in cands_list)
    
    # Extract total votes, blanks, nulls from v or estimate
    tv = int(v_info.get('tv', 0) or 0) if v_info else 0
    vb = int(v_info.get('vb', 0) or 0) if v_info else 0
    vn = int(v_info.get('vn', 0) or 0) if v_info else 0
    
    if tv == 0:
        tv = votos_validos

    return {
        'secoes_tot': secoes_tot,
        'secoes_ap': secoes_ap,
        'pct_secoes': pct_secoes,
        'votos_validos': votos_validos,
        'votos_totais': tv,
        'votos_brancos': vb,
        'votos_nulos': vn,
        'candidatos': cands_list
    }

def main():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    print("Baixando dados do 1º Turno (Presidente - Eleições 2026 - Código 6257)...")
    
    # 1. BR
    url_br = 'https://resultados.tse.jus.br/oficial/ele2026/6257/dados/br/br-c0001-e006257-u.json'
    r_br = requests.get(url_br, headers=headers)
    if r_br.status_code != 200:
        print(f"Erro ao baixar BR: {r_br.status_code}")
        sys.exit(1)
        
    br_data = parse_tse_u_json(r_br.json())
    print(f"BR baixado com sucesso: {br_data['votos_validos']:,} votos válidos.")

    # 2. UFs
    ufs_data = {}
    for uf in UFS:
        url_uf = f'https://resultados.tse.jus.br/oficial/ele2026/6257/dados/{uf}/{uf}-c0001-e006257-u.json'
        try:
            r_uf = requests.get(url_uf, headers=headers, timeout=10)
            if r_uf.status_code == 200:
                parsed = parse_tse_u_json(r_uf.json())
                parsed['nome'] = UF_NAMES.get(uf, uf.upper())
                parsed['regiao'] = get_region(uf)
                ufs_data[uf.upper()] = parsed
                print(f"[{uf.upper()}] OK - {parsed['votos_validos']:,} votos")
            else:
                print(f"[{uf.upper()}] HTTP {r_uf.status_code}")
        except Exception as e:
            print(f"[{uf.upper()}] Exceção: {e}")

    # 3. Aggregates by Region
    regioes_data = {}
    for reg, ufs_list in REGIONS.items():
        v_tot = 0
        v_val = 0
        s_tot = 0
        s_ap = 0
        cand_map = {}
        for uf in ufs_list:
            uf_up = uf.upper()
            if uf_up in ufs_data:
                u_item = ufs_data[uf_up]
                v_tot += u_item['votos_totais']
                v_val += u_item['votos_validos']
                s_tot += u_item['secoes_tot']
                s_ap += u_item['secoes_ap']
                for c in u_item['candidatos']:
                    num = c['n']
                    if num not in cand_map:
                        cand_map[num] = {'n': num, 'nm': c['nm'], 'vap': 0}
                    cand_map[num]['vap'] += c['vap']
        
        cands_reg = list(cand_map.values())
        for c in cands_reg:
            c['pvap'] = round((c['vap'] / v_val * 100), 2) if v_val > 0 else 0.0
        cands_reg.sort(key=lambda x: x['vap'], reverse=True)

        regioes_data[reg] = {
            'secoes_tot': s_tot,
            'secoes_ap': s_ap,
            'votos_totais': v_tot,
            'votos_validos': v_val,
            'candidatos': cands_reg
        }

    dataset = {
        'eleicao': '6257',
        'turno': 1,
        'ano': 2026,
        'brasil': br_data,
        'estados': ufs_data,
        'regioes': regioes_data
    }

    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'baseline_1t_2026.json')
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(f"\nBaseline 1T salvo com sucesso em: {out_file}")

if __name__ == '__main__':
    main()
