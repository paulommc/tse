/**
 * TSE APURAÇÃO ELEIÇÕES 2026 - DASHBOARD SCRIPT
 * Projeções, Comparativo com 1º Turno e Conexão em Tempo Real
 */

// Application State
const state = {
  mode: 'simulation', // 'simulation' | 'live'
  progress: 50.0,
  isPlaying: false,
  playSpeed: 1,
  playIntervalId: null,
  
  // Interactive Simulator Parameters
  c3_to_13: 42.0,
  c3_to_22: 48.0,
  turnout: 0.0,
  bias_ne: 0.0,
  bias_se: 0.0,
  bias_s: 0.0,

  // Table filtering and sorting
  regionFilter: 'ALL',
  searchQuery: '',
  sortField: 'votos_validos',
  sortDir: 'desc',

  // Current data packet
  currentData: null,
  baselineData: null,
  
  // Polling
  pollIntervalId: null
};

// State Acronyms Coordinates for SVG Map
const UF_MAP_POSITIONS = {
  'AC': { x: 50,  y: 280, w: 45, h: 32 },
  'AM': { x: 100, y: 160, w: 90, h: 70 },
  'RR': { x: 170, y: 70,  w: 45, h: 35 },
  'RO': { x: 130, y: 280, w: 45, h: 35 },
  'PA': { x: 240, y: 140, w: 85, h: 75 },
  'AP': { x: 280, y: 60,  w: 38, h: 35 },
  'TO': { x: 300, y: 245, w: 40, h: 55 },
  'MA': { x: 345, y: 160, w: 45, h: 50 },
  'PI': { x: 395, y: 190, w: 38, h: 48 },
  'CE': { x: 440, y: 155, w: 40, h: 40 },
  'RN': { x: 485, y: 160, w: 35, h: 28 },
  'PB': { x: 485, y: 195, w: 35, h: 25 },
  'PE': { x: 450, y: 225, w: 68, h: 28 },
  'AL': { x: 480, y: 258, w: 35, h: 22 },
  'SE': { x: 465, y: 284, w: 30, h: 20 },
  'BA': { x: 385, y: 260, w: 75, h: 65 },
  'MT': { x: 200, y: 280, w: 75, h: 65 },
  'GO': { x: 275, y: 340, w: 55, h: 50 },
  'DF': { x: 335, y: 345, w: 22, h: 18 },
  'MS': { x: 215, y: 385, w: 60, h: 55 },
  'MG': { x: 350, y: 345, w: 80, h: 65 },
  'ES': { x: 435, y: 375, w: 30, h: 32 },
  'RJ': { x: 390, y: 425, w: 45, h: 30 },
  'SP': { x: 295, y: 415, w: 75, h: 50 },
  'PR': { x: 280, y: 475, w: 65, h: 42 },
  'SC': { x: 290, y: 525, w: 60, h: 35 },
  'RS': { x: 260, y: 565, w: 75, h: 55 },
  'ZZ': { x: 480, y: 80,  w: 45, h: 30 }
};

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
  renderBrazilSvgMap();
  updateClock();
  setInterval(updateClock, 1000);

  // Load Baseline Data
  try {
    const res = await fetch('/api/baseline');
    state.baselineData = await res.json();
  } catch (e) {
    console.error('Erro ao carregar baseline:', e);
  }

  // Initial Fetch
  fetchDashboardData();

  // Setup Live Poller
  state.pollIntervalId = setInterval(() => {
    if (state.mode === 'live') {
      fetchDashboardData();
    }
  }, 15000);
});

// Real-time Clock
function updateClock() {
  const now = new Date();
  const timeStr = now.toLocaleTimeString('pt-BR');
  document.getElementById('server-time').innerText = timeStr;
}

