from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'

# --- CONFIGURAÇÃO DO BANCO DE DADOS (MySQL) ---
# Substitua com os módulos do driver de banco de dados que você utiliza no projeto
# Exemplo padrão utilizando Flask-MysqlDB:
# from flask_mysqldb import MySQL
# mysql = MySQL(app)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'sua_senha'
app.config['MYSQL_DB'] = 'nome_do_banco'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor' # Retorna registros como dicionários

# Mock/Simulador do objeto mysql caso precise testar a estrutura localmente sem o driver instalado
class MySQL_Dummy:
    class Connection:
        def cursor(self):
            return DummyCursor()
    def __init__(self, app=None):
        self.connection = self.Connection()
mysql = MySQL_Dummy()

class DummyCursor:
    def execute(self, query, params=None): pass
    def fetchall(self): return []
    def close(self): pass
# --- FIM CONFIGURAÇÃO ---


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        admin_mode = 'admin_mode' in request.form
        
        # Insira aqui a sua lógica de validação de login do banco de dados
        if usuario and senha:
            session['usuario'] = usuario
            session['is_admin'] = admin_mode
            return redirect(url_for('lobby'))
        else:
            flash('Usuário ou senha inválidos.')
    return render_template('login.html')


@app.route('/lobby')
def lobby():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    area_filtrada = request.args.get('area_filtro', 'Todos')
    cursor = mysql.connection.cursor()
    
    if area_filtrada and area_filtrada != 'Todos':
        # Busca filtrada por categoria E sempre ordenada de forma crescente por ID
        cursor.execute(
            "SELECT id_produto, nome, area, quantidade, descricao FROM produtos WHERE area = %s ORDER BY id_produto ASC", 
            (area_filtrada,)
        )
    else:
        # Busca global ordenada sequencialmente por ID
        cursor.execute("SELECT id_produto, nome, area, quantidade, descricao FROM produtos ORDER BY id_produto ASC")
        
    estoque = cursor.fetchall()
    cursor.close()
    
    return render_template('lobby.html', estoque=estoque, area_atual=area_filtrada)


@app.route('/insercao', methods=['GET', 'POST'])
def insercao():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        nome = request.form.get('nome')
        area = request.form.get('area')
        quantidade = request.form.get('quantidade')
        descricao = request.form.get('descricao')
        
        # Insira aqui a sua lógica de geração de ID dinâmico e inserção no banco
        cursor = mysql.connection.cursor()
        # Exemplo básico: cursor.execute("INSERT INTO produtos...")
        cursor.close()
        
        return redirect(url_for('lobby'))
        
    return render_template('insercao.html')


@app.route('/retirada', methods=['GET', 'POST'])
def retirada():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id_produto, nome, quantidade FROM produtos ORDER BY id_produto ASC")
    estoque = cursor.fetchall()
    
    if request.method == 'POST':
        item_id = request.form.get('item_id')
        quantidade_retirar = int(request.form.get('quantidade', 0))
        
        # Insira aqui a validação de quantidade e a query de UPDATE de estoque
        cursor.close()
        return redirect(url_for('lobby'))
        
    cursor.close()
    return render_template('retirada.html', estoque=estoque)


@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'usuario' not in session or not session.get('is_admin'):
        return redirect(url_for('lobby'))
        
    cursor = mysql.connection.cursor()
    
    # Simulações de buscas do painel admin
    cursor.execute("SELECT login, status, senha FROM usuarios")
    usuarios = cursor.fetchall()
    
    cursor.execute("SELECT usuario, acao, detalhe FROM logs ORDER BY id_log DESC")
    historico = cursor.fetchall()
    cursor.close()
    
    if request.method == 'POST':
        # Gerencie aqui as ações enviadas pelo formulário do Administrador
        pass
        
    return render_template('admin.html', usuarios=usuarios, historico=historico)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)