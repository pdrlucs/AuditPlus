# core/workflow_controller.py (Versão Consolidada com todas as regras e correções)

import os
import shutil
import traceback
import logging
import json
from lxml import etree

from . import file_manager
from utils import xml_parser
from . import data_manager
from . import distribution_engine
from . import report_generator
from core import hash_calculator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - (controller) - %(message)s')

class WorkflowController:
    VALOR_MINIMO_GUIA = 25000.0

    TP_PRESTADOR_MAP = {
        "01": {"10", "11", "13", "49", "54", "80", "82"},
        "02": {"42", "44", "50", "51", "52"},
        "03": {"30"},
        "04": {"20", "21", "22", "23", "24", "25", "26", "40", "41", "43", "45", "46", "53"},
        "05": {"12", "47"},
        "06": {"14"},
        "11": {"48"}
    }
    CD_PRESTADOR_RECURSO_PROPRIO = {"11099", "11110", "11152", "8150", "8162"}

    NOME_ARQUIVO_REFERENCIAL_HM = "referencial_hm_list202502.json"
    NOME_ARQUIVO_REFERENCIAL_SADT = "referencial_sadt_list202502.json"
    NOME_ARQUIVO_REFERENCIAL_INSTRUCOES = "referencial_instructions_rol202502.json"

    def __init__(self, log_callback=None):
        if log_callback:
            self.log_callback = log_callback
        else:
            self.log_callback = lambda msg: (print(f"LOG_GUI_FALLBACK: {msg}"), logging.info(f"(Controller-Fallback): {msg}"))

        self.lista_faturas_processadas = []
        self.pasta_faturas_importadas_atual = None
        self.nomes_auditores_ultima_distribuicao = []
        self.plano_ultima_distribuicao = {}
        self.codigos_hm_t00_a_ignorar = set()

        self.dados_referencia_hm = {}
        self.dados_referencia_sadt = {}
        self.dados_instrucoes_gerais = None

        self.ttRegistrosRegraHM = []
        self.ttRegistrosRegraCO = []
        self.ttRegistrosRemanejar = []

        self.log_callback("Controller: WorkflowController inicializando...")
        try:
            if not data_manager.is_hm_tabela00_carregados():
                self.log_callback("Controller: Tentando carregar códigos HM Tabela 00 a ignorar...")
                data_manager.carregar_codigos_hm_tabela00_a_ignorar()
                if data_manager.hm_tabela00_carregados_com_sucesso:
                    self.log_callback("Controller: Códigos HM Tabela 00 a ignorar carregados.")
                    self.codigos_hm_t00_a_ignorar = data_manager.get_codigos_hm_tabela00_a_ignorar()
                else:
                    self.log_callback("Controller ERRO: Falha ao carregar códigos HM Tabela 00 a ignorar.")
            else:
                self.log_callback("Controller: Códigos HM Tabela 00 a ignorar já estavam carregados.")
                self.codigos_hm_t00_a_ignorar = data_manager.get_codigos_hm_tabela00_a_ignorar()

            if not data_manager.is_unimeds_carregadas():
                self.log_callback("Controller: Tentando carregar dados das Unimeds...")
                data_manager.carregar_dados_unimed()
                if data_manager.unimeds_carregadas:
                    self.log_callback("Controller: Dados das Unimeds carregados com sucesso.")
                else:
                    self.log_callback("Controller ERRO: Falha ao carregar dados das Unimeds.")
            else:
                self.log_callback("Controller: Dados das Unimeds já estavam carregados.")

            self._carregar_dados_listas_referencia()

        except Exception as e:
            self.log_callback(f"Controller ERRO CRÍTICO na inicialização: {e}\n{traceback.format_exc()}")
        self.log_callback("WorkflowController inicializado e pronto.")

    def _carregar_dados_listas_referencia(self):
        self.log_callback("Controller: Carregando dados das Listas Referenciais HM, SADT e Instruções...")
        base_dir_config = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       '..', 'config', 'reference_list')

        arquivos_a_carregar = [
            (self.NOME_ARQUIVO_REFERENCIAL_HM, 'dados_referencia_hm', 'COD_PROCEDIMENTO'),
            (self.NOME_ARQUIVO_REFERENCIAL_SADT, 'dados_referencia_sadt', 'COD_PROCEDIMENTO'),
            (self.NOME_ARQUIVO_REFERENCIAL_INSTRUCOES, 'dados_instrucoes_gerais', None)
        ]
        for nome_arquivo, atributo_controller, chave_dicionario in arquivos_a_carregar:
            try:
                caminho_arquivo = os.path.join(base_dir_config, nome_arquivo)
                if os.path.exists(caminho_arquivo):
                    with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                        dados_json = json.load(f)
                        if chave_dicionario and isinstance(dados_json, list):
                            # [PONTO DE ATENÇÃO MENCIONADO ANTERIORMENTE]
                            # Se 'COD_PROCEDIMENTO' não existe, mas outra chave serve como ID,
                            # esta linha pode precisar ser ajustada (ex: usar outra chave como ID)
                            dados_dict = {str(proc.get(chave_dicionario,'')).strip(): proc
                                          for proc in dados_json if proc.get(chave_dicionario)}
                            setattr(self, atributo_controller, dados_dict)
                            self.log_callback(f"Controller: {len(dados_dict)} registros carregados de '{nome_arquivo}'.")
                        elif isinstance(dados_json, (list, dict)) and chave_dicionario is None :
                            setattr(self, atributo_controller, dados_json)
                            self.log_callback(f"Controller: Dados gerais carregados de '{nome_arquivo}'.")
                        else:
                            self.log_callback(f"Controller AVISO: Estrutura inesperada em '{nome_arquivo}'.")
                else:
                    self.log_callback(f"Controller ERRO: Arquivo '{nome_arquivo}' não encontrado em '{base_dir_config}'.")
            except Exception as e:
                self.log_callback(f"Controller ERRO ao carregar '{nome_arquivo}': {e}")
                logging.exception(f"Falha ao carregar {nome_arquivo}")

    def _aplicar_regra_cnes(self, raiz_xml, namespaces):
        regras_aplicadas_nesta_funcao = 0
        xpath_cnes = './/ptu:contratadoExecutante/ptu:CNES | .//ptu:dadosExecutante/ptu:CNES | .//ptu:dadosHospital/ptu:CNES'
        nos_cnes = raiz_xml.xpath(xpath_cnes, namespaces=namespaces)
        if nos_cnes:
            for no_cnes in nos_cnes:
                if no_cnes is not None and (not no_cnes.text or no_cnes.text.strip() in ('', '0')):
                    valor_antigo = no_cnes.text.strip() if no_cnes.text else "vazio"
                    no_cnes.text = '9999999'
                    self.log_callback(f"    - Regra CNES (09) aplicada. CNES antigo: '{valor_antigo}', Novo: '9999999'.")
                    regras_aplicadas_nesta_funcao += 1
        return regras_aplicadas_nesta_funcao

    def _aplicar_regra_tipo_documento(self, raiz_xml, namespaces):
        regras_aplicadas_nesta_funcao = 0
        elementos_documento = raiz_xml.xpath('.//ptu:Cobranca/ptu:documento1 | .//ptu:Cobranca/ptu:documento2', namespaces=namespaces)
        for doc_element in elementos_documento:
            if doc_element is None: continue
            tp_documento_node = doc_element.find('./ptu:tp_Documento', namespaces=namespaces)
            if tp_documento_node is not None and tp_documento_node.text and tp_documento_node.text.strip() == '3':
                tp_documento_node.text = '1'
                self.log_callback(f"    - Regra Tipo Documento (06) aplicada: tp_Documento alterado de '3' para '1'.")
                regras_aplicadas_nesta_funcao += 1
                nfe_node = doc_element.find('./ptu:NFE', namespaces=namespaces)
                if nfe_node is not None:
                    doc_element.remove(nfe_node)
                    self.log_callback(f"    - Regra Tipo Documento (06): Tag <NFE> removida.")
        return regras_aplicadas_nesta_funcao

    def _aplicar_regra_data_conhecimento_protocolo(self, raiz_xml, namespaces):
        regras_aplicadas_nesta_funcao = 0
        guias_com_dados_guia = raiz_xml.xpath('.//ptu:dadosGuia', namespaces=namespaces)
        for dados_guia_node in guias_com_dados_guia:
            if dados_guia_node is None: continue
            dt_conhecimento_node = dados_guia_node.find('./ptu:dt_Conhecimento', namespaces=namespaces)
            dt_protocolo_node = dados_guia_node.find('./ptu:dt_Protocolo', namespaces=namespaces)
            if dt_conhecimento_node is not None and dt_protocolo_node is not None and \
               dt_conhecimento_node.text is not None:
                if dt_protocolo_node.text != dt_conhecimento_node.text:
                    valor_antigo_protocolo = dt_protocolo_node.text if dt_protocolo_node.text is not None else "vazio/None"
                    dt_protocolo_node.text = dt_conhecimento_node.text
                    self.log_callback(f"    - Regra Data Protocolo (08) aplicada: dt_Protocolo ('{valor_antigo_protocolo}') atualizada para '{dt_conhecimento_node.text}'.")
                    regras_aplicadas_nesta_funcao += 1
        return regras_aplicadas_nesta_funcao

    def _aplicar_regra_tipo_prestador(self, raiz_xml, namespaces):
        regras_aplicadas_nesta_funcao = 0
        elementos_prestador_contexto = raiz_xml.xpath(
            './/ptu:contratadoExecutante | .//ptu:contratadoSolicitante | .//ptu:dadosExecutante | .//ptu:equipe_Profissional/ptu:Prestador',
            namespaces=namespaces
        )
        for contexto_node in elementos_prestador_contexto:
            if contexto_node is None: continue
            cd_prest_node = contexto_node.find('./ptu:UnimedPrestador/ptu:cd_Prest', namespaces)
            if cd_prest_node is None:
                cd_prest_node = contexto_node.find('./ptu:cd_Prest', namespaces)

            tp_prestador_node = contexto_node.find('./ptu:prestador/ptu:tp_Prestador', namespaces)
            if tp_prestador_node is None:
                tp_prestador_node = contexto_node.find('./ptu:tp_Prestador', namespaces)

            if not (cd_prest_node is not None and tp_prestador_node is not None): continue

            cd_prest_atual = cd_prest_node.text.strip() if cd_prest_node.text else ""
            tp_prest_original = tp_prestador_node.text.strip() if tp_prestador_node.text else ""
            novo_tp_prest = tp_prest_original

            if cd_prest_atual == "11110":
                novo_tp_prest = "08"
                tp_participacao_node = contexto_node.find('./ptu:tp_Participacao', namespaces)
                if tp_participacao_node is None and cd_prest_node.getparent() is not None and cd_prest_node.getparent().tag.endswith("UnimedPrestador"):
                     pai_unimed_prest = cd_prest_node.getparent()
                     if pai_unimed_prest.getparent() is not None:
                        tp_participacao_node = pai_unimed_prest.getparent().find('./ptu:tp_Participacao', namespaces)

                if tp_participacao_node is not None:
                    pai_participacao = tp_participacao_node.getparent()
                    if pai_participacao is not None:
                        pai_participacao.remove(tp_participacao_node)
                        self.log_callback(f"    - Regra Tipo Prestador (10): tp_Participacao removida para cd_Prest {cd_prest_atual}.")
            else:
                for novo_valor, codigos_originais in self.TP_PRESTADOR_MAP.items():
                    if tp_prest_original in codigos_originais: novo_tp_prest = novo_valor; break

            if novo_tp_prest != tp_prest_original:
                tp_prestador_node.text = novo_tp_prest
                self.log_callback(f"    - Regra Tipo Prestador (10): cd_Prest '{cd_prest_atual}', tp_Prestador de '{tp_prest_original}' para '{novo_tp_prest}'.")
                regras_aplicadas_nesta_funcao += 1

            if novo_tp_prest == "08":
                guia_pai_list = contexto_node.xpath('ancestor::ptu:guiaConsulta | ancestor::ptu:guiaSADT | ancestor::ptu:guiaInternacao | ancestor::ptu:guiaHonorarios', namespaces=namespaces)
                if guia_pai_list:
                    guia_pai = guia_pai_list[0]
                    if guia_pai is None: continue
                    dados_atendimento_node = guia_pai.find('.//ptu:dadosAtendimento/ptu:tp_Atendimento', namespaces=namespaces)
                    if dados_atendimento_node is not None and dados_atendimento_node.text is not None and dados_atendimento_node.text.strip() != "06":
                        valor_antigo_tp_atend = dados_atendimento_node.text.strip()
                        dados_atendimento_node.text = "06"
                        self.log_callback(f"    - Regra Tipo Prestador (10): tp_Atendimento ('{valor_antigo_tp_atend}') alterado para '06'.")
                        regras_aplicadas_nesta_funcao += 1
        return regras_aplicadas_nesta_funcao

    def _aplicar_regra_recurso_proprio(self, raiz_xml, namespaces):
        regras_aplicadas_nesta_funcao = 0
        elementos_prestador_contexto = raiz_xml.xpath(
            './/ptu:contratadoExecutante | .//ptu:contratadoSolicitante | .//ptu:dadosExecutante', namespaces=namespaces
        )
        for contexto_node in elementos_prestador_contexto:
            if contexto_node is None: continue
            cd_prest_node = contexto_node.find('./ptu:UnimedPrestador/ptu:cd_Prest', namespaces)
            if cd_prest_node is None:
                cd_prest_node = contexto_node.find('./ptu:cd_Prest', namespaces)

            id_rec_proprio_node = contexto_node.find('./ptu:prestador/ptu:id_RecProprio', namespaces=namespaces)

            if cd_prest_node is not None and id_rec_proprio_node is not None:
                cd_prest_atual = cd_prest_node.text.strip() if cd_prest_node.text else ""
                novo_valor_rec_proprio = "S" if cd_prest_atual in self.CD_PRESTADOR_RECURSO_PROPRIO else "N"
                if id_rec_proprio_node.text is None or id_rec_proprio_node.text.strip() != novo_valor_rec_proprio:
                    valor_antigo = id_rec_proprio_node.text.strip() if id_rec_proprio_node.text else "vazio"
                    id_rec_proprio_node.text = novo_valor_rec_proprio
                    self.log_callback(f"    - Regra Recurso Próprio (11): cd_Prest '{cd_prest_atual}', id_RecProprio de '{valor_antigo}' para '{novo_valor_rec_proprio}'.")
                    regras_aplicadas_nesta_funcao += 1
        return regras_aplicadas_nesta_funcao

    def _aplicar_regra_digitos_pacote(self, raiz_xml, namespaces):
        regras_aplicadas_nesta_funcao = 0
        procedimentos_executados_nodes = raiz_xml.xpath('.//ptu:procedimentosExecutados', namespaces=namespaces)
        for proc_exec_node in procedimentos_executados_nodes:
            if proc_exec_node is None: continue
            id_pacote_node = proc_exec_node.find('./ptu:id_Pacote', namespaces=namespaces)
            cd_pacote_node = proc_exec_node.find('./ptu:cd_Pacote', namespaces=namespaces)
            if id_pacote_node is not None and cd_pacote_node is not None:
                id_pacote_text = id_pacote_node.text.strip() if id_pacote_node.text else ""
                cd_pacote_text_original = cd_pacote_node.text.strip() if cd_pacote_node.text else ""
                if id_pacote_text.upper() == "S" and cd_pacote_text_original and len(cd_pacote_text_original) < 8:
                    novo_cd_pacote = cd_pacote_text_original.zfill(8)
                    if cd_pacote_node.text != novo_cd_pacote:
                         cd_pacote_node.text = novo_cd_pacote
                         self.log_callback(f"    - Regra Dígitos Pacote: cd_Pacote '{cd_pacote_text_original}' para '{novo_cd_pacote}'.")
                         regras_aplicadas_nesta_funcao += 1
        return regras_aplicadas_nesta_funcao

    def _get_node_text_as_float(self, node, default_if_none=None):
        if node is not None and node.text and node.text.strip():
            try:
                return float(node.text.strip().replace(',', '.'))
            except ValueError:
                return default_if_none
        return default_if_none

    def _update_or_create_node(self, parent_node, tag_name_sem_prefixo, new_value, namespaces, insert_before_node=None):
        if parent_node is None:
            self.log_callback(f"      - AVISO: Tentativa de atualizar/criar nó '{tag_name_sem_prefixo}' em um parent_node Nulo.")
            return None

        tag_name_com_prefixo_ns = f"{{{namespaces['ptu']}}}{tag_name_sem_prefixo}"
        node = parent_node.find(f'./ptu:{tag_name_sem_prefixo}', namespaces=namespaces)

        formatted_value = new_value
        if isinstance(new_value, (int, float)):
            formatted_value = f"{new_value:.2f}".replace('.', ',', 1) # Usar 1 para substituir apenas a primeira ocorrência

        if node is not None:
            node.text = formatted_value
        else:
            node = etree.Element(tag_name_com_prefixo_ns, attrib=None, nsmap=None)
            node.text = formatted_value
            if insert_before_node is not None:
                parent_of_insert_before = insert_before_node.getparent()
                if parent_of_insert_before is not None and parent_of_insert_before == parent_node:
                    insert_before_node.addprevious(node)
                else:
                    parent_node.append(node)
            else:
                parent_node.append(node)
        return node

    def _aplicar_modificacoes_regras_hm_co_xml(self, raiz_xml, namespaces):
        regras_aplicadas_nesta_funcao_total = 0
        self.log_callback("    - Iniciando aplicação de regras HM/CO (baseado em JSONs)...")

        if not self.dados_referencia_hm and not self.dados_referencia_sadt:
            self.log_callback("    - AVISO: Dados de referência HM/SADT não carregados. Regras HM/CO não podem ser aplicadas.")
            return 0

        xpath_cd_servico = ".//ptu:procedimentos/ptu:cd_Servico | .//ptu:procedimentosExecutados/ptu:procedimentos/ptu:cd_Servico"
        todos_nos_cd_servico_xml = raiz_xml.xpath(xpath_cd_servico, namespaces=namespaces)

        for no_cd_servico_xml in todos_nos_cd_servico_xml:
            if no_cd_servico_xml is None: continue
            cd_servico_xml = no_cd_servico_xml.text.strip() if no_cd_servico_xml.text else None
            if not cd_servico_xml: continue

            dados_proc_ref = self.dados_referencia_hm.get(cd_servico_xml)
            if not dados_proc_ref:
                dados_proc_ref = self.dados_referencia_sadt.get(cd_servico_xml)

            if dados_proc_ref:
                no_procedimentos_tag = no_cd_servico_xml.getparent()
                if no_procedimentos_tag is None: continue

                no_contexto_valores_e_taxas = None
                if no_procedimentos_tag.tag == etree.QName(namespaces['ptu'], 'procedimentos'): # GuiaConsulta
                    no_procedimentos_pai = no_procedimentos_tag.getparent()
                    if no_procedimentos_pai is not None and no_procedimentos_pai.tag == etree.QName(namespaces['ptu'], 'dadosGuia'):
                        guia_node = no_procedimentos_pai.getparent()
                        if guia_node is not None and guia_node.tag == etree.QName(namespaces['ptu'], 'guiaConsulta'):
                             no_contexto_valores_e_taxas = no_procedimentos_tag

                if no_contexto_valores_e_taxas is None:
                    no_procedimentos_exec_pai = no_procedimentos_tag.getparent()
                    if no_procedimentos_exec_pai is not None and \
                       no_procedimentos_exec_pai.tag == etree.QName(namespaces['ptu'], 'procedimentosExecutados'):
                        no_contexto_valores_e_taxas = no_procedimentos_exec_pai

                if no_contexto_valores_e_taxas is None: continue

                coberto_status = dados_proc_ref.get("COBERTO_UNIMED_CG", "NAO").upper()

                if coberto_status == "SIM":
                    regras_aplicadas_neste_item = 0
                    vl_serv_node, vl_co_node, tx_adm_serv_node, tx_adm_co_node = None, None, None, None
                    contexto_para_val = no_contexto_valores_e_taxas
                    contexto_para_tax = no_contexto_valores_e_taxas

                    if no_contexto_valores_e_taxas.tag == etree.QName(namespaces['ptu'], 'procedimentos'): # GuiaConsulta
                        vl_serv_node = no_contexto_valores_e_taxas.find('./ptu:vl_ServCobrado', namespaces)
                        vl_co_node = no_contexto_valores_e_taxas.find('./ptu:vl_CO_Cobrado', namespaces)
                        tx_adm_serv_node = no_contexto_valores_e_taxas.find('./ptu:tx_AdmServico', namespaces)
                        tx_adm_co_node = no_contexto_valores_e_taxas.find('./ptu:tx_AdmCO', namespaces)
                    elif no_contexto_valores_e_taxas.tag == etree.QName(namespaces['ptu'], 'procedimentosExecutados'):
                        valores_node = no_contexto_valores_e_taxas.find('./ptu:valores', namespaces)
                        taxas_node = no_contexto_valores_e_taxas.find('./ptu:taxas', namespaces)

                        if valores_node is not None:
                            vl_serv_node = valores_node.find('./ptu:vl_ServCobrado', namespaces)
                            vl_co_node = valores_node.find('./ptu:vl_CO_Cobrado', namespaces)
                            contexto_para_val = valores_node
                        else: # Cria <valores> se não existir
                            valores_node = etree.SubElement(no_contexto_valores_e_taxas, f"{{{namespaces['ptu']}}}valores", attrib=None, nsmap=None)
                            contexto_para_val = valores_node

                        if taxas_node is not None:
                            tx_adm_serv_node = taxas_node.find('./ptu:tx_AdmServico', namespaces)
                            tx_adm_co_node = taxas_node.find('./ptu:tx_AdmCO', namespaces)
                            contexto_para_tax = taxas_node
                        else: # Cria <taxas> se não existir
                            taxas_node = etree.SubElement(no_contexto_valores_e_taxas, f"{{{namespaces['ptu']}}}taxas", attrib=None, nsmap=None)
                            contexto_para_tax = taxas_node
                    else: continue

                    val_serv = self._get_node_text_as_float(vl_serv_node)
                    val_co = self._get_node_text_as_float(vl_co_node)

                    if vl_serv_node is not None and vl_co_node is not None and val_serv is not None and val_co is not None:
                        novo_val_serv = val_serv + val_co
                        vl_serv_node.text = f"{novo_val_serv:.2f}".replace('.', ',')
                        parent_co = vl_co_node.getparent();
                        if parent_co is not None: parent_co.remove(vl_co_node)
                        regras_aplicadas_neste_item += 1
                    elif (vl_serv_node is None or not (vl_serv_node.text and vl_serv_node.text.strip())) and \
                         (vl_co_node is not None and val_co is not None):
                        self._update_or_create_node(contexto_para_val, "vl_ServCobrado", val_co, namespaces, insert_before_node=vl_co_node)
                        if vl_co_node is not None :
                            parent_co = vl_co_node.getparent();
                            if parent_co is not None: parent_co.remove(vl_co_node)
                        regras_aplicadas_neste_item += 1

                    taxa_serv = self._get_node_text_as_float(tx_adm_serv_node)
                    taxa_co = self._get_node_text_as_float(tx_adm_co_node)

                    if tx_adm_serv_node is not None and tx_adm_co_node is not None and taxa_serv is not None and taxa_co is not None:
                        nova_taxa_serv = taxa_serv + taxa_co
                        tx_adm_serv_node.text = f"{nova_taxa_serv:.2f}".replace('.', ',')
                        parent_taxa_co = tx_adm_co_node.getparent();
                        if parent_taxa_co is not None: parent_taxa_co.remove(tx_adm_co_node)
                        regras_aplicadas_neste_item += 1
                    elif (tx_adm_serv_node is None or not (tx_adm_serv_node.text and tx_adm_serv_node.text.strip())) and \
                         (tx_adm_co_node is not None and taxa_co is not None):
                        self._update_or_create_node(contexto_para_tax, "tx_AdmServico", taxa_co, namespaces, insert_before_node=tx_adm_co_node)
                        if tx_adm_co_node is not None:
                            parent_taxa_co = tx_adm_co_node.getparent();
                            if parent_taxa_co is not None: parent_taxa_co.remove(tx_adm_co_node)
                        regras_aplicadas_neste_item += 1

                    if regras_aplicadas_neste_item > 0:
                        self.log_callback(f"        - Modificações HM/CO aplicadas para o procedimento: {cd_servico_xml}")
                        regras_aplicadas_nesta_funcao_total += regras_aplicadas_neste_item

        if regras_aplicadas_nesta_funcao_total == 0 and len(todos_nos_cd_servico_xml) > 0 :
             self.log_callback("    - Nenhuma modificação específica de regra HM/CO foi aplicada.")
        elif regras_aplicadas_nesta_funcao_total > 0:
            self.log_callback(f"    - {regras_aplicadas_nesta_funcao_total} modificações de regras HM/CO aplicadas ao XML.")

        return regras_aplicadas_nesta_funcao_total

    def _remanejar_itens_duplicados_xml(self, raiz_xml, namespaces):
        regras_aplicadas_nesta_funcao = 0
        # Futuramente: Carregar self.ttRegistrosRemanejar de um JSON ou outra fonte
        if self.ttRegistrosRemanejar:
            self.log_callback("    - AVISO: _remanejar_itens_duplicados_xml não implementado em detalhe.")
        return regras_aplicadas_nesta_funcao

    def _aplicar_regras_de_negocio(self, caminho_arquivo_xml):
        self.log_callback(f"  Aplicando regras de negócio ao arquivo: {os.path.basename(caminho_arquivo_xml)}...")
        try:
            parser_xml = etree.XMLParser(recover=True, strip_cdata=False, resolve_entities=False)
            arvore_xml = etree.parse(caminho_arquivo_xml, parser=parser_xml)
            raiz = arvore_xml.getroot()
            if raiz is None:
                self.log_callback(f"  ERRO CRÍTICO: Raiz do XML não pôde ser lida em '{os.path.basename(caminho_arquivo_xml)}'.")
                return False

            namespaces = {'ptu': 'http://ptu.unimed.coop.br/schemas/V3_0'}
            regras_aplicadas_total = 0

            regras_aplicadas_total += self._aplicar_regra_cnes(raiz, namespaces)
            regras_aplicadas_total += self._aplicar_regra_tipo_documento(raiz, namespaces)
            regras_aplicadas_total += self._aplicar_regra_data_conhecimento_protocolo(raiz, namespaces)
            regras_aplicadas_total += self._aplicar_regra_tipo_prestador(raiz, namespaces)
            regras_aplicadas_total += self._aplicar_regra_recurso_proprio(raiz, namespaces)
            regras_aplicadas_total += self._aplicar_regra_digitos_pacote(raiz, namespaces)
            regras_aplicadas_total += self._aplicar_modificacoes_regras_hm_co_xml(raiz, namespaces)
            regras_aplicadas_total += self._remanejar_itens_duplicados_xml(raiz, namespaces)

            if regras_aplicadas_total > 0:
                arvore_xml.write(caminho_arquivo_xml, encoding='latin-1', xml_declaration=True, pretty_print=True)
                self.log_callback(f"  Arquivo XML modificado e salvo com {regras_aplicadas_total} alteraçõe(s) de regras aplicadas.")
            else:
                self.log_callback("  Nenhuma regra de negócio estrutural precisou ser aplicada neste arquivo.")
            return True
        except etree.XMLSyntaxError as exsyn:
            self.log_callback(f"  ERRO DE SINTAXE XML em '{os.path.basename(caminho_arquivo_xml)}': {exsyn}")
            logging.exception(f"XMLSyntaxError em _aplicar_regras_de_negocio para {caminho_arquivo_xml}")
            return False
        except Exception as e:
            self.log_callback(f"  ERRO CRÍTICO ao aplicar regras de negócio em '{os.path.basename(caminho_arquivo_xml)}'. Erro: {e}")
            logging.exception(f"Falha em _aplicar_regras_de_negocio para {caminho_arquivo_xml}")
            return False

    def processar_importacao_faturas(self, caminho_da_pasta_selecionada):
        self.pasta_faturas_importadas_atual = caminho_da_pasta_selecionada
        self.log_callback(f"Iniciando importação da pasta: {self.pasta_faturas_importadas_atual}")
        self.lista_faturas_processadas = []
        self.log_callback("Listando arquivos ZIP...")
        arquivos_zip = file_manager.listar_arquivos_zip(self.pasta_faturas_importadas_atual)
        if not arquivos_zip: self.log_callback(f"Nenhum arquivo .zip encontrado."); return
        self.log_callback(f"{len(arquivos_zip)} arquivo(s) .zip encontrado(s).")
        pasta_backup = file_manager.criar_pasta_backup(self.pasta_faturas_importadas_atual)
        if not pasta_backup: self.log_callback("ERRO CRÍTICO: Não foi possível criar pasta de Backup."); return
        self.log_callback(f"Pasta de backup pronta em: {pasta_backup}")
        pasta_raiz_correcao = file_manager.criar_pasta_raiz_correcao_xml(self.pasta_faturas_importadas_atual)
        if not pasta_raiz_correcao: self.log_callback("ERRO CRÍTICO: Não foi possível criar pasta 'Correção XML'."); return
        self.log_callback(f"Pasta raiz para correção de XMLs pronta em: {pasta_raiz_correcao}")
        pasta_temp_extracao_import = os.path.join(self.pasta_faturas_importadas_atual, ".TempExtracaoXMLImport")
        os.makedirs(pasta_temp_extracao_import, exist_ok=True)
        self.log_callback(f"Pasta de extração temporária criada/pronta em: {pasta_temp_extracao_import}")
        total_faturas = len(arquivos_zip); faturas_com_sucesso = 0
        for i, caminho_zip_fatura in enumerate(arquivos_zip):
            nome_arquivo_zip = os.path.basename(caminho_zip_fatura)
            self.log_callback(f"--- Processando fatura {i+1}/{total_faturas}: {nome_arquivo_zip} ---")
            if file_manager.fazer_backup_fatura(caminho_zip_fatura, pasta_backup): self.log_callback(f"  Backup de '{nome_arquivo_zip}' criado/verificado.")
            else: self.log_callback(f"  AVISO: Falha ao criar backup para '{nome_arquivo_zip}'.")
            self.log_callback(f"  Extraindo XML de '{nome_arquivo_zip}'...")
            caminho_xml_extraido = file_manager.extrair_xml_fatura_do_zip(caminho_zip_fatura, pasta_temp_extracao_import)
            if not caminho_xml_extraido: self.log_callback(f"  ERRO: Não foi possível extrair XML de '{nome_arquivo_zip}'. Pulando."); continue
            nome_xml_extraido = os.path.basename(caminho_xml_extraido)
            self.log_callback(f"  XML '{nome_xml_extraido}' extraído para '{pasta_temp_extracao_import}'.")
            if not self._aplicar_regras_de_negocio(caminho_xml_extraido):
                self.log_callback(f"  AVISO: Problemas ao aplicar regras em '{nome_xml_extraido}'.")
            self.log_callback(f"  Lendo dados do cabeçalho do XML '{nome_xml_extraido}' (após regras)...")
            dados_fatura_xml = xml_parser.extrair_dados_fatura_xml(caminho_xml_extraido)
            if not dados_fatura_xml or not any(dados_fatura_xml.values()):
                self.log_callback(f"  ERRO: Não foi possível ler dados do XML '{nome_arquivo_zip}'. Pulando.")
                file_manager.remover_arquivo_se_existe(caminho_xml_extraido); continue
            dados_fatura_xml['caminho_zip_original'] = caminho_zip_fatura
            dados_fatura_xml['nome_zip'] = nome_arquivo_zip
            codigo_unimed_original_xml = dados_fatura_xml.get('codigo_unimed_destino')
            codigo_unimed_para_busca = codigo_unimed_original_xml
            if codigo_unimed_original_xml:
                try: codigo_unimed_para_busca = f"{int(str(codigo_unimed_original_xml).strip()):03d}"
                except (ValueError, TypeError): self.log_callback(f"  AVISO: Código Unimed '{codigo_unimed_original_xml}' inválido.")
                nome_unimed = data_manager.obter_nome_unimed(codigo_unimed_para_busca)
                dados_fatura_xml['codigo_unimed_destino'] = codigo_unimed_para_busca
                dados_fatura_xml['nome_unimed_destino'] = nome_unimed
                self.log_callback(f"  Unimed Destino: {codigo_unimed_para_busca} - {nome_unimed}")
            else:
                dados_fatura_xml['nome_unimed_destino'] = "NÃO ENCONTRADO NO XML"
                dados_fatura_xml['codigo_unimed_destino'] = ""
                self.log_callback(f"  AVISO: Código da Unimed Destino não encontrado.")
            numero_fatura_atual = dados_fatura_xml.get('numero_fatura')
            if numero_fatura_atual and caminho_xml_extraido:
                self.log_callback(f"  Buscando guias de internação em '{nome_xml_extraido}'...")
                guias_relevantes = xml_parser.extrair_guias_internacao_relevantes(
                    caminho_xml_extraido, numero_fatura_atual,
                    self.codigos_hm_t00_a_ignorar, valor_minimo_guia=self.VALOR_MINIMO_GUIA
                )
                if guias_relevantes: self.log_callback(f"  {len(guias_relevantes)} guia(s) de internação relevante(s) encontrada(s).")
                dados_fatura_xml['guias_internacao_relevantes'] = guias_relevantes if guias_relevantes else []
            else:
                self.log_callback(f"  AVISO: Não foi possível buscar guias."); dados_fatura_xml['guias_internacao_relevantes'] = []
            self.log_callback(f"  Dados processados: Fatura {dados_fatura_xml.get('numero_fatura', 'N/A')}, Valor: {dados_fatura_xml.get('valor_total_documento', 'N/A')}")
            self.lista_faturas_processadas.append(dados_fatura_xml); faturas_com_sucesso += 1
            file_manager.remover_arquivo_se_existe(caminho_xml_extraido)
            self.log_callback(f"  Arquivo XML temporário '{nome_xml_extraido}' removido.")
            self.log_callback(f"--- Fim do processamento para: {nome_arquivo_zip} ---")
        self.log_callback(f"Importação de faturas concluída. {faturas_com_sucesso}/{total_faturas} faturas processadas.")
        try:
            if os.path.exists(pasta_temp_extracao_import): shutil.rmtree(pasta_temp_extracao_import)
            self.log_callback(f"Pasta de extração temporária '{pasta_temp_extracao_import}' removida.")
        except Exception as e_clean: self.log_callback(f"AVISO: Falha ao remover pasta temporária '{pasta_temp_extracao_import}'. Erro: {e_clean}")

    def preparar_distribuicao_faturas(self, numero_auditores, nomes_auditores):
        self.log_callback(f"Distribuindo faturas para {numero_auditores} auditor(es): {', '.join(nomes_auditores)}.")
        self.nomes_auditores_ultima_distribuicao = nomes_auditores; self.plano_ultima_distribuicao = {}
        if not self.lista_faturas_processadas: self.log_callback("ERRO: Nenhuma fatura processada."); return None
        if not self.pasta_faturas_importadas_atual: self.log_callback("ERRO: Pasta de origem não definida."); return None
        self.log_callback(f"Total de {len(self.lista_faturas_processadas)} faturas para distribuir.")
        plano = distribution_engine.distribuir_faturas_entre_auditores(self.lista_faturas_processadas, nomes_auditores)
        self.plano_ultima_distribuicao = plano
        if not self.plano_ultima_distribuicao: self.log_callback("ERRO: Falha ao calcular plano de distribuição."); return None
        self.log_callback("Plano de distribuição calculado:")
        for auditor, dados in self.plano_ultima_distribuicao.items(): self.log_callback(f"  Auditor: {auditor} - Qtd: {dados['total_quantidade']}, Valor: {dados['total_valor']:.2f}")
        pasta_origem_zips = self.pasta_faturas_importadas_atual
        pasta_base_dist = self.pasta_faturas_importadas_atual
        self.log_callback(f"Organizando arquivos ZIP (origem: '{pasta_origem_zips}')...")
        sucesso_org, status_mov = file_manager.organizar_faturas_por_auditor(self.plano_ultima_distribuicao, pasta_origem_zips, pasta_base_dist)
        if sucesso_org: self.log_callback("Organização dos ZIPs concluída.")
        else: self.log_callback("AVISO: Problemas na organização dos ZIPs.")
        for aud, stat in status_mov.items(): self.log_callback(f"  Status {aud}: {stat['movidos']} movidos, {stat['erros']} erros, {stat['avisos_nao_encontrados']} não encontrados.")
        self.log_callback("Gerando relatório de distribuição Excel...")
        pasta_relatorio_dist = os.path.join(pasta_base_dist, "Distribuição"); os.makedirs(pasta_relatorio_dist, exist_ok=True)
        sucesso_rel, caminho_excel = report_generator.gerar_relatorio_distribuicao(self.plano_ultima_distribuicao, pasta_relatorio_dist)
        if sucesso_rel: self.log_callback(f"Relatório de distribuição gerado: {caminho_excel}")
        else: self.log_callback("ERRO: Falha ao gerar relatório de distribuição.")
        return self.plano_ultima_distribuicao

    def preparar_xmls_para_correcao(self, nome_auditor_selecionado):
        self.log_callback(f"Preparando XMLs para correção: {nome_auditor_selecionado}.")
        if not self.pasta_faturas_importadas_atual: self.log_callback("ERRO: Pasta de importação não definida."); return
        if not self.plano_ultima_distribuicao or nome_auditor_selecionado not in self.plano_ultima_distribuicao:
            self.log_callback(f"ERRO: Plano ou auditor '{nome_auditor_selecionado}' não encontrado."); return
        nome_pasta_auditor = nome_auditor_selecionado.replace(' ', '_').replace('.', '')
        pasta_zips_auditor = os.path.join(self.pasta_faturas_importadas_atual, "Distribuição", nome_pasta_auditor)
        if not os.path.isdir(pasta_zips_auditor): self.log_callback(f"ERRO: Pasta de ZIPs para '{nome_auditor_selecionado}' não encontrada: '{pasta_zips_auditor}'."); return
        pasta_destino_xmls_auditor = os.path.join(self.pasta_faturas_importadas_atual, "Correção XML", nome_pasta_auditor)
        self.log_callback(f"XMLs de '{nome_auditor_selecionado}' serão extraídos para: '{pasta_destino_xmls_auditor}'")
        sucesso_extr, qtd_extr, erros_l = file_manager.extrair_xmls_da_pasta_auditor(pasta_zips_auditor, pasta_destino_xmls_auditor)
        guias_csv = []
        if self.plano_ultima_distribuicao.get(nome_auditor_selecionado):
            for fatura_info in self.plano_ultima_distribuicao[nome_auditor_selecionado].get('faturas', []):
                guias_csv.extend(fatura_info.get('guias_internacao_relevantes', []))
        if guias_csv:
            self.log_callback(f"Encontradas {len(guias_csv)} guias para CSV: '{nome_auditor_selecionado}'.")
            if report_generator.gerar_csv_internacao(guias_csv, pasta_destino_xmls_auditor): self.log_callback(f"CSV de guias gerado em: {pasta_destino_xmls_auditor}")
            else: self.log_callback(f"ERRO ao gerar CSV de guias para '{nome_auditor_selecionado}'.")
        else: self.log_callback(f"Nenhuma guia relevante para CSV: '{nome_auditor_selecionado}'.")
        if qtd_extr > 0: self.log_callback(f"{qtd_extr} XML(s) extraído(s) para '{os.path.basename(pasta_destino_xmls_auditor)}'. Local: {os.path.abspath(pasta_destino_xmls_auditor)}")
        elif sucesso_extr and not erros_l: self.log_callback(f"Nenhum XML extraído de '{os.path.basename(pasta_zips_auditor)}'.")
        if erros_l:
            self.log_callback(f"AVISO: {len(erros_l)} problemas na extração de XMLs:")
            for err in erros_l: self.log_callback(f"  - {err}")
        if not sucesso_extr and not qtd_extr and not erros_l: self.log_callback(f"ERRO: Falha geral ao preparar XMLs para '{nome_auditor_selecionado}'.")
        self.log_callback(f"Preparação de XMLs para '{nome_auditor_selecionado}' concluída.")

    # [MÉTODO MODIFICADO]
    def executar_substituicao_hash(self, caminho_arquivo_ptu):
        self.log_callback(f"Controller: Iniciando substituição de hash para: {caminho_arquivo_ptu}")
        if not caminho_arquivo_ptu: return (False, "Nenhum arquivo fornecido.")

        # 1. Inferir o nome do XML dentro do ZIP e o nome do ZIP correspondente.
        nome_xml_extraido = os.path.basename(caminho_arquivo_ptu) # Ex: N0123456.051
        nome_zip_correspondente = nome_xml_extraido.replace('.051', '.zip') # Ex: N0123456.zip

        # 2. Localizar o caminho do ZIP original.
        # Assumimos que o XML que o usuário selecionou veio da pasta "Correção XML/NomeAuditor".
        # O ZIP original correspondente deve estar na pasta "Distribuição/NomeAuditor".
        diretorio_atual_xml = os.path.dirname(caminho_arquivo_ptu)
        nome_pasta_auditor = os.path.basename(diretorio_atual_xml) # Ex: Auditor1

        # Navega para a pasta raiz da importação (um nível acima de "Correção XML")
        # Ex: "C:/Faturas/Correção XML/Auditor1" -> "C:/Faturas"
        pasta_raiz_importacao = os.path.abspath(os.path.join(diretorio_atual_xml, '..', '..'))

        caminho_zip_original = os.path.join(pasta_raiz_importacao, "Distribuição", nome_pasta_auditor, nome_zip_correspondente)

        if not os.path.exists(caminho_zip_original):
            msg_erro_zip = f"ERRO: Não foi possível localizar o arquivo ZIP original correspondente a '{nome_xml_extraido}'. Esperado em: {caminho_zip_original}"
            self.log_callback(msg_erro_zip)
            return (False, msg_erro_zip)

        # 3. Definir a pasta de destino para os NOVOS ZIPs (Validação CMB)
        pasta_validacao_cmb = os.path.join(pasta_raiz_importacao, "Validação CMB")
        # A pasta será criada dentro da função de file_manager, mas garantimos aqui também
        os.makedirs(pasta_validacao_cmb, exist_ok=True)

        try:
            # 4. Aplicar regras de negócio ao XML (in-place na cópia temporária extraída)
            self.log_callback(f"Controller: Aplicando regras em '{nome_xml_extraido}' antes do cálculo do hash...")
            if not self._aplicar_regras_de_negocio(caminho_arquivo_ptu):
                 self.log_callback(f"Controller: Aviso - Problemas ao aplicar algumas regras em '{nome_xml_extraido}'. Hash será calculado sobre o estado atual.")

            # 5. Calcular o novo Hash
            parser = etree.XMLParser(recover=True, strip_cdata=False, resolve_entities=False)
            arvore = etree.parse(caminho_arquivo_ptu, parser)
            raiz = arvore.getroot()
            if raiz is None:
                self.log_callback(f"  ERRO CRÍTICO: Raiz do XML não pôde ser lida em '{nome_xml_extraido}' para cálculo do hash.")
                return (False, f"Não foi possível ler a raiz do XML em '{nome_xml_extraido}' para o hash.")

            novo_hash = hash_calculator.calcular_hash_moderno(raiz)
            if not novo_hash: return (False, "Falha ao calcular o hash moderno.")

            # 6. Inserir/Substituir o novo Hash no XML
            namespaces = {'ptu': 'http://ptu.unimed.coop.br/schemas/V3_0'}
            no_hash_list = raiz.xpath('/ptu:ptuA500/ptu:hash', namespaces=namespaces)

            if no_hash_list:
                no_hash_list[0].text = novo_hash
                self.log_callback(f"  Hash antigo substituído por: {novo_hash}")
            else:
                self.log_callback(f"  AVISO: Tag <ptu:hash> não encontrada. Criando com: {novo_hash}")
                elemento_raiz_ptuA500 = raiz.xpath('/ptu:ptuA500', namespaces=namespaces)
                if elemento_raiz_ptuA500:
                    nova_tag_hash = etree.Element(f"{{{namespaces['ptu']}}}hash", attrib=None, nsmap=None)
                    nova_tag_hash.text = novo_hash
                    elemento_raiz_ptuA500[0].insert(0, nova_tag_hash)
                else:
                    self.log_callback("  ERRO: Raiz <ptuA500> não encontrada para adicionar <ptu:hash>.")
                    return (False, "Raiz <ptuA500> não encontrada.")

            # 7. Salvar o XML modificado de volta no CAMINHO TEMPORÁRIO (o mesmo caminho_arquivo_ptu)
            # Isso é necessário para que file_manager.recriar_zip_com_novo_xml possa lê-lo do disco.
            arvore.write(caminho_arquivo_ptu, encoding='latin-1', xml_declaration=True, pretty_print=True)
            self.log_callback(f"  XML modificado temporariamente salvo em '{os.path.basename(caminho_arquivo_ptu)}' para reintegração no ZIP.")

            # 8. Chamar a nova função do file_manager para criar o NOVO ZIP na pasta "Validação CMB"
            sucesso_recriacao, caminho_novo_zip_criado_ou_erro = file_manager.recriar_zip_com_novo_xml(
                caminho_zip_original,
                caminho_arquivo_ptu, # O XML modificado está salvo aqui agora
                nome_xml_extraido,   # O nome do XML dentro do ZIP (ex: N0123456.051)
                pasta_validacao_cmb  # Pasta de destino 'Validação CMB'
            )

            # 9. Limpeza e Retorno
            # O arquivo XML temporário (caminho_arquivo_ptu) deve ser removido após a operação do ZIP.
            file_manager.remover_arquivo_se_existe(caminho_arquivo_ptu)
            self.log_callback(f"  Arquivo XML extraído de correção '{os.path.basename(caminho_arquivo_ptu)}' removido após processamento.")

            if sucesso_recriacao:
                self.log_callback(f"  Sucesso: Nova fatura ZIP criada em '{os.path.basename(pasta_validacao_cmb)}'.")
                return (True, f"Fatura atualizada e nova ZIP criada com sucesso em:\n{caminho_novo_zip_criado_ou_erro}")
            else:
                self.log_callback(f"  ERRO: Falha ao criar a nova fatura ZIP. Detalhes: {caminho_novo_zip_criado_ou_erro}")
                return (False, f"Falha ao criar nova fatura ZIP: {caminho_novo_zip_criado_ou_erro}")

        except etree.XMLSyntaxError as exsyn_hash:
            self.log_callback(f"Controller ERRO DE SINTAXE XML ao processar para hash '{nome_xml_extraido}': {exsyn_hash}")
            logging.exception(f"XMLSyntaxError em executar_substituicao_hash para {nome_xml_extraido}")
            return (False, f"Erro de sintaxe XML ao processar para hash: {exsyn_hash}")
        except Exception as e:
            self.log_callback(f"Controller ERRO: Substituição de hash falhou para '{nome_xml_extraido}': {e}")
            logging.exception("Erro crítico no workflow de substituição de hash.")
            return (False, f"Erro inesperado: {e}")