// -------------------------------------------------------------
// DATA FETCHING & API INTERACTION
// -------------------------------------------------------------
async function fetchDashboardData() {
  let url = `/api/apuracao?mode=${state.mode}`;
  
  if (state.mode === 'simulation') {
    url += `&progress=${state.progress}`;
    url += `&c3_to_13=${state.c3_to_13}`;
    url += `&c3_to_22=${state.c3_to_22}`;
    url += `&turnout=${state.turnout}`;
    url += `&bias_Nordeste=${state.bias_ne}`;
    url += `&bias_Sudeste=${state.bias_se}`;
    url += `&bias_Sul=${state.bias_s}`;
  }

  try {
    const res = await fetch(url);
    const data = await res.json();
    state.currentData = data;
    renderDashboard(data);
  } catch (err) {
    console.error('Erro ao buscar apuração:', err);
  }
}

// -------------------------------------------------------------
// MAIN DASHBOARD RENDERER
// -------------------------------------------------------------
function renderDashboard(data) {
  if (!data) return;

  // 1. Status Indicator & Timestamps
  const liveIndicator = document.getElementById('live-indicator');
  const liveText = document.getElementById('live-status-text');
  const tseUpdateTime = document.getElementById('tse-update-time');

  if (state.mode === 'live') {
    liveIndicator.className = 'live-status-pill live-active';
    liveText.innerText = 'CONECTADO AO VIVO (TSE 2026)';
    tseUpdateTime.innerText = data.hg ? `TSE: ${data.hg}` : 'TSE: Conectado';
  } else {
    liveIndicator.className = 'live-status-pill';
    liveText.innerText = 'MODO SIMULAÇÃO 2º TURNO';
    tseUpdateTime.innerText = `Simulação: ${data.pct_secoes}% apurado`;
  }

  // 2. Candidates Cards
  const c13 = data.candidatos.find(c => c.n === 13) || {};
  const c22 = data.candidatos.find(c => c.n === 22) || {};

  // Lula 13
  document.getElementById('cand13-pct').innerText = `${c13.pvap.toFixed(2)}%`;
  document.getElementById('cand13-votes').innerText = c13.vap.toLocaleString('pt-BR');
  
  const swing13El = document.getElementById('cand13-swing');
  const s13Val = c13.swing;
  swing13El.className = `swing-tag ${s13Val >= 0 ? 'positive' : 'negative'}`;
  swing13El.innerHTML = `<i class="fa-solid fa-arrow-trend-${s13Val >= 0 ? 'up' : 'down'}"></i> ${s13Val >= 0 ? '+' : ''}${s13Val.toFixed(2)} p.p. vs 1ºT`;

  document.getElementById('cand13-proj-pct').innerText = `${c13.proj_pct.toFixed(2)}%`;
  document.getElementById('cand13-proj-votes').innerText = `${c13.proj_votos.toLocaleString('pt-BR')} votos projetados`;
  document.getElementById('cand13-needed').innerText = `Precisa de ${c13.pct_restante_necessario.toFixed(1)}% dos votos restantes`;

  // Flávio 22
  document.getElementById('cand22-pct').innerText = `${c22.pvap.toFixed(2)}%`;
  document.getElementById('cand22-votes').innerText = c22.vap.toLocaleString('pt-BR');
  
  const swing22El = document.getElementById('cand22-swing');
  const s22Val = c22.swing;
  swing22El.className = `swing-tag ${s22Val >= 0 ? 'positive' : 'negative'}`;
  swing22El.innerHTML = `<i class="fa-solid fa-arrow-trend-${s22Val >= 0 ? 'up' : 'down'}"></i> ${s22Val >= 0 ? '+' : ''}${s22Val.toFixed(2)} p.p. vs 1ºT`;

  document.getElementById('cand22-proj-pct').innerText = `${c22.proj_pct.toFixed(2)}%`;
  document.getElementById('cand22-proj-votes').innerText = `${c22.proj_votos.toLocaleString('pt-BR')} votos projetados`;
  document.getElementById('cand22-needed').innerText = `Precisa de ${c22.pct_restante_necessario.toFixed(1)}% dos votos restantes`;

  // 3. Center Totalizer & Gauge
  const pctSecoes = data.pct_secoes || 0.0;
  document.getElementById('secoes-pct').innerText = `${pctSecoes.toFixed(2)}%`;
  document.getElementById('secoes-count').innerText = `${data.secoes_ap.toLocaleString('pt-BR')} / ${data.secoes_tot.toLocaleString('pt-BR')}`;
  
  // Animate SVG gauge stroke
  const circle = document.getElementById('secoes-circle');
  if (circle) {
    circle.setAttribute('stroke-dasharray', `${pctSecoes}, 100`);
  }

  // Difference card
  const diffVotes = Math.abs(c13.vap - c22.vap);
  const diffPct = Math.abs(c13.pvap - c22.pvap);
  const leaderName = c13.vap >= c22.vap ? 'LULA' : 'FLÁVIO';
  
  const diffLeaderEl = document.getElementById('diff-leader-name');
  diffLeaderEl.innerText = `${leaderName} NA FRENTE`;
  diffLeaderEl.style.color = c13.vap >= c22.vap ? 'var(--c13-red)' : '#60a5fa';
  
  document.getElementById('diff-votes-num').innerText = `+${diffVotes.toLocaleString('pt-BR')} votos`;
  document.getElementById('diff-pct-num').innerText = `Margem: ${diffPct.toFixed(2)} p.p.`;

  // Ballot stats
  document.getElementById('stat-votos-validos').innerText = data.votos_validos.toLocaleString('pt-BR');
  document.getElementById('stat-votos-totais').innerText = data.votos_totais.toLocaleString('pt-BR');
  document.getElementById('stat-brancos-nulos').innerText = `${((data.votos_brancos || 0) + (data.votos_nulos || 0)).toLocaleString('pt-BR')}`;
  
  const votosFaltando = Math.max(0, (data.projecao ? data.projecao.votos_restantes : 0));
  document.getElementById('stat-votos-faltando').innerText = votosFaltando.toLocaleString('pt-BR');

  // 4. Tug of War Bar
  document.getElementById('tow-p13').innerText = `${c13.pvap.toFixed(2)}%`;
  document.getElementById('tow-p22').innerText = `${c22.pvap.toFixed(2)}%`;
  document.getElementById('tow-bar-13').style.width = `${c13.pvap}%`;
  document.getElementById('tow-bar-22').style.width = `${c22.pvap}%`;

  // 5. Projection & Estimativa Panel
  const proj = data.projecao || {};
  const winnerName = proj.lider_projetado === 13 ? 'LULA (13)' : 'FLÁVIO BOLSONARO (22)';
  const winnerPct = proj.lider_projetado === 13 ? proj.proj_p13 : proj.proj_p22;

  document.getElementById('proj-winner-name').innerText = winnerName;
  document.getElementById('proj-winner-name').style.color = proj.lider_projetado === 13 ? 'var(--c13-red)' : '#60a5fa';
  document.getElementById('proj-winner-pct').innerText = `${winnerPct.toFixed(2)}%`;

  document.getElementById('proj-box-13-pct').innerText = `${proj.proj_p13.toFixed(2)}%`;
  document.getElementById('proj-box-13-votes').innerText = `${proj.proj_tot_13.toLocaleString('pt-BR')} votos`;

  document.getElementById('proj-box-22-pct').innerText = `${proj.proj_p22.toFixed(2)}%`;
  document.getElementById('proj-box-22-votes').innerText = `${proj.proj_tot_22.toLocaleString('pt-BR')} votos`;

  // Math threshold bars
  document.getElementById('thresh-p13').innerText = `${c13.pct_restante_necessario.toFixed(1)}% dos votos restantes`;
  document.getElementById('thresh-bar-13').style.width = `${Math.min(100, Math.max(0, c13.pct_restante_necessario))}%`;
  document.getElementById('thresh-votes-13').innerText = `Faltam ${c13.votos_para_vencer.toLocaleString('pt-BR')} votos para a vitória`;

  document.getElementById('thresh-p22').innerText = `${c22.pct_restante_necessario.toFixed(1)}% dos votos restantes`;
  document.getElementById('thresh-bar-22').style.width = `${Math.min(100, Math.max(0, c22.pct_restante_necessario))}%`;
  document.getElementById('thresh-votes-22').innerText = `Faltam ${c22.votos_para_vencer.toLocaleString('pt-BR')} votos para a vitória`;

  const mathStatusText = document.getElementById('math-status-text');
  if (proj.vencedor_matematico === 13) {
    mathStatusText.innerHTML = `<strong>LULA MATEMATICAMENTE ELEITO!</strong> Ultrapassou a marca de 50% + 1 dos votos totais esperados.`;
  } else if (proj.vencedor_matematico === 22) {
    mathStatusText.innerHTML = `<strong>FLÁVIO BOLSONARO MATEMATICAMENTE ELEITO!</strong> Ultrapassou a marca de 50% + 1 dos votos totais esperados.`;
  } else {
    mathStatusText.innerHTML = `Extrapolação estatística por estado. Votos restantes a apurar: <strong>${votosFaltando.toLocaleString('pt-BR')}</strong>.`;
  }

  // 6. Comparison Tool (1º Turno vs 2º Turno)
  const comp = data.comparativo_1t || {};
  document.getElementById('comp-13-2t-votes').innerText = `${c13.vap.toLocaleString('pt-BR')} (${c13.pvap.toFixed(2)}%)`;
  document.getElementById('comp-13-swing-pp').innerText = `${s13Val >= 0 ? '+' : ''}${s13Val.toFixed(2)} p.p.`;
  document.getElementById('comp-13-swing-pp').className = s13Val >= 0 ? 'positive' : 'negative';
  
  const gap13 = Math.max(0, comp.cand13_1t_votos - c13.vap);
  document.getElementById('comp-13-gap-votes').innerText = gap13 > 0 ? `${gap13.toLocaleString('pt-BR')} restantes` : 'Superou a marca do 1º Turno!';

  document.getElementById('comp-22-2t-votes').innerText = `${c22.vap.toLocaleString('pt-BR')} (${c22.pvap.toFixed(2)}%)`;
  document.getElementById('comp-22-swing-pp').innerText = `${s22Val >= 0 ? '+' : ''}${s22Val.toFixed(2)} p.p.`;
  document.getElementById('comp-22-swing-pp').className = s22Val >= 0 ? 'positive' : 'negative';
  
  const gap22 = Math.max(0, comp.cand22_1t_votos - c22.vap);
  document.getElementById('comp-22-gap-votes').innerText = gap22 > 0 ? `${gap22.toLocaleString('pt-BR')} restantes` : 'Superou a marca do 1º Turno!';

  // 7. Regional Cards
  renderRegionsGrid(data.regioes);

  // 8. Update Brazil Map colors
  updateBrazilMap(data.estados);

  // 9. Render States Table
  renderStatesTable(data.estados);
}

