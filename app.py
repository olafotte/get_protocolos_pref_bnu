from flask import Flask, render_template_string, jsonify, request, send_file
import datetime
import io
import os
import re
import unicodedata

app = Flask(__name__)

# Função para remover acentos
def remover_acentos(txt):
    return ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn')


# Lista de palavras-chave
lista_original = ['AMABRE','Bom Retiro','Hermann Hering', 'Recife', 'Carijós',
    'Palhoça', 'Augusto Otte', 'Porto Alegre', 'Ernesto Emmendoerfer', 'Tiradentes', 'Gertrud Gross Hering',
    'Klara Hering', 'Vitor Hering', 'Cuiabá', 'Richard Holetz', 'Francisco Knoch', 'Teresina', 'Belém',
    'Oswaldo Berndt', 'Voluntários da Pátria', 'Alexandre Flemming', 'Sebastian Fischer','Inconfidentes']

lista_original=sorted(lista_original)
lista = [w.lower() for w in lista_original]



# Dicionário de famílias de palavras (adicione mais conforme necessário)
familias = {
    'Alexandre Flemming': ['Alexander Flemming', 'Alexandre Flemming','Alexander Fleming', 'Alexandre Fleming'],
    'carijos': ['carijos', 'carijo'],
    'Vitor Hering': ['victor hering', 'vitor hering'],
    'Klara Hering': ['klara hering', 'clara hering'],
    'Ernesto Emmendoerfer': ['ernesto emmendoerfer', 'ernesto emendoerfer'],
    'Gertrud Gross Hering': ['gertrud gross hering', 'gertrud gros hering', 'gertrud hering', 'gertrudes gross'],
    'Teresina': ['teresina', 'terezina'],
    # Adicione outras famílias conforme necessário
}

# Pré-processa famílias para busca rápida (mapa de variante para família)
mapa_familias = {}
for key, variantes in familias.items():
    for v in variantes:
        mapa_familias[remover_acentos(v).lower()] = set(remover_acentos(va).lower() for va in variantes)

# Lista normalizada para busca (sem acentos, lower)
lista_normalizada = set()
for nome in lista_original:
    nome_sem_acento = remover_acentos(nome).lower()
    if nome_sem_acento in mapa_familias:
        lista_normalizada.update(mapa_familias[nome_sem_acento])
    else:
        lista_normalizada.add(nome_sem_acento)

lista_normalizada = list(lista_normalizada)
print(sorted(lista_normalizada))
# Read Protocolo_combinados.txt and extract matching protocols

# Extrai todos os protocolos, retorna lista de dicts: {'id': '2024/00001', 'block': ..., 'ano': ..., 'numero': ...}
def extract_all_protocols(protocol_file, removidos=None):
    if removidos is None:
        removidos = set()
    with open(protocol_file, 'r', encoding='utf-8') as f:
        content = f.read()
    blocks = content.split('\n--- ')
    protocolos = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        id_line = lines[0].strip('- ').strip() if lines and lines[0].startswith('202') and '/' in lines[0] else None
        ano, numero = (id_line.split('/') if id_line and '/' in id_line else (None, None))
        if id_line and id_line in removidos:
            continue
        protocolos.append({'id': id_line, 'block': block, 'ano': ano, 'numero': numero})
    return protocolos


# Função para destacar palavras
def highlight(text, keywords):
    # Remove duplicatas e ignora vazios
    keywords = list({k.strip().lower() for k in keywords if k.strip()})
    if not keywords:
        return text
    # Ordena por tamanho decrescente para evitar sobreposição de matches
    keywords.sort(key=len, reverse=True)
    pattern = re.compile(r'(' + '|'.join(map(re.escape, keywords)) + r')', re.IGNORECASE)
    return pattern.sub(lambda m: f'<span class="highlight">{m.group(0)}</span>', text)

def contains_any_keyword(block, keywords):
    block_norm = remover_acentos(block).lower()
    return any(word in block_norm for word in keywords)

