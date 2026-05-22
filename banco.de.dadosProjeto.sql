-- 1. Criação do Banco de Dados (Schema)
CREATE DATABASE IF NOT EXISTS almoxarifado_db 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE almoxarifado_db;

-- 2. Tabela de Usuários/Funcionários
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    login VARCHAR(50) NOT NULL UNIQUE,
    senha VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'ativo' -- 'ativo', 'suspenso_temp', 'suspenso_perm'
);

-- 3. Tabela de Configuração e Chave Secundária do Administrador
CREATE TABLE IF NOT EXISTS config_admin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    chave_secundaria VARCHAR(50) NOT NULL DEFAULT '1234'
);

-- 4. Tabela do Estoque de Produtos
CREATE TABLE IF NOT EXISTS estoque (
    id_produto VARCHAR(5) PRIMARY KEY, -- ID de 5 dígitos conforme sua regra de classes
    nome VARCHAR(100) NOT NULL,
    area VARCHAR(50) NOT NULL,         -- 'Geral', 'Mecânica', 'Elétrica', etc.
    quantidade INT NOT NULL DEFAULT 0,
    descricao TEXT
);

-- 5. Tabela do Histórico de Alterações (Logs de Entrada e Saída)
CREATE TABLE IF NOT EXISTS historico_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(50) NOT NULL,
    acao VARCHAR(50) NOT NULL,        -- 'Inserção' ou 'Retirada'
    detalhe TEXT NOT NULL,
    data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Registra automaticamente a data/hora da ação
);

-- -----------------------------------------------------
-- CARGA DE DADOS INICIAIS (Para testes no sistema)
-- -----------------------------------------------------

-- Inserindo os usuários padrão (Teóricos, sem criptografia por enquanto)
INSERT INTO usuarios (login, senha, status) VALUES 
('admin', 'admin', 'ativo'),
('user1', '123', 'ativo');

-- Inserindo a chave secundária padrão do Administrador
INSERT INTO config_admin (chave_secundaria) VALUES 
('1234');

-- Inserindo itens iniciais respeitando a regra do primeiro dígito do ID
-- 0 = Geral, 1 = Mecânica, 2 = Elétrica
INSERT INTO estoque (id_produto, nome, area, quantidade, descricao) VALUES 
('00001', 'Vassoura', 'Geral', 10, 'Utilidade geral de limpeza'),
('10001', 'Alicate', 'Mecânica', 5, 'Alicate de pressão'),
('20001', 'Chave de Fenda', 'Elétrica', 8, 'Isolada 1000V');

SELECT * FROM estoque
SELECT * FROM config_admin
SELECT * FROM historico_logs
SELECT * FROM usuarios