// -------------------------------------------------------------
// REGIONAL CARDS RENDERER
// -------------------------------------------------------------
function renderRegionsGrid(regioes) {
  const container = document.getElementById('regions-container');
  if (!container || !regioes) return;

  const regOrder = ['Sudeste', 'Nordeste', 'Sul', 'Norte', 'Centro-Oeste', 'Exterior'];
  
  container.innerHTML = regOrder.map(rName => {
    const reg = regioes[rName] || {
      pct_secoes: 0, votos_validos: 0,
      cand13_pct: 0, cand13_votos: 0,
      cand22_pct: 0, cand22_votos: 0
    };

    const leaderText = reg.cand13_votos >= reg.cand22_votos ? 'Lula' : 'Flávio';
    const leaderClass = reg.cand13_votos >= reg.cand22_votos ? 'lula' : 'flavio';

    return `
      <div class="region-card" onclick="filterByRegionCard('${rName}')">
        <div>
          <div class="reg-card-header">
            <h5>${rName}</h5>
            <span class="reg-ap-badge">${reg.pct_secoes.toFixed(1)}% apurado</span>
          </div>

          <div class="reg-bar-wrapper">
            <div class="reg-bar">
              <div class="reg-bar-13" style="width: ${reg.cand13_pct}%"></div>
              <div class="reg-bar-22" style="width: ${reg.cand22_pct}%"></div>
            </div>
          </div>

          <div class="reg-cands-info">
            <div class="reg-cand-row lula">
              <span>Lula (13):</span>
              <strong>${reg.cand13_pct.toFixed(2)}% (${reg.cand13_votos.toLocaleString('pt-BR')})</strong>
            </div>
            <div class="reg-cand-row flavio">
              <span>Flávio (22):</span>
              <strong>${reg.cand22_pct.toFixed(2)}% (${reg.cand22_votos.toLocaleString('pt-BR')})</strong>
            </div>
          </div>
        </div>

        <div class="reg-totals">
          <span>Válidos: ${reg.votos_validos.toLocaleString('pt-BR')}</span>
          <span style="color: ${reg.cand13_votos >= reg.cand22_votos ? 'var(--c13-red)' : '#60a5fa'}">Líder: ${leaderText}</span>
        </div>
      </div>
    `;
  }).join('');
}

