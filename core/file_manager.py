# core/file_manager.py

import os
import glob
import shutil
import zipfile
import tempfile
import logging # Garanta que logging esteja importado no início

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - (file_manager) - %(message)s')

def listar_arquivos_zip(caminho_pasta):
    """
    Lista todos os arquivos .zip em uma pasta especificada.
    Retorna uma lista de caminhos completos para os arquivos .zip.
    """
    if not os.path.isdir(caminho_pasta):
        logging.error(f"O caminho '{caminho_pasta}' não é uma pasta válida.")
        return []

    padrao_busca = os.path.join(caminho_pasta, "*.zip")
    lista_zips = glob.glob(padrao_busca)
    return lista_zips

def criar_pasta_backup(pasta_raiz_faturas):
    """
    Cria uma subpasta chamada 'Backup' dentro da pasta raiz das faturas, se não existir.
    Retorna o caminho completo para a pasta de backup, ou None se falhar.
    """
    pasta_backup = os.path.join(pasta_raiz_faturas, "Backup")
    try:
        if not os.path.exists(pasta_backup):
            os.makedirs(pasta_backup)
        return pasta_backup
    except Exception as e:
        logging.error(f"Não foi possível criar a pasta de backup '{pasta_backup}'. Erro: {e}")
        return None

def criar_pasta_raiz_correcao_xml(pasta_raiz_faturas):
    """
    Cria uma subpasta chamada 'Correção XML' dentro da pasta raiz das faturas, se não existir.
    Retorna o caminho completo para a pasta 'Correção XML', ou None se falhar.
    """
    pasta_correcao_xml = os.path.join(pasta_raiz_faturas, "Correção XML")
    try:
        if not os.path.exists(pasta_correcao_xml):
            os.makedirs(pasta_correcao_xml)
        return pasta_correcao_xml
    except Exception as e:
        logging.error(f"Não foi possível criar a pasta raiz 'Correção XML' em '{pasta_correcao_xml}'. Erro: {e}")
        return None

def fazer_backup_fatura(caminho_fatura_original, caminho_pasta_backup):
    """
    Copia um arquivo de fatura para a pasta de backup.
    Retorna True se o backup for bem-sucedido, False caso contrário.
    """
    if not os.path.isfile(caminho_fatura_original):
        logging.error(f"Arquivo original '{caminho_fatura_original}' não encontrado para backup.")
        return False
    if not os.path.isdir(caminho_pasta_backup):
        logging.error(f"Pasta de backup '{caminho_pasta_backup}' não encontrada.")
        return False

    nome_arquivo = os.path.basename(caminho_fatura_original)
    caminho_destino_backup = os.path.join(caminho_pasta_backup, nome_arquivo)

    try:
        if os.path.exists(caminho_destino_backup):
            logging.info(f"Backup de '{nome_arquivo}' já existe. Nenhuma ação necessária.")
            return True
        shutil.copy2(caminho_fatura_original, caminho_destino_backup)
        return True
    except Exception as e:
        logging.error(f"Falha ao copiar '{nome_arquivo}' para backup. Erro: {e}")
        return False