# Página principal: lista de protocolos à esquerda, detalhe à direita
@app.route('/')
def index():
    # Carrega removidos uma vez
    removidos = set()
    if os.path.exists('removidos.txt'):
        with open('removidos.txt', 'r', encoding='utf-8') as f:
            removidos = set(line.strip() for line in f if line.strip())
    protocolos = extract_all_protocols("Protocolo_combinados.txt", removidos)

    # Adiciona flag e filtra em uma única passagem
    protos = []
    total_arch = total_notarch = total_amabre = 0
    for p in protocolos:
        block_norm = remover_acentos(p['block']).lower()
        p['has_archivado'] = 'arquiva-se o protocolo' in block_norm
        if p['id'] and contains_any_keyword(p['block'], lista_normalizada):
            protos.append(p)
            if p['has_archivado']:
                total_arch += 1
            else:
                total_notarch += 1
            if 'amabre' in block_norm:
                total_amabre += 1
    total_todos = len(protos)
    html = '''
        <html>
        <head>
        <style>
        body { font-family: Arial, sans-serif; }
        .container { display: flex; height: 98vh; }
        .left { width: 20%; border-right: 1px solid #ccc; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; }
    .right { flex: 1; padding: 20px; overflow-y: auto; font-size: min(1.2vw, 1.1em); }
        .proto-item { cursor: pointer; padding: 6px; border-radius: 4px; }
        .proto-item:hover, .proto-item.selected { background: #e0e0e0; }
        .highlight { background-color: yellow; font-weight: bold; }
        pre { white-space: pre-wrap; word-break: break-word; }
        .filter-btn { margin: 2px 4px 8px 0; padding: 4px 10px; border: 1px solid #888; border-radius: 4px; background: #f5f5f5; cursor: pointer; }
        .filter-btn.selected { background: #b3d1ff; border-color: #0057b8; }
        .remove-btn { margin-left: 10px, 2px 6px; border: none; border-radius: 4px; background: #ffcccc; color: #d9534f; cursor: pointer; }
        .remove-btn:hover { background: #f5c6cb; }
        </style>
                    <script>
                    let currentFilter = 'all';
                    let familiasData = {};

                    function showProtocolo(id) {
    const detail = document.getElementById('detail');
    detail.innerHTML = '<em>Carregando...</em>';
    const search = document.getElementById('input-busca') ? document.getElementById('input-busca').value : '';
    fetch('/protocolo?id=' + encodeURIComponent(id) + '&search=' + encodeURIComponent(search))
        .then(r => r.json())
        .then(data => {
            detail.innerHTML = '<pre>' + data.html + '</pre>';
            // Marca selecionado
            document.querySelectorAll('.proto-item').forEach(e => e.classList.remove('selected'));
            let el = document.getElementById('item-' + id.replaceAll('/', '-'));
            if (el) el.classList.add('selected');
        });
}
                    function filterProtos(type) {
                        currentFilter = type;
                        document.querySelectorAll('.filter-btn').forEach(e => e.classList.remove('selected'));
                        document.getElementById('btn-' + type).classList.add('selected');
                        document.querySelectorAll('.proto-item').forEach(e => {
                          let isArch = e.getAttribute('data-arch') === '1';
                          let block = e.getAttribute('data-block') ? e.getAttribute('data-block').toLowerCase() : '';
                          if (type === 'all') e.style.display = '';
                          else if (type === 'arch') e.style.display = isArch ? '' : 'none';
                          else if (type === 'notarch') e.style.display = !isArch ? '' : 'none';
                          else if (type === 'amabre') e.style.display = block.includes('amabre') ? '' : 'none';
                        });
                        // Seleciona o primeiro visível
                        let first = Array.from(document.querySelectorAll('.proto-item')).find(e => e.style.display !== 'none');
                        if (first) first.click();
                        else document.getElementById('detail').innerHTML = '<em>Nenhum protocolo encontrado.</em>';
                    }

                    function exportarProtocolos() {
      let ids = Array.from(document.querySelectorAll('.proto-item'))
        .filter(e => e.style.display !== 'none')
        .map(e => e.id.replace('item-', '').replace(/-/g, '/'));
      if (ids.length === 0) {
        alert('Nenhum protocolo para exportar!');
        return;
      }
      fetch('/exportar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ids: ids})
      })
      .then(response => {
        if (!response.ok) throw new Error('Erro ao exportar');
        return response.blob().then(blob => ({ blob, response }));
      })
      .then(({ blob, response }) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        let disposition = response.headers.get('Content-Disposition');
        let filename = 'Exportados.txt';
        if (disposition && disposition.indexOf('filename=') !== -1) {
          filename = disposition.split('filename=')[1].replace(/'"'/g, '');
        }
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
      })
      .catch(e => alert('Erro ao exportar: ' + e.message));
    }

                    function removerProtocolo(id) {
  if (!confirm('Tem certeza que deseja remover este protocolo?')) return;
  fetch('/remover', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({id: id})
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      // Remove da lista
      let el = document.getElementById('item-' + id.replaceAll('/', '-'));
      if (el) el.remove();
      document.getElementById('detail').innerHTML = '<em>Protocolo removido.</em>';
    } else {
      alert('Erro ao remover protocolo.');
    }
  });
    }

                    function removerProtocoloSelecionado() {
      let sel = document.querySelector('.proto-item.selected');
      if (!sel) return;
      let id = sel.id.replace('item-', '').replace(/-/g, '/');
      if (sel.hasAttribute('onclick')) {
        let m = sel.getAttribute('onclick').match(/'(.*?)'/);
        if (m) id = m[1];
      }
      removerProtocolo(id);
    }
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Delete') {
        removerProtocoloSelecionado();
      }
    });

                    // Navegação por teclado (setas)
                    document.addEventListener('keydown', function(e) {
                        if (['ArrowUp','ArrowDown'].includes(e.key)) {
                            let items = Array.from(document.querySelectorAll('.proto-item')).filter(x => x.style.display !== 'none');
                            let sel = items.findIndex(x => x.classList.contains('selected'));
                            if (items.length === 0) return;
                            let next = sel;
                            if (e.key === 'ArrowDown') next = sel < items.length-1 ? sel+1 : 0;
                            if (e.key === 'ArrowUp') next = sel > 0 ? sel-1 : items.length-1;
                            if (next !== sel) {
                                items[next].click();
                                items[next].scrollIntoView({block:'nearest'});
                                e.preventDefault();
                            }
                        }
                    });

                    window.onload = function() {
                        fetch('/familias')
                            .then(response => response.json())
                            .then(data => {
                                const normalizedFamilias = {};
                                for (const key in data) {
                                    const variantes = data[key].map(v => normalizar(v));
                                    variantes.forEach(v => {
                                        normalizedFamilias[v] = variantes;
                                    });
                                    normalizedFamilias[normalizar(key)] = variantes;
                                }
                                familiasData = normalizedFamilias;
                                filterProtos('all'); // Initialize view after data is loaded
                            });
                    }

                    window.filterProtos = filterProtos;
                    // Filtro por palavra-chave do droplist
                    function normalizar(txt) {
    // Remove acentos de forma compatível com todos os navegadores
    return txt.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function getFamilia(palavra) {
    palavra = normalizar(palavra);
    return familiasData[palavra] || [palavra];
}

function filtrarPorPalavra() {
    let detail = document.getElementById('detail');
    detail.innerHTML = '<em>Carregando...</em>';
    let select = document.getElementById('droplist-palavra');
    let palavra = select.value.trim();
    let variantes = getFamilia(palavra);

    variantes = variantes.map(normalizar);
    document.querySelectorAll('.proto-item').forEach(e => {
        let block = e.getAttribute('data-block') ? normalizar(e.getAttribute('data-block')) : '';
        if (!palavra || palavra === '') {
            e.style.display = '';
        } else {
            e.style.display = variantes.some(v => block.includes(v)) ? '' : 'none';
        }
    });
    // Seleciona o primeiro visível
    let first = Array.from(document.querySelectorAll('.proto-item')).find(e => e.style.display !== 'none');
    if (first) first.click();
    else detail.innerHTML = '<em>Nenhum protocolo encontrado.</em>';
}
                    // Filtro por texto digitado
                    function filtrarPorTexto() {
                        let detail = document.getElementById('detail');
    detail.innerHTML = '<em>Carregando...</em>';
                        let texto = document.getElementById('input-busca').value.trim().toLowerCase();
                        let palavra = document.getElementById('droplist-palavra').value.trim().toLowerCase();
                        document.querySelectorAll('.proto-item').forEach(e => {
                            let block = e.getAttribute('data-block') ? e.getAttribute('data-block').toLowerCase() : '';
                            let matchPalavra = (!palavra || palavra === '') || block.includes(palavra);
                            let matchTexto = (!texto || texto === '') || block.includes(texto);
                            e.style.display = (matchPalavra && matchTexto) ? '' : 'none';
                        });
                        // Seleciona o primeiro visível
                        let first = Array.from(document.querySelectorAll('.proto-item')).find(e => e.style.display !== 'none');
                        if (first) first.click();
                        else detail.innerHTML = '<em>Nenhum protocolo encontrado.</em>';
                    }
                    // Atualizar filtro do droplist ao digitar
                    document.getElementById('input-busca').addEventListener('input', filtrarPorTexto);
                    document.getElementById('droplist-palavra').addEventListener('change', filtrarPorTexto);
                    </script>
        </head>
        <body>
        <div class="container">
            <div class="left">
                <h3>Protocolos</h3>
                <button class="filter-btn selected" id="btn-all" onclick="filterProtos('all')">Todos ({{total_todos}})</button>
                <button class="filter-btn" id="btn-arch" onclick="filterProtos('arch')">Arquivados (+) ({{total_arch}})</button>
                <button class="filter-btn" id="btn-notarch" onclick="filterProtos('notarch')">Não arquivados ({{total_notarch}})</button>
                <button class="filter-btn" id="btn-amabre" onclick="filterProtos('amabre')">AMABRE ({{total_amabre}})</button>
                <button class="filter-btn remove-main-btn" id="btn-remove-main" onclick="removerProtocoloSelecionado()" style="background:#ffdddd; color:#900; border-color:#d00; float:right;">Remover</button>
                <button class="filter-btn export-btn" id="btn-exportar" onclick="exportarProtocolos()" style="background:#e0ffe0; color:#060; border-color:#080; float:right;">Exportar</button>
                <div style="margin-top:10px"></div>
                <label for="droplist-palavra">Filtrar por palavra-chave:</label>
                <select id="droplist-palavra" onchange="filtrarPorPalavra()">
                    <option value="">-- Todas --</option>
                    {% for palavra in lista_original %}
                        <option value="{{palavra}}">{{palavra}}</option>
                    {% endfor %}
                </select>
                <br>
                <label for="input-busca">Buscar texto:</label>
                <input type="text" id="input-busca" placeholder="Digite para buscar..." oninput="filtrarPorTexto()" style="width:90%;margin-bottom:8px;">
                {% for p in protos %}
                    <div class="proto-item" id="item-{{p.id.replace('/', '-') }}" data-arch="{{1 if p.has_archivado else 0}}" data-block="{{p.block|e}}" onclick="showProtocolo('{{p.id}}')">
                        {{p.ano}}/{{p.numero}}{% if p.has_archivado %} <span title="Arquivado">+</span>{% endif %}
                    </div>
                {% endfor %}
            </div>
                            <div class="right" id="detail">
                                <em>Selecione um protocolo à esquerda...</em>
                            </div>
        </div>
        </body>
        </html>
        '''
    return render_template_string(html, protos=protos, total_todos=total_todos, total_arch=total_arch, total_notarch=total_notarch, total_amabre=total_amabre, lista_original=lista_original)