// -------------------------------------------------------------
// BRAZIL SVG MAP RENDERER
// -------------------------------------------------------------
function renderBrazilSvgMap() {
  const svg = document.getElementById('brazil-svg');
  if (!svg) return;

  svg.innerHTML = Object.entries(UF_MAP_POSITIONS).map(([uf, pos]) => {
    return `
      <g class="map-uf-node" id="map-group-${uf}" onmouseover="onUfHover(event, '${uf}')" onmouseout="onUfOut()" onclick="onUfClick('${uf}')">
        <rect x="${pos.x}" y="${pos.y}" width="${pos.w}" height="${pos.h}" rx="6" id="map-rect-${uf}" fill="#1e1317" stroke="#33141b" stroke-width="1.5" />
        <text x="${pos.x + pos.w / 2}" y="${pos.y + pos.h / 2 + 5}" text-anchor="middle" fill="#ffffff" font-family="'JetBrains Mono', monospace" font-size="12" font-weight="700" pointer-events="none">${uf}</text>
      </g>
    `;
  }).join('');
}

function updateBrazilMap(estados) {
  if (!estados) return;

  Object.entries(estados).forEach(([uf, data]) => {
    const rect = document.getElementById(`map-rect-${uf}`);
    if (!rect) return;

    if (data.votos_validos === 0) {
      rect.setAttribute('fill', '#15151c');
      return;
    }

    const diff = data.cand13_pct - data.cand22_pct;
    if (diff > 15) {
      rect.setAttribute('fill', '#ff2a4b'); // Lula Strong
    } else if (diff > 0) {
      rect.setAttribute('fill', '#991b1b'); // Lula Lead
    } else if (diff < -15) {
      rect.setAttribute('fill', '#1d4ed8'); // Flávio Strong
    } else if (diff < 0) {
      rect.setAttribute('fill', '#2563eb'); // Flávio Lead
    } else {
      rect.setAttribute('fill', '#475569'); // Empate
    }
  });
}