def extrair_xml_fatura_do_zip(caminho_zip, pasta_destino_extracao):
    """
    Extrai o arquivo .051 (XML da fatura) de dentro de um arquivo .zip.
    """
    nome_base_zip, _ = os.path.splitext(os.path.basename(caminho_zip))
    nome_arquivo_xml_interno_esperado = nome_base_zip + ".051"
    caminho_completo_xml_extraido = os.path.join(pasta_destino_extracao, nome_arquivo_xml_interno_esperado)

    try:
        with zipfile.ZipFile(caminho_zip, 'r') as arquivo_zip_aberto:
            lista_arquivos_no_zip = arquivo_zip_aberto.namelist()
            arquivo_xml_para_extrair = None

            if nome_arquivo_xml_interno_esperado in lista_arquivos_no_zip:
                arquivo_xml_para_extrair = nome_arquivo_xml_interno_esperado
            else:
                for nome_no_zip in lista_arquivos_no_zip:
                    if nome_no_zip.lower().endswith(".051"):
                        logging.info(f"Nome exato '{nome_arquivo_xml_interno_esperado}' não encontrado em '{os.path.basename(caminho_zip)}'. Usando alternativo '{nome_no_zip}'.")
                        arquivo_xml_para_extrair = nome_no_zip
                        caminho_completo_xml_extraido = os.path.join(pasta_destino_extracao, arquivo_xml_para_extrair)
                        break

            if arquivo_xml_para_extrair:
                arquivo_zip_aberto.extract(arquivo_xml_para_extrair, path=pasta_destino_extracao)
                return caminho_completo_xml_extraido
            else:
                logging.error(f"Nenhum arquivo .051 (ex: '{nome_arquivo_xml_interno_esperado}') encontrado dentro de '{os.path.basename(caminho_zip)}'.")
                return None
    except zipfile.BadZipFile:
        logging.error(f"Arquivo '{os.path.basename(caminho_zip)}' não é um ZIP válido ou está corrompido.")
        return None
    except Exception as e:
        logging.exception(f"Falha ao extrair de '{os.path.basename(caminho_zip)}'. Erro: {e}")
        return None

def remover_arquivo_se_existe(caminho_arquivo):
    """Remove um arquivo se ele existir."""
    try:
        if caminho_arquivo and os.path.exists(caminho_arquivo) and os.path.isfile(caminho_arquivo):
            os.remove(caminho_arquivo)
            return True
    except Exception as e:
        logging.warning(f"Não foi possível remover o arquivo '{os.path.basename(caminho_arquivo)}'. Erro: {e}")
    return False

def organizar_faturas_por_auditor(plano_distribuicao, pasta_base_onde_faturas_estao, pasta_base_para_distribuicao):
    if not plano_distribuicao:
        logging.error("Plano de distribuição está vazio. Nada a organizar.")
        return False, {}

    caminho_pasta_distribuicao_principal = os.path.join(pasta_base_para_distribuicao, "Distribuição")
    status_movimentacao = {}

    try:
        if not os.path.exists(caminho_pasta_distribuicao_principal):
            os.makedirs(caminho_pasta_distribuicao_principal)
    except Exception as e:
        logging.critical(f"Não foi possível criar a pasta 'Distribuição' em '{caminho_pasta_distribuicao_principal}'. Erro: {e}")
        return False, {}

    sucesso_geral = True
    for nome_auditor, dados_auditor in plano_distribuicao.items():
        status_auditor = {'movidos': 0, 'erros': 0, 'avisos_nao_encontrados': 0}
        # Nome da pasta do auditor, substituindo caracteres problemáticos
        nome_pasta_auditor_seguro = nome_auditor.replace(' ', '_').replace('.', '')
        caminho_pasta_auditor = os.path.join(caminho_pasta_distribuicao_principal, nome_pasta_auditor_seguro)

        try:
            if not os.path.exists(caminho_pasta_auditor):
                os.makedirs(caminho_pasta_auditor)
        except Exception as e:
            logging.error(f"Não foi possível criar pasta para o auditor '{nome_auditor}' em '{caminho_pasta_auditor}'. Erro: {e}")
            status_auditor['erros'] += len(dados_auditor.get('faturas', []))
            sucesso_geral = False
            status_movimentacao[nome_auditor] = status_auditor
            continue

        for fatura_info in dados_auditor.get('faturas', []):
            caminho_zip_original_na_fonte = fatura_info.get('caminho_zip_original')

            if not caminho_zip_original_na_fonte or not os.path.isfile(caminho_zip_original_na_fonte):
                logging.warning(f"Arquivo ZIP original '{caminho_zip_original_na_fonte}' para o auditor '{nome_auditor}' não encontrado na origem. Pulando.")
                status_auditor['avisos_nao_encontrados'] += 1
                continue

            nome_arquivo_zip = os.path.basename(caminho_zip_original_na_fonte)
            caminho_destino_zip = os.path.join(caminho_pasta_auditor, nome_arquivo_zip)

            try:
                if os.path.exists(caminho_destino_zip):
                    # Se o arquivo já foi movido (ex: reexecução), não precisa mover novamente
                    status_auditor['movidos'] += 1
                    logging.info(f"Arquivo '{nome_arquivo_zip}' já existe no destino. Nenhuma ação necessária.")
                elif os.path.exists(caminho_zip_original_na_fonte):
                    shutil.move(caminho_zip_original_na_fonte, caminho_destino_zip)
                    status_auditor['movidos'] += 1
                    logging.info(f"Arquivo '{nome_arquivo_zip}' movido para '{caminho_pasta_auditor}'.")
                else:
                    logging.warning(f"Arquivo ZIP original '{caminho_zip_original_na_fonte}' desapareceu antes de mover. Pulando.")
                    status_auditor['avisos_nao_encontrados'] += 1
            except Exception as e_move:
                logging.error(f"Falha ao mover '{nome_arquivo_zip}' para '{caminho_pasta_auditor}'. Erro: {e_move}")
                status_auditor['erros'] += 1
                sucesso_geral = False
        status_movimentacao[nome_auditor] = status_auditor
    return sucesso_geral, status_movimentacao

