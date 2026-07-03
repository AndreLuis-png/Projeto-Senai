import os
import re
import unicodedata
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
import bcrypt
import MySQLdb.cursors

app = Flask(__name__)
app.secret_key = os.urandom(24)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  
app.config['MYSQL_DB'] = 'almoxarifado_db'

mysql = MySQL(app)

def limpar_texto(texto):
    if not texto:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', texto)
    texto_sem_acento = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    texto_limpo = texto_sem_acento.strip().lower()
    return texto_limpo.capitalize()

def gerar_proximo_id(area):
    prefixos = {'Geral': '0', 'Mecânica': '1', 'Elétrica': '2'}
    prefixo = prefixos.get(area, '0')
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT id_produto FROM estoque WHERE id_produto LIKE %s ORDER BY id_produto ASC", (prefixo + '%',))
    ids_existentes = [int(row['id_produto']) for row in cursor.fetchall()]
    
    inicio_sequencia = int(prefixo + "0001")
    proximo_numero = inicio_sequencia
    while proximo_numero in ids_existentes:
        proximo_numero += 1
        
    return f"{proximo_numero:05d}"

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha']
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM usuarios WHERE login = %s", (usuario,))
        account = cursor.fetchone()
        
        if account:
            senha_banco = account.get('senha')
            if senha_banco and bcrypt.checkpw(senha.encode('utf-8'), senha_banco.encode('utf-8')):
                if account.get('status') != 'ativo':
                    flash(f"Este utilizador encontra-se suspenso/bloqueado. Status: {account.get('status')}.")
                    return redirect(url_for('login'))
                    
                session['logged_in'] = True
                session['usuario'] = account['login']
                session['is_admin'] = (account['role'] == 'admin')
                return redirect(url_for('lobby'))
            else:
                flash("Utilizador ou Palavra-passe incorretos!")
        else:
            flash("Utilizador ou Palavra-passe incorretos!")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/lobby', methods=['GET'])
@app.route('/lobby/<area_filtro>', methods=['GET'])
def lobby(area_filtro='Todos'):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    termo_pesquisa = request.args.get('pesquisa', '').strip()
    ordem_preco = request.args.get('ordem', '').strip()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    query = """
        SELECT id_produto, nome, area, quantidade, preco, descricao, 
        CASE WHEN link_midia IS NOT NULL AND link_midia != '' THEN 1 ELSE 0 END as possui_imagem 
        FROM estoque WHERE 1=1
    """
    params = []
    
    if area_filtro != 'Todos':
        query += " AND area = %s"
        params.append(area_filtro)
        
    if termo_pesquisa:
        query += " AND (nome LIKE %s OR id_produto LIKE %s OR CAST(preco AS CHAR) LIKE %s)"
        params.append('%' + termo_pesquisa + '%')
        params.append('%' + termo_pesquisa + '%')
        params.append('%' + termo_pesquisa + '%')
        
    if ordem_preco == 'crescente':
        query += " ORDER BY preco ASC"
    elif ordem_preco == 'decrescente':
        query += " ORDER BY preco DESC"
    else:
        query += " ORDER BY id_produto ASC"
        
    cursor.execute(query, tuple(params))
    itens_estoque = cursor.fetchall()
    
    cursor.execute("SELECT id_produto, nome, preco FROM estoque")
    sugestoes = cursor.fetchall()
    
    return render_template('lobby.html', estoque=itens_estoque, area_atual=area_filtro, sugestoes=sugestoes, termo_pesquisa=termo_pesquisa, ordem_atual=ordem_preco)
@app.route('/api/obter_link_imagem/<id_produto>')
def obter_link_imagem(id_produto):
    if 'logged_in' not in session:
        return jsonify({'error': 'Não autorizado'}), 401
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT link_midia FROM estoque WHERE id_produto = %s", (id_produto,))
    produto = cursor.fetchone()
    return jsonify({'link_url': produto['link_midia'] if produto else None})