function onUfHover(event, uf) {
  const tooltip = document.getElementById('map-tooltip');
  if (!tooltip || !state.currentData || !state.currentData.estados) return;

  const ufData = state.currentData.estados[uf];
  if (!ufData) return;

  tooltip.innerHTML = `
    <strong>${ufData.nome} (${uf})</strong> - ${ufData.regiao}<br>
    Apuração: <strong>${ufData.pct_secoes.toFixed(1)}%</strong> (${ufData.secoes_ap.toLocaleString('pt-BR')}/${ufData.secoes_tot.toLocaleString('pt-BR')})<br>
    <span style="color: var(--c13-red)">Lula: ${ufData.cand13_pct.toFixed(2)}% (${ufData.cand13_votos.toLocaleString('pt-BR')})</span><br>
    <span style="color: #60a5fa">Flávio: ${ufData.cand22_pct.toFixed(2)}% (${ufData.cand22_votos.toLocaleString('pt-BR')})</span><br>
    Swing vs 1ºT: <strong>${ufData.swing_13 >= 0 ? '+' : ''}${ufData.swing_13.toFixed(2)} p.p.</strong><br>
    Projeção UF: Lula ${ufData.proj_p13.toFixed(1)}% vs Flávio ${ufData.proj_p22.toFixed(1)}%
  `;

  tooltip.style.display = 'block';
  tooltip.style.left = `${event.offsetX + 15}px`;
  tooltip.style.top = `${event.offsetY - 20}px`;
}