def extrair_xmls_da_pasta_auditor(pasta_zips_auditor, pasta_destino_correcao_xml):
    """
    Extrai todos os arquivos .051 XML dos arquivos ZIP encontrados na pasta de um auditor
    para uma pasta de destino específica para correção.
    """
    if not os.path.isdir(pasta_zips_auditor):
        msg_erro = f"ERRO: Pasta de origem dos ZIPs do auditor não encontrada: '{pasta_zips_auditor}'"
        logging.error(msg_erro)
        return False, 0, [msg_erro]

    try:
        if not os.path.exists(pasta_destino_correcao_xml):
            os.makedirs(pasta_destino_correcao_xml)
            logging.info(f"Pasta de correção XML criada: '{pasta_destino_correcao_xml}'")
    except Exception as e:
        msg_erro = f"ERRO CRÍTICO: Não foi possível criar pasta de destino '{pasta_destino_correcao_xml}'. Erro: {e}"
        logging.critical(msg_erro)
        return False, 0, [msg_erro]

    arquivos_zip_do_auditor = listar_arquivos_zip(pasta_zips_auditor)

    if not arquivos_zip_do_auditor:
        msg_info = f"Nenhum arquivo .zip encontrado na pasta do auditor: '{os.path.basename(pasta_zips_auditor)}'"
        logging.info(msg_info)
        return True, 0, []

    quantidade_extraida = 0
    erros_detalhados = []
    sucesso_geral = True

    logging.info(f"Encontrados {len(arquivos_zip_do_auditor)} arquivos ZIP na pasta '{os.path.basename(pasta_zips_auditor)}' para extração de XML.")

    for caminho_zip in arquivos_zip_do_auditor:
        nome_zip_atual = os.path.basename(caminho_zip)
        caminho_xml_extraido = extrair_xml_fatura_do_zip(caminho_zip, pasta_destino_correcao_xml)

        if caminho_xml_extraido and os.path.exists(caminho_xml_extraido):
            quantidade_extraida += 1
        else:
            sucesso_geral = False
            erro_msg = f"Falha ao extrair XML do arquivo '{nome_zip_atual}'."
            erros_detalhados.append(erro_msg)

    return sucesso_geral, quantidade_extraida, erros_detalhados

