# 🇧🇷 TSE 2026 - Central de Apuração Presidencial & Projeções em Tempo Real

Aplicação completa para acompanhar a apuração da **Eleição Presidencial de 2026 (2º Turno)** diretamente da CDN oficial do TSE, com comparativo do 1º turno, discriminação de votos por Estado e Região, mapa interativo e ferramenta de projeção/estimativa matemática.

---

## 🚀 Como Iniciar

Basta dar dois cliques no arquivo:
```bat
iniciar.bat
```
Ou executar no terminal (PowerShell / Prompt de Comando):
```bash
python server.py
```
O painel abrirá automaticamente no seu navegador no endereço:  
👉 **[http://127.0.0.1:8080](http://127.0.0.1:8080)**

*(Nota: a porta 8080 foi selecionada para não conflitar com a porta 5000 já utilizada pelo seu sistema Tuya).*

---

## 🗳️ Funcionalidades Principais

### 1. Destaque dos Candidatos a Presidente
* **Placar em Destaque:** Percentual de votos válidos e contagem absoluta de votos apurados para cada candidato.
* **Barra de Disputa (Tug-of-War):** Linha divisória de 50% indicando a margem de liderança em tempo real.
* **Indicador de Diferença:** Vantagem líquida em votos e pontos percentuais.

### 2. Votação por Estado (27 UFs + Exterior) e Região
* **6 Regiões Consolidadas:** Sudeste, Nordeste, Sul, Norte, Centro-Oeste e Exterior (ZZ).
* **Tabela Interativa dos Estados:** Exibe para cada UF:
  * % de seções apuradas;
  * Total de votos válidos;
  * Votos e % de cada candidato;
  * Swing (variação) em relação ao 1º turno;
  * Projeção final esperada para o estado.
* **Filtros e Busca:** Filtre por macrorregião ou pesquise diretamente pela sigla/nome da UF.
* **Mapa Eleitoral Interativo:** Mostra o Brasil com coloração dinâmica por liderança de cada estado e detalhes ao passar o mouse.

### 3. Ferramenta de Comparação: 1º Turno vs 2º Turno
* Carrega os dados reais e oficiais do 1º turno de 2026 salvos diretamente da Justiça Eleitoral.
* Mostra a variação percentual (swing em pontos percentuais: `+X.XX p.p.`).
* Calcula quantos votos faltam para cada candidato atingir ou superar a sua votação de 1º turno.

### 4. Ferramenta de Projeção & Estimativa Matemática
* **Modelo de Swing Estadual:** Extrapola os votos restantes ainda não apurados com base no comportamento real observado nas urnas já totalizadas de cada UF.
* **O que falta para vencer:** Calcula em tempo real quantos por cento dos votos restantes cada candidato precisa obter nas urnas pendentes para atingir 50% + 1 voto.
* **Simulador Interativo (Gaveta Expansível):** Permite ajustar:
  * Migração de votos da 3ª via (Augusto Cury, Renan Santos, Ronaldo Caiado, Romeu Zema, etc.);
  * Variação de comparecimento / abstenção;
  * Desvios de força por região (Nordeste, Sudeste, Sul, etc.).

### 5. Modos de Operação
* **⚡ Modo Simulação 2º Turno (Base 1º Turno):** Permite testar todo o dashboard hoje antes da abertura das urnas. Possui barra deslizante de progresso (0% a 100%), botão Play com controle de velocidade (1x, 2x, 5x) e parciais pré-programadas.
* **🔴 Modo Ao Vivo (TSE Oficial):** Conecta diretamente aos endpoints oficiais de totalização do TSE (`resultados.tse.jus.br`) via polling em segundo plano com tratamento de cache.

---

## ⚙️ Configurações do TSE

No canto superior direito, clique no ícone da engrenagem ⚙️ para abrir a modal de conexão técnica:
* **Código do Pleito Presidencial:** `6258` (Código oficial do 2º Turno Presidencial 2026 registrado no TSE).
* **Ciclo:** `ele2026`.
* **Intervalo de Consulta:** 15 segundos (ideal para garantir tempo real sem risco de bloqueio por WAF/CDN).
* **Botão "Testar Conexão Agora":** Executa um ping de diagnóstico diretamente contra o servidor do TSE e retorna a latência e o status HTTP da resposta.
