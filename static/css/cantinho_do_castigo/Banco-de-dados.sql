-- =====================================================
-- 1. CRIAÇÃO DO BANCO DE DADOS (SCHEMA)
-- =====================================================
CREATE DATABASE IF NOT EXISTS almoxarifado_db 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE almoxarifado_db;

-- =====================================================
-- 2. LIMPEZA DE ESTRUTURAS ANTIGAS (Garante a atualização)
-- =====================================================
-- Remove a tabela de mídias antiga se ela ainda existir
DROP TABLE IF EXISTS midia_produtos;

-- Remove a tabela estoque antiga para recriá-la com a nova coluna
DROP TABLE IF EXISTS estoque;

-- Remove as outras tabelas para garantir uma instalação limpa do zero
DROP TABLE IF EXISTS usuarios;
DROP TABLE IF EXISTS config_admin;
DROP TABLE IF EXISTS historico_logs;


-- =====================================================
-- 3. CRIAÇÃO DAS TABELAS ATUALIZADAS
-- =====================================================

-- Tabela de Usuários/Funcionários (Já com a coluna 'role' inclusa)
CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    login VARCHAR(50) NOT NULL UNIQUE,
    senha VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'ativo', -- 'ativo', 'suspenso_temp', 'suspenso_perm'
    role VARCHAR(20) NOT NULL DEFAULT 'user'
);

-- Tabela de Configuração e Chave Secundária do Administrador
CREATE TABLE config_admin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    chave_secundaria VARCHAR(50) NOT NULL DEFAULT '1234'
);

-- Tabela do Estoque de Produtos (Agora com a coluna link_midia oficializada)
CREATE TABLE estoque (
    id_produto VARCHAR(5) PRIMARY KEY, -- ID de 5 dígitos conforme regra de classes
    nome VARCHAR(100) NOT NULL,
    area VARCHAR(50) NOT NULL,         -- 'Geral', 'Mecânica', 'Elétrica', etc.
    quantidade INT NOT NULL DEFAULT 0,
    descricao TEXT,
    link_midia VARCHAR(500) DEFAULT NULL -- Nova coluna integrada aqui!
);

-- Tabela do Histórico de Alterações (Logs de Entrada e Saída)
CREATE TABLE historico_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(50) NOT NULL,
    acao VARCHAR(50) NOT NULL,        -- 'Inserção' ou 'Retirada'
    detalhe TEXT NOT NULL,
    data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
);


-- =====================================================
-- 4. CARGA DE DADOS INICIAIS (Para testes no sistema)
-- =====================================================

-- Inserindo os usuários padrão (admin e user1)
INSERT INTO usuarios (login, senha, status, role) VALUES 
('admin', 'admin', 'ativo', 'admin'),
('user1', '123', 'ativo', 'user');

-- Inserindo a chave secundária padrão do Administrador
INSERT INTO config_admin (chave_secundaria) VALUES 
('1234');

-- Inserindo itens iniciais no estoque (com o campo de mídia pronto)
INSERT INTO estoque (id_produto, nome, area, quantidade, descricao, link_midia) VALUES 
('00001', 'Vassoura', 'Geral', 10, 'Utilidade geral de limpeza', NULL),
('10001', 'Alicate', 'Mecânica', 5, 'Alicate de pressão', NULL),
('20001', 'Chave de Fenda', 'Elétrica', 8, 'Isolada 1000V', NULL);


-- =====================================================
-- 5. CONSULTAS DE VERIFICAÇÃO
-- =====================================================
SELECT * FROM estoque;
SELECT * FROM config_admin;
SELECT * FROM historico_logs;
SELECT * FROM usuarios;