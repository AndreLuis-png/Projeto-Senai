from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql
import pymysql.cursors
import unicodedata

app = Flask(__name__)
app.secret_key = 'chave_secreta_almoxarifado'

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
db_config = {
    'host': '127.0.0.1',       
    'port': 3306,              
    'user': 'root',            
    'password': '',            
    'db': 'almoxarifado_db',   
    'cursorclass': pymysql.cursors.DictCursor,       
}

class MySQLWrapper:
    @property
    def connection(self):
        return pymysql.connect(**db_config)

mysql = MySQLWrapper()

# 🛡️ FUNÇÃO PADRONIZADORA DE TEXTO
def normalizar_texto(texto):
    if not texto:
        return ""
    texto = texto.strip()
    texto_nfd = unicodedata.normalize('NFD', texto)
    texto_sem_acento = "".join(c for c in texto_nfd if unicodedata.category(c) != 'Mn')
    return texto_sem_acento.capitalize()

def obter_nomes_produtos():
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT nome FROM estoque ORDER BY nome ASC")
        produtos = cursor.fetchall()
        cursor.close()
        conn.close()
        return [p['nome'] for p in produtos]
    except:
        return []

# 🔑 TELA DE LOGIN
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM usuarios WHERE login = %s AND senha = %s", (usuario, senha))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user:
                if user['status'] != 'ativo':
                    flash('Este utilizador está suspenso ou bloqueado no sistema.', 'error')
                    return render_template('login.html')
                    
                session['usuario'] = user['login']
                session['is_admin'] = (user['role'] == 'admin')
                
                return redirect(url_for('lobby'))
            else:
                flash('Utilizador ou senha incorretos.', 'error')
        except Exception as e:
            flash(f'Erro ao ligar ao Banco de Dados: {e}', 'error')
            
    return render_template('login.html')

# 🔎 PAINEL PRINCIPAL / CONSULTA DE ESTOQUE
@app.route('/lobby')
def lobby():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    area_filtrada = request.args.get('area_filtro', 'Todos')
    
    conn = mysql.connection
    cursor = conn.cursor()
    
    # CORREÇÃO: Puxa diretamente do estoque e verifica se o campo 'link_midia' não está nulo ou vazio
    query_base = """
        SELECT id_produto, nome, area, quantidade, descricao, 
               CASE WHEN link_midia IS NOT NULL AND link_midia != '' THEN 1 ELSE 0 END as possui_imagem
        FROM estoque
    """
    
    if area_filtrada and area_filtrada != 'Todos':
        cursor.execute(query_base + " WHERE area = %s ORDER BY id_produto ASC", (area_filtrada,))
    else:
        cursor.execute(query_base + " ORDER BY id_produto ASC")
        
    estoque = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('lobby.html', estoque=estoque, area_atual=area_filtrada)

# 🌐 ROTA DE API: RETORNA O LINK DA IMAGEM EM JSON FOR THE JAVASCRIPT
@app.route('/api/obter_link_imagem/<id_produto>')
def obter_link_imagem(id_produto):
    if 'usuario' not in session:
        return jsonify({'error': 'Não autorizado'}), 401
        
    conn = mysql.connection
    cursor = conn.cursor()
    
    # CORREÇÃO: Busca direta da coluna 'link_midia' na tabela 'estoque'
    cursor.execute("SELECT link_midia FROM estoque WHERE id_produto = %s", (id_produto,))
    produto = cursor.fetchone()
    cursor.close()
    conn.close() 
    
    if produto and produto['link_midia']:
        return jsonify({'link_url': produto['link_midia']})
    
    return jsonify({'error': 'Imagem não encontrada'}), 404

