# core/data_manager.py

import json
import os
import logging

# Configuração básica do logging para este módulo
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - (data_manager) - %(message)s')

# --- Variáveis Globais para Armazenar Dados Carregados ---
# Para os códigos HM da Tabela 00 a serem ignorados
codigos_hm_tabela00_a_ignorar_set = set()
hm_tabela00_carregados_com_sucesso = False

# Para o mapa de Unimeds
mapa_unimeds = {}
unimeds_carregadas = False

# --- Funções para Carregar Dados ---

def carregar_codigos_hm_tabela00_a_ignorar():
    """
    Carrega a lista de códigos de serviço HM da Tabela 00 a serem ignorados
    do arquivo config/ignore_00.json.
    Espera uma lista de objetos, onde cada objeto tem uma chave "Código".
    """
    global codigos_hm_tabela00_a_ignorar_set, hm_tabela00_carregados_com_sucesso
    hm_tabela00_carregados_com_sucesso = False # Reseta a flag no início

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, 'config', 'ignore_00.json') # Nome do arquivo atualizado

    logging.info(f"Tentando carregar códigos HM Tabela 00 a ignorar de: {config_path}")

    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                lista_de_objetos_json = json.load(f)
                
                if isinstance(lista_de_objetos_json, list):
                    temp_codigos = []
                    for item in lista_de_objetos_json:
                        if isinstance(item, dict) and "Código" in item:
                            temp_codigos.append(str(item["Código"]).strip())
                        else:
                            logging.warning(f"Item ignorado em '{os.path.basename(config_path)}' por não ser um dicionário com a chave 'Código': {item}")
                    codigos_hm_tabela00_a_ignorar_set = set(temp_codigos)
                    hm_tabela00_carregados_com_sucesso = True
                    logging.info(f"Sucesso! {len(codigos_hm_tabela00_a_ignorar_set)} códigos HM Tabela 00 a ignorar carregados de '{config_path}'.")
                else:
                    logging.error(f"Estrutura inesperada em '{config_path}'. Esperava uma lista de objetos, mas recebi {type(lista_de_objetos_json)}.")
                    codigos_hm_tabela00_a_ignorar_set = set()
        else:
            logging.error(f"Arquivo de configuração '{config_path}' não encontrado.")
            codigos_hm_tabela00_a_ignorar_set = set()

    except json.JSONDecodeError:
        logging.exception(f"Erro ao decodificar o JSON em: {config_path}")
        codigos_hm_tabela00_a_ignorar_set = set()
    except Exception as e:
        logging.exception(f"Erro inesperado ao carregar configurações de {config_path}: {e}")
        codigos_hm_tabela00_a_ignorar_set = set()

def carregar_dados_unimed():
    """
    Carrega os dados de mapeamento das Unimeds do arquivo config/unimed_map.json.
    """
    global mapa_unimeds, unimeds_carregadas
    unimeds_carregadas = False

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    map_path = os.path.join(base_dir, 'config', 'unimed_map.json')

    logging.info(f"Tentando carregar mapa de Unimeds de: {map_path}")
    try:
        if os.path.exists(map_path):
            with open(map_path, 'r', encoding='utf-8') as f:
                mapa_unimeds = json.load(f)
                if isinstance(mapa_unimeds, dict):
                    unimeds_carregadas = True
                    logging.info(f"{len(mapa_unimeds)} Unimeds carregadas do arquivo '{map_path}'.")
                else:
                    logging.error(f"Estrutura inesperada em '{map_path}'. Esperava um dicionário (objeto JSON), mas recebi {type(mapa_unimeds)}.")
                    mapa_unimeds = {}
        else:
            logging.error(f"Arquivo de mapa de Unimeds '{map_path}' não encontrado. Usando mapa vazio.")
            mapa_unimeds = {}
            
    except json.JSONDecodeError:
        logging.exception(f"Erro ao decodificar o JSON do mapa de Unimeds em: {map_path}")
        mapa_unimeds = {}
    except Exception as e:
        logging.exception(f"Erro inesperado ao carregar mapa de Unimeds de {map_path}: {e}")
        mapa_unimeds = {}

# --- Funções para Acessar Dados ---

def get_codigos_hm_tabela00_a_ignorar():
    """Retorna o conjunto de códigos de serviço HM da Tabela 00 a serem ignorados."""
    return codigos_hm_tabela00_a_ignorar_set

def is_hm_tabela00_carregados():
    """Retorna True se os dados dos HM da Tabela 00 a ignorar foram carregados com sucesso."""
    return hm_tabela00_carregados_com_sucesso

def is_unimeds_carregadas():
    """Retorna True se os dados das Unimeds foram carregados com sucesso."""
    return unimeds_carregadas

def obter_nome_unimed(codigo_unimed):
    """
    Retorna o nome da Unimed com base no código.
    """
    if not unimeds_carregadas:
        logging.warning("Tentativa de obter nome da Unimed, mas os dados das Unimeds não foram carregados.")
        return f"MAPA UNIMEDS NÃO CARREGADO (Cód: {str(codigo_unimed).strip()})"

    codigo_str = str(codigo_unimed).strip()
    nome = mapa_unimeds.get(codigo_str, f"CÓDIGO {codigo_str} NÃO MAPEADO")
    return nome