# Endpoint para retornar protocolo específico com destaque
@app.route('/protocolo')
def protocolo_detail():
    pid = request.args.get('id')
    search = request.args.get('search', '').strip()
    removidos = set()
    if os.path.exists('removidos.txt'):
        with open('removidos.txt', 'r', encoding='utf-8') as f:
            removidos = set(line.strip() for line in f if line.strip())
    protocolos = extract_all_protocols("Protocolo_combinados.txt", removidos)
    p = next((x for x in protocolos if x['id'] == pid and contains_any_keyword(x['block'], lista_normalizada)), None)
    if not p:
        return jsonify({'html': '<em>Protocolo não encontrado ou não está na lista.</em>'})
    # Destaca tanto as palavras da lista quanto o termo buscado, tudo sem acento
    palavras_destaque = lista_normalizada.copy()
    if search:
        search_norm = remover_acentos(search).lower()
        palavras_destaque.append(search_norm)
    html = highlight(remover_acentos(p['block']), palavras_destaque)
    return jsonify({'html': html})

@app.route('/familias')
def get_familias():
    return jsonify(familias)

@app.route('/remover', methods=['POST'])
def remover():
    data = request.get_json()
    pid = data.get('id')
    if not pid:
        return {'success': False}
    # Adiciona o id ao removidos.txt
    with open('removidos.txt', 'a', encoding='utf-8') as f:
        f.write(pid + '\n')
    return {'success': True}

