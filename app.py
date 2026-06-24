import os
import re
import unicodedata
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
import bcrypt
import MySQLdb.cursors

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configurações do Banco de Dados
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  # Deixe vazio para XAMPP ou preencha com a sua senha
app.config['MYSQL_DB'] = 'almoxarifado_db'

mysql = MySQL(app)

# -----------------------------------------------------------------------------
# FUNÇÕES AUXILIARES / TRATAMENTO DE TEXTO E ID DINÂMICO
# -----------------------------------------------------------------------------
def limpar_texto(texto):
    """Remove acentos e deixa apenas a primeira letra da string em maiúscula."""
    if not texto:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', texto)
    texto_sem_acento = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    texto_limpo = texto_sem_acento.strip().lower()
    return texto_limpo.capitalize()

def gerar_proximo_id(area):
    """Gera o próximo ID de 5 dígitos preenchendo lacunas deixadas por exclusões."""
    prefixos = {'Geral': '0', 'Mecânica': '1', 'Elétrica': '2'}
    prefixo = prefixos.get(area, '0')
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT id_produto FROM estoque 
        WHERE id_produto LIKE %s 
        ORDER BY id_produto ASC
    """, (prefixo + '%',))
    ids_existentes = [int(row['id_produto']) for row in cursor.fetchall()]
    
    inicio_sequencia = int(prefixo + "0001")
    
    proximo_numero = inicio_sequencia
    while proximo_numero in ids_existentes:
        proximo_numero += 1
        
    return f"{proximo_numero:05d}"

# -----------------------------------------------------------------------------
# ROTAS DE AUTENTICAÇÃO
# -----------------------------------------------------------------------------
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
            
            # Validação robusta codificando string para bytes antes da comparação
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

# -----------------------------------------------------------------------------
# VISÃO GERAL: CONSULTA DE ESTOQUE (LOBBY)
# -----------------------------------------------------------------------------
@app.route('/lobby')
@app.route('/lobby/<area_filtro>')
def lobby(area_filtro='Todos'):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if area_filtro == 'Todos':
        cursor.execute("""
            SELECT id_produto, nome, area, quantidade, descricao, 
            CASE WHEN link_midia IS NOT NULL AND link_midia != '' THEN 1 ELSE 0 END as possui_imagem 
            FROM estoque ORDER BY id_produto ASC
        """)
    else:
        cursor.execute("""
            SELECT id_produto, nome, area, quantidade, descricao, 
            CASE WHEN link_midia IS NOT NULL AND link_midia != '' THEN 1 ELSE 0 END as possui_imagem 
            FROM estoque WHERE area = %s ORDER BY id_produto ASC
        """, (area_filtro,))
        
    itens_estoque = cursor.fetchall()
    return render_template('lobby.html', estoque=itens_estoque, area_atual=area_filtro)

@app.route('/api/obter_link_imagem/<id_produto>')
def obter_link_imagem(id_produto):
    if 'logged_in' not in session:
        return jsonify({'error': 'Não autorizado'}), 401
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT link_midia FROM estoque WHERE id_produto = %s", (id_produto,))
    produto = cursor.fetchone()
    
    if produto:
        return jsonify({'link_url': produto['link_midia']})
    return jsonify({'link_url': None})

# -----------------------------------------------------------------------------
# MOVIMENTAÇÕES E EDIÇÃO DE PRODUTOS
# -----------------------------------------------------------------------------
@app.route('/insercao', methods=['GET', 'POST'])
def insercao():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if request.method == 'POST':
        nome = limpar_texto(request.form['nome'])
        area = request.form['area']
        quantidade = int(request.form['quantidade'])
        descricao = limpar_texto(request.form.get('descricao', ''))
        link_imagem = request.form.get('link_imagem', None)
        
        cursor.execute("SELECT * FROM estoque WHERE nome = %s AND area = %s", (nome, area))
        produto_existente = cursor.fetchone()
        
        if produto_existente:
            nova_qtd = produto_existente['quantidade'] + quantidade
            cursor.execute("UPDATE estoque SET quantidade = %s WHERE id_produto = %s", (nova_qtd, produto_existente['id_produto']))
            id_final = produto_existente['id_produto']
        else:
            id_final = gerar_proximo_id(area)
            cursor.execute("""
                INSERT INTO estoque (id_produto, nome, area, quantidade, descricao, link_midia)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (id_final, nome, area, quantidade, descricao, link_imagem if link_imagem else None))
            
        cursor.execute("""
            INSERT INTO historico_logs (usuario, acao, detalhe)
            VALUES (%s, 'Inserção', %s)
        """, (session['usuario'], f"Adicionado {quantidade} un do item {nome} (ID: {id_final})"))
        
        mysql.connection.commit()
        flash(f"Entrada do item '{nome}' registrada com sucesso!", "success")
        return redirect(url_for('lobby'))
        
    cursor.execute("SELECT DISTINCT nome FROM estoque")
    sugestoes = [row['nome'] for row in cursor.fetchall()]
    
    # Corrigido aqui para 'insercao.html' (sem acento)
    return render_template('insercao.html', sugestoes=sugestoes)

