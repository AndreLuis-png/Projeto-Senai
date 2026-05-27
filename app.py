from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql
import pymysql.cursors
import unicodedata  # 🌟 Biblioteca nativa para remoção de acentos

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


# 🛡️ FUNÇÃO PADRONIZADORA (Remove acentos, espaços extras e padroniza em Maiúsculas)
def normalizar_nome(texto):
    if not texto:
        return ""
    # Remove espaços inúteis nas pontas
    texto = texto.strip()
    # Separa os acentos das letras (Forma NFD)
    texto_nfd = unicodedata.normalize('NFD', texto)
    # Filtra mantendo apenas o que não for marca de acentuação (Mn = Mark, Nonspacing)
    texto_sem_acento = "".join(c for c in texto_nfd if unicodedata.category(c) != 'Mn')
    # Retorna em Letras Maiúsculas para total igualdade no banco de dados
    return texto_sem_acento.upper()


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
    
    if area_filtrada and area_filtrada != 'Todos':
        cursor.execute(
            "SELECT id_produto, nome, area, quantidade, descricao FROM estoque WHERE area = %s ORDER BY id_produto ASC", 
            (area_filtrada,)
        )
    else:
        cursor.execute("SELECT id_produto, nome, area, quantidade, descricao FROM estoque ORDER BY id_produto ASC")
        
    estoque = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('lobby.html', estoque=estoque, area_atual=area_filtrada)

# 📥 ENTRADA DE MATERIAL (LÓGICA COM PADRONIZAÇÃO COMPLETA)
@app.route('/insercao', methods=['GET', 'POST'])
def insercao():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        # 🌟 Aplica a normalização purificando o texto enviado
        nome = normalizar_nome(request.form.get('nome'))
        area_solicitada = request.form.get('area')
        quantidade = int(request.form.get('quantidade', 0))
        descricao = request.form.get('descricao', '').strip()[:255]
        
        if not nome:
            flash("Nome do produto inválido!", "error")
            return redirect(url_for('insercao'))

        conn = mysql.connection
        cursor = conn.cursor()
        
        # Busca direta e segura (ambos estarão em maiúsculas e sem acento)
        cursor.execute("SELECT id_produto, area, quantidade FROM estoque WHERE nome = %s", (nome,))
        item_existente = cursor.fetchone()
        
        if item_existente:
            area_real = item_existente['area']
            nova_qtd_total = item_existente['quantidade'] + quantidade
            cursor.execute("UPDATE estoque SET quantidade = %s WHERE id_produto = %s", (nova_qtd_total, item_existente['id_produto']))
            
            detalhe_log = f"Reabasteceu '{nome}' (ID: {item_existente['id_produto']}). Vinculado automaticamente ao setor original [{area_real}]. Adicionado: {quantidade} un. Novo Saldo: {nova_qtd_total} un."
            cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Inserção', %s)", (session['usuario'], detalhe_log))
            
            if area_solicitada != area_real:
                flash(f"O item '{nome}' já possui cadastro no setor [{area_real}]. A quantidade foi somada lá para evitar duplicados!", "success")
            else:
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
                
                flash(f"O produto '{antigo['nome']}' foi excluído permanentemente para correção!", "success")
                cursor.close()
                conn.close()
                return redirect(url_for('lobby'))
            
            else:
                # 🌟 Aplica a normalização no nome modificado também
                novo_nome = normalizar_nome(request.form.get('nome'))
                nova_area = request.form.get('area')
                nova_qtd = int(request.form.get('quantidade', 0))
                nova_descricao = request.form.get('descricao', '').strip()[:255]
                
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
                
                detalhes_mudanca = f"Editou item ID {id_produto}. Antigo: [{antigo['nome']}, Qtd: {antigo['quantidade']}]. Novo: [ID: {id_final}, {novo_nome}, Qtd: {nova_qtd}]."
                cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Alteração', %s)", (session['usuario'], detalhes_mudanca))
                flash(f"Informações do item '{novo_nome}' atualizadas com sucesso!", "success")
                
        cursor.close()
        conn.close()
        return redirect(url_for('lobby'))
        
    cursor.execute("SELECT * FROM estoque WHERE id_produto = %s", (id_produto,))
    produto = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not produto:
        flash("Produto não encontrado!", "error")
        return redirect(url_for('lobby'))
        
    sugestoes = obter_nomes_produtos()
    return render_template('editar.html', produto=produto, sugestoes=sugestoes)

# 📤 RETIRADA / BAIXA DE MATERIAL
@app.route('/retirada', methods=['GET', 'POST'])
def retirada():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    conn = mysql.connection
    cursor = conn.cursor()
    
    if request.method == 'POST':
        # 🌟 Normaliza a busca para garantir que case com o registro limpo do banco
        nome_digitado = normalizar_nome(request.form.get('nome_item_busca'))
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
                    cursor.execute("UPDATE usuarios SET status = 'suspenso_temp' WHERE login = %s", (funcionario,))
                    flash(f'Usuário {funcionario} suspenso temporariamente.', 'success')
                elif acao == 'restringir_perm':
                    cursor.execute("UPDATE usuarios SET status = 'suspenso_perm' WHERE login = %s", (funcionario,))
                    flash(f'Usuário {funcionario} banido permanentemente.', 'success')
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