# [NOVA FUNÇÃO ADICIONADA]
def recriar_zip_com_novo_xml(caminho_zip_original, caminho_xml_modificado, nome_xml_dentro_zip, pasta_destino_novos_zips):
    """
    Cria um NOVO arquivo ZIP na pasta de destino, substituindo o XML antigo pelo modificado,
    e mantendo os demais arquivos do ZIP original.

    Args:
        caminho_zip_original (str): Caminho completo para o arquivo ZIP de origem.
        caminho_xml_modificado (str): Caminho completo para o arquivo XML já modificado.
        nome_xml_dentro_zip (str): O nome exato do arquivo XML DENTRO do ZIP (ex: 'N0123456.051').
        pasta_destino_novos_zips (str): Pasta onde o novo ZIP será criado.

    Returns:
        tuple: (bool, str) - True e o caminho do novo ZIP em caso de sucesso, False e msg de erro em caso de falha.
    """
    if not os.path.exists(caminho_zip_original):
        logging.error(f"Erro: Arquivo ZIP original não encontrado: {caminho_zip_original}")
        return False, f"Arquivo ZIP original não encontrado: {caminho_zip_original}"
    if not os.path.exists(caminho_xml_modificado):
        logging.error(f"Erro: Arquivo XML modificado não encontrado: {caminho_xml_modificado}")
        return False, f"Arquivo XML modificado não encontrado: {caminho_xml_modificado}"

    os.makedirs(pasta_destino_novos_zips, exist_ok=True)

    # O nome do novo ZIP será o mesmo do original
    nome_base_zip = os.path.basename(caminho_zip_original)
    caminho_novo_zip = os.path.join(pasta_destino_novos_zips, nome_base_zip)

    # Verifica se o ZIP de destino já existe e, se sim, o remove para evitar conflito.
    if os.path.exists(caminho_novo_zip):
        try:
            os.remove(caminho_novo_zip)
            logging.info(f"Arquivo ZIP de destino existente '{os.path.basename(caminho_novo_zip)}' removido para substituição.")
        except Exception as e:
            logging.error(f"Erro: Não foi possível remover ZIP de destino existente '{os.path.basename(caminho_novo_zip)}': {e}")
            return False, f"Erro: Não foi possível remover ZIP de destino existente: {e}"

    try:
        with zipfile.ZipFile(caminho_zip_original, 'r') as zip_read:
            with zipfile.ZipFile(caminho_novo_zip, 'w', zipfile.ZIP_DEFLATED) as zip_write:
                # Copiar todos os arquivos do ZIP original, exceto o XML que será substituído
                for item in zip_read.infolist():
                    if item.filename == nome_xml_dentro_zip:
                        logging.info(f"Ignorando o XML antigo '{nome_xml_dentro_zip}' no ZIP original para o novo ZIP.")
                        continue # Pula o XML antigo

                    data = zip_read.read(item.filename)
                    zip_write.writestr(item, data)
                    logging.debug(f"Copiado '{item.filename}' para o novo ZIP.")

                # Adicionar o novo XML modificado
                zip_write.write(caminho_xml_modificado, arcname=nome_xml_dentro_zip)
                logging.info(f"Novo XML '{nome_xml_dentro_zip}' adicionado ao novo ZIP.")

        return True, caminho_novo_zip

    except Exception as e:
        # Se ocorrer um erro, tentar limpar o arquivo temporário/parcialmente criado
        if os.path.exists(caminho_novo_zip):
            os.remove(caminho_novo_zip)
        logging.exception(f"Erro ao recriar ZIP com novo XML para '{os.path.basename(caminho_zip_original)}': {e}")
        return False, f"Erro ao criar novo ZIP: {e}"


# Bloco de teste (para rodar 'python core/file_manager.py' diretamente)
if __name__ == '__main__':
    logging.info("Executando file_manager.py como script principal para teste (apenas exemplo de funções).")
    # Este bloco pode ser expandido para testar as novas funções, se desejar.
    # Exemplo de uso da nova função:
    # criar um ZIP de teste, extrair um XML, modificá-lo, e depois recriar o ZIP
    # e verificar a pasta de destino.