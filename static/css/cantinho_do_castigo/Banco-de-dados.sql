-- 1. Criação do Banco de Dados
CREATE DATABASE IF NOT EXISTS almoxarifado_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE almoxarifado_db;

-- 2. Tabela de Estoque / Produtos
CREATE TABLE IF NOT EXISTS estoque (
    id_produto VARCHAR(5) NOT NULL,
    nome VARCHAR(100) NOT NULL,
    area VARCHAR(50) NOT NULL,
    quantidade INT NOT NULL DEFAULT 0,
    descricao VARCHAR(255) NULL,
    link_midia VARCHAR(500) NULL,
    PRIMARY KEY (id_produto)
) ENGINE=InnoDB;

-- 3. Tabela de Usuários (Configurada para Hashes de 60 caracteres do Bcrypt)
CREATE TABLE IF NOT EXISTS usuarios (
    login VARCHAR(50) NOT NULL,
    senha VARCHAR(255) NOT NULL, -- Espaço seguro de 255 caracteres
    status VARCHAR(20) NOT NULL DEFAULT 'ativo',
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    PRIMARY KEY (login)
) ENGINE=InnoDB;

-- 4. Tabela de Configurações Administrativas
CREATE TABLE IF NOT EXISTS config_admin (
    id INT AUTO_INCREMENT,
    chave_secundaria VARCHAR(255) NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB;

-- 5. Tabela de Histórico / Logs do Sistema
CREATE TABLE IF NOT EXISTS historico_logs (
    id INT AUTO_INCREMENT,
    usuario VARCHAR(50) NOT NULL,
    acao VARCHAR(50) NOT NULL,
    detalhe TEXT NOT NULL,
    data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- INSERÇÃO DE REGISTROS INICIAIS OBRIGATÓRIOS
-- -----------------------------------------------------------------------------

-- Define a Chave Mestra para o Painel Administrativo
-- Altere 'SUA_CHAVE_MESTRA_AQUI' para o código que você usa na verificação secundária
INSERT INTO config_admin (chave_secundaria) 
VALUES ('ROCAMBOLE');

-- Garante a remoção de qualquer usuário antigo 'admin' para evitar conflitos
DELETE FROM usuarios WHERE login = 'admin';

-- Criação do Administrador Padrão
-- O hash abaixo corresponde estritamente à senha em texto puro: admin
INSERT INTO usuarios (login, senha, status, role) #senha = admin
VALUES ('admin', '$2a$12$TyKbVE6G425lA7ko/IgwoOcR.Uc4RCbcvGj/ftZkopSNhhlelM8Zi', 'ativo', 'admin');

INSERT INTO usuarios (login, senha, status, role) #senha = 123
VALUES ('andre', '$2a$12$iaj8/rlNnch3bV0WlT/BNO.nQrFOUgoJ7KvCgsLdaaO/hySJbDgSa', 'ativo', 'admin');

USE almoxarifado_db;

UPDATE usuarios 
SET senha = '$2a$12$TyKbVE6G425lA7ko/IgwoOcR.Uc4RCbcvGj/ftZkopSNhhlelM8Zi'
WHERE login = 'admin';


SELECT * FROM estoque;
SELECT * FROM config_admin;
SELECT * FROM historico_logs;
SELECT * FROM usuarios;