# 📥 ENTRADA DE MATERIAL
@app.route('/insercao', methods=['GET', 'POST'])
def insercao():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        nome = normalizar_texto(request.form.get('nome'))
        area_solicitada = request.form.get('area')
        quantidade = int(request.form.get('quantidade', 0))
        descricao = normalizar_texto(request.form.get('descricao'))[:255]
        link_imagem = request.form.get('link_imagem', '').strip()
        
        if not nome:
            flash("Nome do produto inválido!", "error")
            return redirect(url_for('insercao'))

        conn = mysql.connection
        cursor = conn.cursor()
        
        cursor.execute("SELECT id_produto, area, quantidade FROM estoque WHERE nome = %s", (nome,))
        item_existente = cursor.fetchone()
        
        if item_existente:
            target_id = item_existente['id_produto']
            nova_qtd_total = item_existente['quantidade'] + quantidade
            
            # CORREÇÃO: Se enviou um novo link no reabastecimento, atualiza também a coluna de mídia do produto
            if link_imagem:
                cursor.execute("UPDATE estoque SET quantidade = %s, link_midia = %s WHERE id_produto = %s", (nova_qtd_total, link_imagem, target_id))
            else:
                cursor.execute("UPDATE estoque SET quantidade = %s WHERE id_produto = %s", (nova_qtd_total, target_id))
            
            detalhe_log = f"Reabasteceu '{nome}' (ID: {target_id}). Adicionado: {quantidade} un. Novo Saldo: {nova_qtd_total} un."
            cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Inserção', %s)", (session['usuario'], detalhe_log))
            flash(f"Quantidade somada ao item '{nome}' com sucesso.", "success")
            
        else:
            prefixo = '0' if area_solicitada == 'Geral' else ('1' if area_solicitada == 'Mecânica' else '2')
            cursor.execute("SELECT id_produto FROM estoque WHERE id_produto LIKE %s ORDER BY id_produto DESC LIMIT 1", (prefixo + '%',))
            ultimo_item = cursor.fetchone()
            
            if ultimo_item:
                proximo_sequencial = int(ultimo_item['id_produto'][1:]) + 1
                novo_id = f"{prefixo}{proximo_sequencial:04d}"
            else:
                novo_id = f"{prefixo}0001"
                
            # CORREÇÃO: Salvando a string de mídia na nova coluna link_midia durante a criação do novo produto
            cursor.execute(
                "INSERT INTO estoque (id_produto, nome, area, quantidade, descricao, link_midia) VALUES (%s, %s, %s, %s, %s, %s)",
                (novo_id, nome, area_solicitada, quantidade, descricao, link_imagem if link_imagem else None)
            )
                
            detalhe_log = f"Cadastrou NOVO item '{nome}' (ID: {novo_id}) com stock inicial de {quantidade} un."
            cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Inserção', %s)", (session['usuario'], detalhe_log))
            flash(f"Novo item '{nome}' cadastrado com sucesso!", "success")
        
        cursor.close()
        conn.close()
        return redirect(url_for('lobby'))
        
    sugestoes = obter_nomes_produtos()
    return render_template('insercao.html', sugestoes=sugestoes)

# 📝 EDITAR INFORMAÇÕES OU APAGAR UM PRODUTO
@app.route('/editar/<id_produto>', methods=['GET', 'POST'])
def editar(id_produto):
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    conn = mysql.connection
    cursor = conn.cursor()
    
    if request.method == 'POST':
        botao_pressionado = request.form.get('botao_acao')
        
        cursor.execute("SELECT * FROM estoque WHERE id_produto = %s", (id_produto,))
        antigo = cursor.fetchone()
        
        if antigo:
            if botao_pressionado == 'excluir':
                cursor.execute("DELETE FROM estoque WHERE id_produto = %s", (id_produto,))
                detalhes_log = f"Excluiu o produto '{antigo['nome']}' (ID: {id_produto}). Saldo apagado: {antigo['quantidade']} un."
                cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Exclusão', %s)", (session['usuario'], detalhes_log))
                
                flash(f"O produto '{antigo['nome']}' foi excluído!", "success")
                cursor.close()
                conn.close()
                return redirect(url_for('lobby'))
            
            else:
                novo_nome = normalizar_texto(request.form.get('nome'))
                nova_area = request.form.get('area')
                nova_qtd = int(request.form.get('quantidade', 0))
                nova_descricao = normalizar_texto(request.form.get('descricao'))[:255]
                novo_link = request.form.get('link_imagem', '').strip()
                
                if not novo_nome:
                    flash("Nome do produto inválido!", "error")
                    return redirect(url_for('editar', id_produto=id_produto))

                id_final = id_produto
                if antigo['area'] != nova_area:
                    prefixo = '0' if nova_area == 'Geral' else ('1' if nova_area == 'Mecânica' else '2')
                    cursor.execute("SELECT id_produto FROM estoque WHERE id_produto LIKE %s ORDER BY id_produto DESC LIMIT 1", (prefixo + '%',))
                    ultimo_item = cursor.fetchone()
                    
                    if ultimo_item:
                        proximo_sequencial = int(ultimo_item['id_produto'][1:]) + 1
                        id_final = f"{prefixo}{proximo_sequencial:04d}"
                    else:
                        id_final = f"{prefixo}0001"
                
                # CORREÇÃO: Atualiza os dados comuns juntamente com o link_midia unificado na tabela estoque
                cursor.execute(
                    "UPDATE estoque SET id_produto = %s, nome = %s, area = %s, quantidade = %s, descricao = %s, link_midia = %s WHERE id_produto = %s",
                    (id_final, novo_nome, nova_area, nova_qtd, nova_descricao, novo_link if novo_link else None, id_produto)
                )
                    
                detalhes_mudanca = f"Editou item ID {id_produto}. Antigo: [{antigo['nome']}]. Novo: [ID: {id_final}, {novo_nome}]."
                cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Alteração', %s)", (session['usuario'], detalhes_mudanca))
                flash(f"Informações do item '{novo_nome}' atualizadas com sucesso!", "success")
                
        cursor.close()
        conn.close()
        return redirect(url_for('lobby'))
        
    # CORREÇÃO: Carregando a página de edição puxando o link diretamente da tabela estoque
    cursor.execute("SELECT * FROM estoque WHERE id_produto = %s", (id_produto,))
    produto = cursor.fetchone()
    
    link_atual = produto['link_midia'] if produto and produto['link_midia'] else ''
    
    cursor.close()
    conn.close()
    
    sugestoes = obter_nomes_produtos()
    return render_template('editar.html', produto=produto, sugestoes=sugestoes, link_atual=link_atual)