@app.route('/insercao', methods=['GET', 'POST'])
def insercao():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if request.method == 'POST':
        nome = limpar_texto(request.form['nome'])
        area = request.form['area']
        quantidade = int(request.form['quantidade'])
        preco = float(request.form['preco'].replace(',', '.'))
        descricao = limpar_texto(request.form.get('descricao', ''))
        link_imagem = request.form.get('link_imagem', None)
        
        cursor.execute("SELECT * FROM estoque WHERE nome = %s AND area = %s", (nome, area))
        produto_existente = cursor.fetchone()
        
        if produto_existente:
            nova_qtd = produto_existente['quantidade'] + quantidade
            cursor.execute("UPDATE estoque SET quantidade = %s, preco = %s WHERE id_produto = %s", (nova_qtd, preco, produto_existente['id_produto']))
            id_final = produto_existente['id_produto']
        else:
            id_final = gerar_proximo_id(area)
            cursor.execute("""
                INSERT INTO estoque (id_produto, nome, area, quantidade, preco, descricao, link_midia)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (id_final, nome, area, quantidade, preco, descricao, link_imagem if link_imagem else None))
            
        cursor.execute("""
            INSERT INTO historico_logs (usuario, acao, detalhe)
            VALUES (%s, 'Inserção', %s)
        """, (session['usuario'], f"Adicionado {quantidade} un do item {nome} (ID: {id_final}) a R${preco:.2f} cada"))
        
        mysql.connection.commit()
        flash(f"Entrada do item '{nome}' registrada com sucesso!", "success")
        return redirect(url_for('lobby'))
        
    cursor.execute("SELECT id_produto, nome, preco FROM estoque")
    sugestoes = cursor.fetchall()
    return render_template('insercao.html', sugestoes=sugestoes)

@app.route('/retirada', methods=['GET', 'POST'])
def retirada():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if request.method == 'POST':
        nome_selecionado = request.form['nome']
        quantidade_retirar = int(request.form['quantidade'])
        
        cursor.execute("SELECT * FROM estoque WHERE nome = %s AND quantidade >= %s", (nome_selecionado, quantidade_retirar))
        produto = cursor.fetchone()
        
        if produto:
            nova_qtd = produto['quantidade'] - quantidade_retirar
            cursor.execute("UPDATE estoque SET quantidade = %s WHERE id_produto = %s", (nova_qtd, produto['id_produto']))
            
            cursor.execute("""
                INSERT INTO historico_logs (usuario, acao, detalhe)
                VALUES (%s, 'Retirada', %s)
            """, (session['usuario'], f"Retirado {quantidade_retirar} un do item {produto['nome']} (ID: {produto['id_produto']})"))
            
            mysql.connection.commit()
            flash("Baixa efetuada com sucesso!", "success")
            return redirect(url_for('lobby'))
        else:
            flash("Erro: Produto não encontrado ou quantidade insuficiente em estoque!", "error")
            
    cursor.execute("SELECT id_produto, nome, preco FROM estoque WHERE quantidade > 0")
    sugestoes = cursor.fetchall()
    return render_template('retirada.html', sugestoes=sugestoes)

@app.route('/editar/<id_produto>', methods=['GET', 'POST'])
def editar(id_produto):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if request.method == 'POST':
        botao_acao = request.form.get('botao_acao')
        
        if botao_acao == 'excluir':
            cursor.execute("SELECT nome FROM estoque WHERE id_produto = %s", (id_produto,))
            prod = cursor.fetchone()
            cursor.execute("DELETE FROM estoque WHERE id_produto = %s", (id_produto,))
            cursor.execute("""
                INSERT INTO historico_logs (usuario, acao, detalhe)
                VALUES (%s, 'Exclusão', %s)
            """, (session['usuario'], f"Apagado o produto {prod['nome']} (ID: {id_produto}) permanentemente."))
            mysql.connection.commit()
            flash("Produto removido definitivamente do estoque.", "success")
            return redirect(url_for('lobby'))
            
        elif botao_acao == 'salvar':
            nome = limpar_texto(request.form['nome'])
            area = request.form['area']
            quantidade = int(request.form['quantidade'])
            preco = float(request.form['preco'].replace(',', '.'))
            descricao = limpar_texto(request.form.get('descricao', ''))
            link_imagem = request.form.get('link_imagem', None)
            
            cursor.execute("""
                UPDATE estoque 
                SET nome = %s, area = %s, quantidade = %s, preco = %s, descricao = %s, link_midia = %s
                WHERE id_produto = %s
            """, (nome, area, quantidade, preco, descricao, link_imagem if link_imagem else None, id_produto))
            
            cursor.execute("""
                INSERT INTO historico_logs (usuario, acao, detalhe)
                VALUES (%s, 'Alteração', %s)
            """, (session['usuario'], f"Editou propriedades do item {nome} (ID: {id_produto})"))
            
            mysql.connection.commit()
            flash("Informações do material atualizadas!", "success")
            return redirect(url_for('lobby'))

    cursor.execute("SELECT id_produto, nome, area, quantidade, preco, descricao, link_midia as link_imagem FROM estoque WHERE id_produto = %s", (id_produto,))
    produto = cursor.fetchone()
    
    cursor.execute("SELECT id_produto, nome, preco FROM estoque")
    sugestoes = cursor.fetchall()
    return render_template('editar.html', produto=produto, sugestoes=sugestoes)

# ==========================================
# ROTAS DO PAINEL ADMINISTRATIVO 
# ==========================================

@app.route('/admin_panel', methods=['GET', 'POST'])
def admin_panel():
    if 'logged_in' not in session or not session.get('is_admin'):
        flash("Acesso restrito apenas a administradores!")
        return redirect(url_for('lobby'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_user':
            novo_usuario = request.form['novo_usuario'].strip()
            nova_senha = request.form['nova_senha']
            role = request.form['role']
            
            cursor.execute("SELECT * FROM usuarios WHERE login = %s", (novo_usuario,))
            if cursor.fetchone():
                flash("Erro: Este usuário já existe!", "error")
            else:
                hashed_password = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
                cursor.execute("INSERT INTO usuarios (login, senha, status, role) VALUES (%s, %s, 'ativo', %s)", (novo_usuario, hashed_password, role))
                cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Admin', %s)", (session['usuario'], f"Criou o usuário '{novo_usuario}' com a função '{role}'"))
                mysql.connection.commit()
                flash(f"Usuário '{novo_usuario}' cadastrado com sucesso!", "success")
                
        elif action in ['suspender', 'reativar']:
            alvo = request.form['usuario_alvo']
            novo_status = 'suspenso' if action == 'suspender' else 'ativo'
            
            if alvo == 'admin':
                flash("Erro: O usuário master 'admin' não pode ser suspenso!", "error")
            else:
                cursor.execute("UPDATE usuarios SET status = %s WHERE login = %s", (novo_status, alvo))
                cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Admin', %s)", (session['usuario'], f"Alterou o status do usuário '{alvo}' para '{novo_status}'"))
                mysql.connection.commit()
                flash(f"Status do usuário '{alvo}' alterado para {novo_status}!", "success")
                
        elif action == 'alterar_chave':
            nova_chave = request.form['nova_chave'].strip()
            cursor.execute("UPDATE config_admin SET chave_secundaria = %s WHERE id = 1", (nova_chave,))
            cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Admin', 'Alterou a chave mecânica secundária')", (session['usuario'],))
            mysql.connection.commit()
            flash("Chave mecânica secundária atualizada com sucesso!", "success")
            
        return redirect(url_for('admin_panel'))
        
    cursor.execute("SELECT login, status, role FROM usuarios WHERE login != %s", (session['usuario'],))
    lista_usuarios = cursor.fetchall()
    
    cursor.execute("SELECT chave_secundaria FROM config_admin WHERE id = 1")
    chave_atual = cursor.fetchone()
    
    cursor.execute("SELECT usuario, acao, detalhe, data_registro FROM historico_logs ORDER BY data_registro DESC LIMIT 100")
    lista_logs = cursor.fetchall()
    
    return render_template('admin.html', usuarios=lista_usuarios, logs=lista_logs, chave_mecanica=chave_atual)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)