@app.route('/retirada', methods=['GET', 'POST'])
def retirada():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if request.method == 'POST':
        id_produto = request.form['id_produto']
        quantidade_retirar = int(request.form['quantidade'])
        
        cursor.execute("SELECT * FROM estoque WHERE id_produto = %s", (id_produto,))
        produto = cursor.fetchone()
        
        if produto and produto['quantidade'] >= quantidade_retirar:
            nova_qtd = produto['quantidade'] - quantidade_retirar
            cursor.execute("UPDATE estoque SET quantidade = %s WHERE id_produto = %s", (nova_qtd, id_produto))
            
            cursor.execute("""
                INSERT INTO historico_logs (usuario, acao, detalhe)
                VALUES (%s, 'Retirada', %s)
            """, (session['usuario'], f"Retirado {quantidade_retirar} un do item {produto['nome']} (ID: {id_produto})"))
            
            mysql.connection.commit()
            flash("Baixa efetuada com sucesso!", "success")
            return redirect(url_for('lobby'))
        else:
            flash("Erro: Quantidade indisponível ou produto inexistente!", "error")
            
    cursor.execute("SELECT id_produto, nome, quantidade FROM estoque WHERE quantidade > 0 ORDER BY id_produto ASC")
    produtos_disponiveis = cursor.fetchall()
    return render_template('retirada.html', estoque=produtos_disponiveis)

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
            descricao = limpar_texto(request.form.get('descricao', ''))
            link_imagem = request.form.get('link_imagem', None)
            
            cursor.execute("""
                UPDATE estoque 
                SET nome = %s, area = %s, quantidade = %s, descricao = %s, link_midia = %s
                WHERE id_produto = %s
            """, (nome, area, quantidade, descricao, link_imagem if link_imagem else None, id_produto))
            
            cursor.execute("""
                INSERT INTO historico_logs (usuario, acao, detalhe)
                VALUES (%s, 'Alteração', %s)
            """, (session['usuario'], f"Editou propriedades do item {nome} (ID: {id_produto})"))
            
            mysql.connection.commit()
            flash("Informações do material atualizadas!", "success")
            return redirect(url_for('lobby'))

    cursor.execute("SELECT id_produto, nome, area, quantidade, descricao, link_midia as link_imagem FROM estoque WHERE id_produto = %s", (id_produto,))
    produto = cursor.fetchone()
    
    cursor.execute("SELECT DISTINCT nome FROM estoque")
    sugestoes = [row['nome'] for row in cursor.fetchall()]
    
    return render_template('editar.html', produto=produto, sugestoes=sugestoes)