function onUfOut() {
  const tooltip = document.getElementById('map-tooltip');
  if (tooltip) tooltip.style.display = 'none';
}

function onUfClick(uf) {
  const searchInput = document.getElementById('state-search-input');
  if (searchInput) {
    searchInput.value = uf;
    filterStatesTable();
  }
}

// -------------------------------------------------------------
// STATES TABLE RENDERER
// -------------------------------------------------------------
function renderStatesTable(estados) {
  const tbody = document.getElementById('states-tbody');
  if (!tbody || !estados) return;

  let list = Object.values(estados);

  // Filter by Region
  if (state.regionFilter !== 'ALL') {
    list = list.filter(item => item.regiao === state.regionFilter);
  }

  // Filter by Search Query
  if (state.searchQuery) {
    const q = state.searchQuery.toLowerCase();
    list = list.filter(item => 
      item.uf.toLowerCase().includes(q) || 
      item.nome.toLowerCase().includes(q) || 
      item.regiao.toLowerCase().includes(q)
    );
  }

  // Sorting
  list.sort((a, b) => {
    let vA = a[state.sortField];
    let vB = b[state.sortField];

    if (typeof vA === 'string') {
      return state.sortDir === 'asc' ? vA.localeCompare(vB) : vB.localeCompare(vA);
    }
    return state.sortDir === 'asc' ? vA - vB : vB - vA;
  });

  tbody.innerHTML = list.map(item => {
    const leader = item.cand13_votos >= item.cand22_votos ? 'Lula' : 'Flávio';
    const leaderColor = item.cand13_votos >= item.cand22_votos ? 'var(--c13-red)' : '#60a5fa';
    const swingSign = item.swing_13 >= 0 ? '+' : '';
    const swingColor = item.swing_13 >= 0 ? 'var(--positive)' : 'var(--negative)';

    return `
      <tr id="row-uf-${item.uf}">
        <td>
          <span class="uf-badge">${item.uf}</span>
          <span>${item.nome}</span>
        </td>
        <td>
          <strong>${item.pct_secoes.toFixed(1)}%</strong>
        </td>
        <td>${item.votos_validos.toLocaleString('pt-BR')}</td>
        <td class="cand-13-col">
          <strong>${item.cand13_pct.toFixed(2)}%</strong>
          <span style="font-size: 0.72rem; color: var(--text-dim); display: block;">${item.cand13_votos.toLocaleString('pt-BR')}</span>
        </td>
        <td class="cand-22-col">
          <strong>${item.cand22_pct.toFixed(2)}%</strong>
          <span style="font-size: 0.72rem; color: var(--text-dim); display: block;">${item.cand22_votos.toLocaleString('pt-BR')}</span>
        </td>
        <td style="color: ${leaderColor}; font-weight: 700;">${leader}</td>
        <td style="color: ${swingColor};">
          ${swingSign}${item.swing_13.toFixed(2)} p.p.
        </td>
        <td>
          <span style="color: var(--c13-red);">${item.proj_p13.toFixed(1)}%</span> / 
          <span style="color: #60a5fa;">${item.proj_p22.toFixed(1)}%</span>
        </td>
      </tr>
    `;
  }).join('');
}