# 📤 RETIRADA / BAIXA DE MATERIAL
@app.route('/retirada', methods=['GET', 'POST'])
def retirada():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    conn = mysql.connection
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nome_digitado = normalizar_texto(request.form.get('nome_item_busca'))
        quantidade_retirar = int(request.form.get('quantidade', 0))
        
        # CORREÇÃO: Removido o "quantity=" que estava quebrando o comando SQL
        cursor.execute("SELECT id_produto, nome, quantidade FROM estoque WHERE nome = %s", (nome_digitado,))
        produto = cursor.fetchone()
        
        if produto:
            if produto['quantidade'] >= quantidade_retirar:
                nova_qtd = produto['quantidade'] - quantidade_retirar
                cursor.execute("UPDATE estoque SET quantidade = %s WHERE id_produto = %s", (nova_qtd, produto['id_produto']))
                
                detalhe_log = f"Retirou {quantidade_retirar} un. do item '{produto['nome']}' (ID: {produto['id_produto']})."
                cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Retirada', %s)", (session['usuario'], detalhe_log))
                flash(f"Baixa de {quantidade_retirar} un. efetuada no item '{produto['nome']}'!", "success")
                cursor.close()
                conn.close()
                return redirect(url_for('lobby'))
            else:
                flash(f"Quantidade indisponível! O saldo atual de '{produto['nome']}' é de apenas {produto['quantidade']} un.", "error")
        else:
            flash("Equipamento não encontrado! Certifique-se de selecionar ou digitar um nome válido.", "error")
            
    cursor.execute("SELECT id_produto, nome, quantidade FROM estoque ORDER BY id_produto ASC")
    estoque = cursor.fetchall()
    cursor.close()
    conn.close()
    
    sugestoes = obter_nomes_produtos()
    return render_template('retirada.html', estoque=estoque, sugestoes=sugestoes)

# 🛠️ PAINEL ADMINISTRATIVO
@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'usuario' not in session or not session.get('is_admin'):
        return redirect(url_for('lobby'))
        
    conn = mysql.connection
    cursor = conn.cursor()
    
    if request.method == 'POST':
        acao = request.form.get('acao')
        
        if acao == 'alterar_chave_mestra':
            nova_chave = request.form.get('nova_chave')
            cursor.execute("UPDATE config_admin SET chave_secundaria = %s WHERE id = 1", (nova_chave,))
            flash('Chave de segurança administrativa alterada com sucesso!', 'success')
        else:
            funcionario = request.form.get('funcionario')
            nova_senha = request.form.get('nova_senha')
            verificacao_seguranca = request.form.get('verificacao_seguranca')
            tipo_permissao = request.form.get('tipo_permissao', 'user')
            
            cursor.execute("SELECT chave_secundaria FROM config_admin ORDER BY id ASC LIMIT 1")
            chave_banco = cursor.fetchone()['chave_secundaria']
            
            if verificacao_seguranca != chave_banco:
                flash('Chave de verificação secundária incorreta! Operação cancelada.', 'error')
            else:
                if acao == 'cadastrar':
                    try:
                        cursor.execute(
                            "INSERT INTO usuarios (login, senha, status, role) VALUES (%s, %s, 'ativo', %s)", 
                            (funcionario, nova_senha, tipo_permissao)
                        )
                        flash(f'Perfil {funcionario} ({tipo_permissao}) criado com sucesso!', 'success')
                    except:
                        flash('Este login já existe no sistema.', 'error')
                elif acao == 'alterar_dados':
                    cursor.execute("UPDATE usuarios SET senha = %s WHERE login = %s", (nova_senha, funcionario))
                    flash(f'Senha de {funcionario} atualizada!', 'success')
                elif acao == 'restringir_temp':
                    periodo_bloqueio = request.form.get('tempo_bloqueio', 'Não especificado')
                    cursor.execute("UPDATE usuarios SET status = 'suspenso_temp' WHERE login = %s", (funcionario,))
                    
                    detalhes_suspensao = f"Usuário {funcionario} suspenso temporariamente por: {periodo_bloqueio}."
                    cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Bloqueio Temp', %s)", (session['usuario'], detalhes_suspensao))
                    flash(f'Usuário {funcionario} suspenso por {periodo_bloqueio}.', 'success')
                elif acao == 'excluir':
                    cursor.execute("DELETE FROM usuarios WHERE login = %s", (funcionario,))
                    flash(f'Usuário {funcionario} eliminado.', 'success')

    cursor.execute("SELECT login, status, senha, role FROM usuarios")
    usuarios = cursor.fetchall()
    
    cursor.execute("SELECT usuario, acao, detalhe, data_registro FROM historico_logs ORDER BY id DESC")
    historico = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin.html', usuarios=usuarios, historico=historico)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)