@app.route('/exportar', methods=['POST'])
def exportar():
    data = request.get_json()
    ids = set(data.get('ids', []))
    if not ids:
        return '', 400
    removidos = set()
    if os.path.exists('removidos.txt'):
        with open('removidos.txt', 'r', encoding='utf-8') as f:
            removidos = set(line.strip() for line in f if line.strip())
    protocolos = extract_all_protocols("Protocolo_combinados.txt", removidos)
    blocos = []
    for p in protocolos:
        if p['id'] in ids:
            # Formata número com zero à esquerda
            if p['ano'] and p['numero']:
                numero_formatado = p['numero'].zfill(5)
                id_formatado = f"{p['ano']}/{numero_formatado}"
            else:
                id_formatado = p['id']
            # Ajusta a primeira linha do bloco
            block_lines = p['block'].splitlines()
            if block_lines and block_lines[0].startswith('202') and '/' in block_lines[0]:
                block_lines[0] = id_formatado + ' ---'
            bloco = f"--- {id_formatado} ---\n" + '\n'.join(block_lines[1:])
            blocos.append(bloco)
    conteudo = '\n\n'.join(blocos)
    now = datetime.datetime.now()
    nome = f"Exportados {now.strftime('%d-%m-%Y %H-%M')}.txt"
    buf = io.BytesIO()
    buf.write(conteudo.encode('utf-8'))
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=nome, mimetype='text/plain')

if __name__ == '__main__':
    app.run(debug=True)