function filterStatesTable() {
  state.searchQuery = document.getElementById('state-search-input').value.trim();
  if (state.currentData) renderStatesTable(state.currentData.estados);
}

function setRegionFilter(region, btn) {
  state.regionFilter = region;
  document.querySelectorAll('.region-filter-pills .pill').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  if (state.currentData) renderStatesTable(state.currentData.estados);
}

function filterByRegionCard(region) {
  setRegionFilter(region, null);
  document.querySelectorAll('.region-filter-pills .pill').forEach(b => {
    if (b.innerText === region) b.classList.add('active');
  });
  document.getElementById('states-table').scrollIntoView({ behavior: 'smooth' });
}

function sortStates(field) {
  if (state.sortField === field) {
    state.sortDir = state.sortDir === 'desc' ? 'asc' : 'desc';
  } else {
    state.sortField = field;
    state.sortDir = 'desc';
  }
  if (state.currentData) renderStatesTable(state.currentData.estados);
}

// -------------------------------------------------------------
// SIMULATION ENGINE INTERACTIONS
// -------------------------------------------------------------
function switchMode(newMode) {
  state.mode = newMode;
  document.getElementById('btn-mode-sim').classList.toggle('active', newMode === 'simulation');
  document.getElementById('btn-mode-live').classList.toggle('active', newMode === 'live');
  
  const simPanel = document.getElementById('sim-control-panel');
  if (simPanel) {
    simPanel.style.display = newMode === 'simulation' ? 'block' : 'none';
  }

  fetchDashboardData();
}

function onSimSliderInput(val) {
  state.progress = parseFloat(val);
  document.getElementById('sim-progress-display').innerText = `${state.progress.toFixed(1)}%`;
  
  // Calculate simulated hour (17:00 at 0% to 20:30 at 100%)
  const totalMins = Math.round((state.progress / 100) * 210); // 3h30 = 210 mins
  const startHour = 17;
  const currentTotalMins = (startHour * 60) + totalMins;
  const h = Math.floor(currentTotalMins / 60);
  const m = currentTotalMins % 60;
  const mStr = m < 10 ? `0${m}` : `${m}`;
  document.getElementById('sim-est-time').innerText = `Horário estimado: ${h}:${mStr}`;

  fetchDashboardData();
}

function jumpSim(val) {
  const slider = document.getElementById('sim-slider');
  slider.value = val;
  onSimSliderInput(val);
}

function toggleSimPlay() {
  state.isPlaying = !state.isPlaying;
  const icon = document.getElementById('sim-play-icon');

  if (state.isPlaying) {
    icon.className = 'fa-solid fa-pause';
    state.playIntervalId = setInterval(() => {
      let nextVal = state.progress + (0.5 * state.playSpeed);
      if (nextVal > 100) {
        nextVal = 100;
        toggleSimPlay();
      }
      jumpSim(nextVal);
    }, 400);
  } else {
    icon.className = 'fa-solid fa-play';
    if (state.playIntervalId) clearInterval(state.playIntervalId);
  }
}

