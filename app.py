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
    'autocommit': True         
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
    
    query_base = """
        SELECT e.id_produto, e.nome, e.area, e.quantidade, e.descricao, 
               CASE WHEN m.link_url IS NOT NULL THEN 1 ELSE 0 END as possui_imagem
        FROM estoque e
        LEFT JOIN midia_produtos m ON e.id_produto = m.id_produto
    """
    
    if area_filtrada and area_filtrada != 'Todos':
        cursor.execute(query_base + " WHERE e.area = %s ORDER BY e.id_produto ASC", (area_filtrada,))
    else:
        cursor.execute(query_base + " ORDER BY e.id_produto ASC")
        
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
    cursor.execute("SELECT link_url FROM midia_produtos WHERE id_produto = %s LIMIT 1", (id_produto,))
    midia = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if midia and midia['link_url']:
        return jsonify({'link_url': midia['link_url']})
    
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
            cursor.execute("UPDATE estoque SET quantidade = %s WHERE id_produto = %s", (nova_qtd_total, target_id))
            
            if link_imagem:
                cursor.execute("SELECT id FROM midia_produtos WHERE id_produto = %s", (target_id,))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO midia_produtos (id_produto, link_url) VALUES (%s, %s)", (target_id, link_imagem))
            
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
                
            cursor.execute(
                "INSERT INTO estoque (id_produto, nome, area, quantidade, descricao) VALUES (%s, %s, %s, %s, %s)",
                (novo_id, nome, area_solicitada, quantidade, descricao)
            )
            
            if link_imagem:
                cursor.execute("INSERT INTO midia_produtos (id_produto, link_url) VALUES (%s, %s)", (novo_id, link_imagem))
                
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
                
                cursor.execute(
                    "UPDATE estoque SET id_produto = %s, nome = %s, area = %s, quantidade = %s, descricao = %s WHERE id_produto = %s",
                    (id_final, novo_nome, nova_area, nova_qtd, nova_descricao, id_produto)
                )
                
                cursor.execute("DELETE FROM midia_produtos WHERE id_produto = %s", (id_final,))
                if novo_link:
                    cursor.execute("INSERT INTO midia_produtos (id_produto, link_url) VALUES (%s, %s)", (id_final, novo_link))
                    
                detalhes_mudanca = f"Editou item ID {id_produto}. Antigo: [{antigo['nome']}]. Novo: [ID: {id_final}, {novo_nome}]."
                cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Alteração', %s)", (session['usuario'], detalhes_mudanca))
                flash(f"Informações do item '{novo_nome}' atualizadas com sucesso!", "success")
                
        cursor.close()
        conn.close()
        return redirect(url_for('lobby'))
        
    cursor.execute("SELECT * FROM estoque WHERE id_produto = %s", (id_produto,))
    produto = cursor.fetchone()
    
    cursor.execute("SELECT link_url FROM midia_produtos WHERE id_produto = %s LIMIT 1", (id_produto,))
    midia = cursor.fetchone()
    link_atual = midia['link_url'] if midia else ''
    
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