# -----------------------------------------------------------------------------
# PAINEL ADMINISTRATIVO
# -----------------------------------------------------------------------------
@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'logged_in' not in session or not session.get('is_admin'):
        flash("Acesso restrito apenas a administradores geral!")
        return redirect(url_for('lobby'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if request.method == 'POST':
        acao = request.form.get('acao')
        verificacao_seguranca = request.form.get('verificacao_seguranca')
        
        cursor.execute("SELECT chave_secundaria FROM config_admin LIMIT 1")
        chave_mestra = cursor.fetchone()['chave_secundaria']
        
        if verificacao_seguranca != chave_mestra:
            flash("Chave de Verificação Secundária (Mestra) Inválida! Operação cancelada.", "error")
            return redirect(url_for('admin_panel'))
            
        funcionario = request.form.get('funcionario')
        
        if acao == 'cadastrar':
            nova_senha = request.form.get('nova_senha')
            tipo_permissao = request.form.get('tipo_permissao', 'user')
            
            salt = bcrypt.gensalt()
            senha_hash = bcrypt.hashpw(nova_senha.encode('utf-8'), salt).decode('utf-8')
            
            try:
                cursor.execute("""
                    INSERT INTO usuarios (login, senha, status, role)
                    VALUES (%s, %s, 'ativo', %s)
                """, (funcionario, senha_hash, tipo_permissao))
                
                cursor.execute("""
                    INSERT INTO historico_logs (usuario, acao, detalhe)
                    VALUES (%s, 'Admin', %s)
                """, (session['usuario'], f"Criou o utilizador '{funcionario}' com perfil '{tipo_permissao}'"))
                mysql.connection.commit()
                flash(f"Perfil de '{funcionario}' criado com sucesso!", "success")
            except:
                flash("Erro: Esse nome de utilizador já se encontra registrado.", "error")
                
        elif acao == 'alterar_dados':
            nova_senha = request.form.get('nova_senha')
            if nova_senha and nova_senha.strip() != "":
                salt = bcrypt.gensalt()
                senha_hash_nova = bcrypt.hashpw(nova_senha.encode('utf-8'), salt).decode('utf-8')
                cursor.execute("UPDATE usuarios SET senha = %s WHERE login = %s", (senha_hash_nova, funcionario))
                flash(f"Senha de {funcionario} redefinida com segurança.", "success")
                mysql.connection.commit()
                
        elif acao == 'restringir_temp':
            tempo_bloqueio = request.form.get('tempo_bloqueio', 'Não especificado')
            cursor.execute("UPDATE usuarios SET status = 'suspenso_temp' WHERE login = %s", (funcionario,))
            cursor.execute("""
                INSERT INTO historico_logs (usuario, acao, detalhe)
                VALUES (%s, 'Admin', %s)
            """, (session['usuario'], f"Bloqueou temporariamente o usuário {funcionario}. Tempo: {tempo_bloqueio}"))
            mysql.connection.commit()
            flash(f"Usuário {funcionario} suspenso temporariamente ({tempo_bloqueio}).", "success")
            
        elif acao == 'excluir':
            cursor.execute("DELETE FROM usuarios WHERE login = %s", (funcionario,))
            cursor.execute("""
                INSERT INTO historico_logs (usuario, acao, detalhe)
                VALUES (%s, 'Admin', %s)
            """, (session['usuario'], f"Excluiu permanentemente o usuário {funcionario}"))
            mysql.connection.commit()
            flash(f"Usuário {funcionario} deletado permanentemente do sistema.", "success")

    cursor.execute("SELECT login, status, role FROM usuarios")
    usuarios_lista = cursor.fetchall()
    
    cursor.execute("SELECT usuario, acao, detalhe, data_registro FROM historico_logs ORDER BY data_registro DESC")
    historico_logs_lista = cursor.fetchall()
    
    return render_template('admin.html', usuarios=usuarios_lista, historico=historico_logs_lista)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)