function setSimSpeed(spd, btn) {
  state.playSpeed = spd;
  document.querySelectorAll('.spd-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

// Simulator Parameters
function toggleSimDrawer() {
  const body = document.getElementById('sim-drawer-body');
  const chevron = document.getElementById('drawer-chevron');
  const isOpen = body.classList.toggle('open');
  chevron.className = `fa-solid fa-chevron-${isOpen ? 'up' : 'down'}`;
}

function onSimParamChange() {
  state.c3_to_13 = parseFloat(document.getElementById('slider-migr-13').value);
  state.c3_to_22 = parseFloat(document.getElementById('slider-migr-22').value);
  state.turnout = parseFloat(document.getElementById('slider-turnout').value);
  state.bias_ne = parseFloat(document.getElementById('slider-bias-ne').value);
  state.bias_se = parseFloat(document.getElementById('slider-bias-se').value);
  state.bias_s = parseFloat(document.getElementById('slider-bias-s').value);

  document.getElementById('val-migr-13').innerText = `${state.c3_to_13}%`;
  document.getElementById('val-migr-22').innerText = `${state.c3_to_22}%`;
  document.getElementById('val-turnout').innerText = `${state.turnout > 0 ? '+' : ''}${state.turnout.toFixed(1)}%`;
  document.getElementById('val-bias-ne').innerText = `${state.bias_ne > 0 ? '+' : ''}${state.bias_ne}%`;
  document.getElementById('val-bias-se').innerText = `${state.bias_se > 0 ? '+' : ''}${state.bias_se}%`;
  document.getElementById('val-bias-s').innerText = `${state.bias_s > 0 ? '+' : ''}${state.bias_s}%`;

  fetchDashboardData();
}

function resetSimParams() {
  document.getElementById('slider-migr-13').value = 42;
  document.getElementById('slider-migr-22').value = 48;
  document.getElementById('slider-turnout').value = 0;
  document.getElementById('slider-bias-ne').value = 0;
  document.getElementById('slider-bias-se').value = 0;
  document.getElementById('slider-bias-s').value = 0;
  onSimParamChange();
}

// -------------------------------------------------------------
// MODAL & TSE CONNECTION SETTINGS
// -------------------------------------------------------------
function openSettingsModal() {
  document.getElementById('settings-modal').classList.add('open');
}

function closeSettingsModal(e) {
  if (e && e.target !== e.currentTarget) return;
  document.getElementById('settings-modal').classList.remove('open');
}

async function saveSettings() {
  const code = document.getElementById('cfg-election-code').value.trim();
  const cycle = document.getElementById('cfg-election-cycle').value.trim();
  const poll = parseInt(document.getElementById('cfg-poll-interval').value) || 15;

  try {
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        election_code: code,
        election_cycle: cycle,
        poll_interval: poll
      })
    });
    closeSettingsModal();
    fetchDashboardData();
  } catch (err) {
    alert('Erro ao salvar configurações: ' + err);
  }
}

async function runTseConnectionTest() {
  const btn = document.getElementById('btn-run-test');
  const resultBox = document.getElementById('test-result-box');
  const code = document.getElementById('cfg-election-code').value.trim();
  const cycle = document.getElementById('cfg-election-cycle').value.trim();

  btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Testando...`;
  resultBox.innerHTML = `Conectando a <code>resultados.tse.jus.br</code>...`;

  try {
    const res = await fetch(`/api/test_tse_connection?code=${code}&cycle=${cycle}`);
    const data = await res.json();
    
    if (data.status === 'ok') {
      resultBox.innerHTML = `
        <span style="color: var(--positive); font-weight: 700;">&check; SUCESSO! Conexão estabelecida com o TSE.</span><br>
        Status HTTP: <strong>${data.code}</strong> &bull; Latência: <strong>${data.latency_ms} ms</strong> &bull; Tamanho: <strong>${data.content_length} bytes</strong><br>
        <span style="color: var(--text-dim)">Endpoint: ${data.url}</span>
      `;
    } else {
      resultBox.innerHTML = `
        <span style="color: var(--negative); font-weight: 700;">&cross; Resposta do Servidor: HTTP ${data.code}</span><br>
        <span style="color: var(--text-dim)">Endpoint: ${data.url}</span><br>
        <em>O arquivo de 2º turno do TSE já existe ou será totalizado a partir das 17h.</em>
      `;
    }
  } catch (err) {
    resultBox.innerHTML = `<span style="color: var(--negative);">&cross; Erro de rede: ${err}</span>`;
  } finally {
    btn.innerHTML = `<i class="fa-solid fa-bolt"></i> Testar Conexão Agora`;
  }
}
