# utils/xml_parser.py (VERSÃO CORRIGIDA DO NOME DO PARÂMETRO)

from lxml import etree
import os
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - (xml_parser) - %(message)s')
NAMESPACES = {'ptu': 'http://ptu.unimed.coop.br/schemas/V3_0'}

def extrair_dados_fatura_xml(caminho_arquivo_xml):
    nome_base_arquivo = os.path.basename(caminho_arquivo_xml)
    dados_fatura = {}
    try:
        if not os.path.exists(caminho_arquivo_xml):
            logging.error(f"Arquivo XML não encontrado em '{caminho_arquivo_xml}'")
            return None
        parser_xml = etree.XMLParser(recover=True)
        arvore_xml = etree.parse(caminho_arquivo_xml, parser=parser_xml)
        raiz = arvore_xml.getroot()

        def _obter_texto(elemento_pai, xpath_expr):
            elemento_lista = elemento_pai.xpath(xpath_expr, namespaces=NAMESPACES)
            if elemento_lista and elemento_lista[-1].text is not None:
                return elemento_lista[-1].text.strip()
            return None

        dados_fatura['numero_fatura'] = _obter_texto(raiz, './/ptu:cabecalho/ptu:GuiasCobrancaUtilizacao/ptu:Cobranca/ptu:documento1/ptu:nr_Documento')
        dados_fatura['competencia'] = _obter_texto(raiz, './/ptu:cabecalho/ptu:GuiasCobrancaUtilizacao/ptu:Cobranca/ptu:nr_Competencia')
        dados_fatura['codigo_unimed_destino'] = _obter_texto(raiz, './/ptu:cabecalho/ptu:unimed/ptu:cd_Uni_Destino')
        dados_fatura['data_emissao'] = _obter_texto(raiz, './/ptu:cabecalho/ptu:GuiasCobrancaUtilizacao/ptu:Cobranca/ptu:documento1/ptu:dt_EmissaoDoc')
        dados_fatura['data_vencimento'] = _obter_texto(raiz, './/ptu:cabecalho/ptu:GuiasCobrancaUtilizacao/ptu:Cobranca/ptu:documento1/ptu:dt_VencimentoDoc')
        dados_fatura['valor_total_documento'] = _obter_texto(raiz, './/ptu:cabecalho/ptu:GuiasCobrancaUtilizacao/ptu:Cobranca/ptu:documento1/ptu:vl_TotalDoc')
        return dados_fatura
    except etree.XMLSyntaxError as exsyn:
        logging.error(f"O arquivo XML '{nome_base_arquivo}' está mal formado. Detalhes: {exsyn}")
        return None
    except Exception as e:
        logging.exception(f"Erro inesperado ao processar cabeçalho do XML '{nome_base_arquivo}': {e}")
        return None

def _try_parse_float(valor_str, nome_campo="valor", guia_id="N/A", arquivo_base="N/A"):
    if valor_str is None:
        return 0.0
    try:
        return float(str(valor_str).strip().replace(',', '.'))
    except ValueError:
        logging.warning(f"'{nome_campo}' inválido ('{valor_str}') na guia '{guia_id}' do arquivo '{arquivo_base}'. Tratado como 0.0.")
        return 0.0

def extrair_guias_internacao_relevantes(caminho_arquivo_xml, numero_fatura_pai, 
                                        codigos_hm_t00_a_ignorar, # Nome do parâmetro ajustado para corresponder à chamada
                                        valor_minimo_guia=25000.0):
    nome_base_arquivo = os.path.basename(caminho_arquivo_xml)
    print(f"--- XML Parser: Iniciando extração em '{nome_base_arquivo}' para Fatura '{numero_fatura_pai}'. Filtro >= {valor_minimo_guia:.2f} ---")

    guias_internacao_filtradas = []
    map_tipo_internacao = { "1": "Hospitalar", "2": "Hospital-dia", "3": "Domiciliar" }

    try:
        if not os.path.exists(caminho_arquivo_xml):
            logging.error(f"Arquivo XML '{caminho_arquivo_xml}' não encontrado.")
            return []

        parser_xml = etree.XMLParser(recover=True)
        arvore_xml = etree.parse(caminho_arquivo_xml, parser=parser_xml)
        raiz = arvore_xml.getroot()
        guias_internacao_xml = raiz.xpath('.//ptu:guiaInternacao', namespaces=NAMESPACES)

        print(f"!!! DEBUG PRINT (XML Parser) !!! XML: {nome_base_arquivo}, Guias <ptu:guiaInternacao> encontradas: {len(guias_internacao_xml)}")

        if not guias_internacao_xml:
            logging.info(f"Nenhuma tag <ptu:guiaInternacao> encontrada em '{nome_base_arquivo}'.")
            print(f"!!! DEBUG PRINT (XML Parser) !!! Nenhuma tag <ptu:guiaInternacao> encontrada em '{nome_base_arquivo}'.")
            return []

        for i, guia_xml_node in enumerate(guias_internacao_xml):
            valor_total_guia_calc_para_filtro = 0.0
            valor_total_real_da_guia = 0.0

            nr_guia_node = guia_xml_node.xpath('./ptu:dadosGuia/ptu:nr_Guias/ptu:nr_GuiaTissPrestador', namespaces=NAMESPACES)
            nr_guia = nr_guia_node[-1].text.strip() if nr_guia_node and nr_guia_node[-1].text is not None else f"GuiaDesconhecida_{i+1}"

            id_benef_node = guia_xml_node.xpath('./ptu:dadosBeneficiario/ptu:id_Benef', namespaces=NAMESPACES)
            codigo_beneficiario = id_benef_node[-1].text.strip() if id_benef_node and id_benef_node[-1].text is not None else ""

            nm_benef_node = guia_xml_node.xpath('./ptu:dadosBeneficiario/ptu:nm_Benef', namespaces=NAMESPACES)
            nome_beneficiario = nm_benef_node[-1].text.strip() if nm_benef_node and nm_benef_node[-1].text is not None else ""

            rg_internacao_node = guia_xml_node.xpath('./ptu:dadosInternacao/ptu:rg_Internacao', namespaces=NAMESPACES)
            rg_internacao_cod = rg_internacao_node[-1].text.strip() if rg_internacao_node and rg_internacao_node[-1].text is not None else ""
            tipo_internacao_desc = map_tipo_internacao.get(rg_internacao_cod, f"Cod:{rg_internacao_cod}")

            if nome_base_arquivo == "N0183113.051" and nr_guia == "255521452": 
                print(f"\n!!! DEBUG XML SNIPPET for {nome_base_arquivo}, Guia {nr_guia} !!!")
                try:
                    print(etree.tostring(guia_xml_node, pretty_print=True).decode('utf-8')) # type: ignore
                except Exception as e_tostring:
                    print(f"Erro ao tentar converter guia_xml_node para string: {e_tostring}")
                print("!!! END DEBUG XML SNIPPET !!!\n")

            procedimentos_executados_nodes = guia_xml_node.xpath('./ptu:dadosGuia/ptu:procedimentosExecutados', namespaces=NAMESPACES)
            if not procedimentos_executados_nodes:
                procedimentos_executados_nodes = guia_xml_node.xpath('.//ptu:procedimentosExecutados', namespaces=NAMESPACES)

            for j, proc_exec_node in enumerate(procedimentos_executados_nodes):
                valor_procedimento_atual_para_soma = 0.0

                tp_tabela_node = proc_exec_node.xpath('.//ptu:procedimentos/ptu:tp_Tabela', namespaces=NAMESPACES)
                tp_Tabela_atual = tp_tabela_node[-1].text.strip() if tp_tabela_node and tp_tabela_node[-1].text is not None else None

                cd_servico_node = proc_exec_node.xpath('.//ptu:procedimentos/ptu:cd_Servico', namespaces=NAMESPACES)
                cd_Servico_atual = cd_servico_node[-1].text.strip() if cd_servico_node and cd_servico_node[-1].text is not None else None
                print(f"       !!! DEBUG PRINT (XML Parser) !!! Guia '{nr_guia}', ProcExec {j+1}: tp_Tabela = {tp_Tabela_atual}, cd_Servico = {cd_Servico_atual}")

                vl_serv_node_list = proc_exec_node.xpath('.//ptu:valores/ptu:vl_ServCobrado', namespaces=NAMESPACES)
                if vl_serv_node_list and vl_serv_node_list[-1].text is not None:
                    valor_serv = _try_parse_float(vl_serv_node_list[-1].text, "vl_ServCobrado", nr_guia, nome_base_arquivo)
                    valor_procedimento_atual_para_soma += valor_serv

                tx_adm_node_list = proc_exec_node.xpath('.//ptu:taxas/ptu:tx_AdmServico', namespaces=NAMESPACES)
                if tx_adm_node_list and tx_adm_node_list[-1].text is not None:
                    valor_taxa = _try_parse_float(tx_adm_node_list[-1].text, "tx_AdmServico", nr_guia, nome_base_arquivo)
                    valor_procedimento_atual_para_soma += valor_taxa

                vl_co_node_list = proc_exec_node.xpath('.//ptu:valores/ptu:vl_CO_Cobrado', namespaces=NAMESPACES)
                if vl_co_node_list and vl_co_node_list[-1].text is not None:
                    valor_co = _try_parse_float(vl_co_node_list[-1].text, "vl_CO_Cobrado", nr_guia, nome_base_arquivo)
                    valor_procedimento_atual_para_soma += valor_co
                
                tx_adm_co_node_list = proc_exec_node.xpath('.//ptu:taxas/ptu:tx_AdmCO', namespaces=NAMESPACES)
                if tx_adm_co_node_list and tx_adm_co_node_list[-1].text is not None:
                    valor_taxa_co = _try_parse_float(tx_adm_co_node_list[-1].text, "tx_AdmCO", nr_guia, nome_base_arquivo)
                    valor_procedimento_atual_para_soma += valor_taxa_co
                
                valor_total_real_da_guia += valor_procedimento_atual_para_soma

                procedimento_ignorado_para_filtro = False
                motivo_filtro = ""

                if tp_Tabela_atual == '22':
                    procedimento_ignorado_para_filtro = True
                    motivo_filtro = "Tabela 22"
                elif tp_Tabela_atual == '00' and cd_Servico_atual and cd_Servico_atual in codigos_hm_t00_a_ignorar: # Usando o nome do parâmetro
                    procedimento_ignorado_para_filtro = True
                    motivo_filtro = f"HM Tabela 00 (Cód: {cd_Servico_atual})"
                
                if procedimento_ignorado_para_filtro:
                    logging.debug(f"Guia '{nr_guia}', Proc {j+1} (Tab:{tp_Tabela_atual}, Cód:{cd_Servico_atual}), Vlr {valor_procedimento_atual_para_soma:.2f} IGNORADO V_Filtro ({motivo_filtro}).")
                    print(f"       !!! DEBUG PRINT (XML Parser) !!! Guia '{nr_guia}', ProcExec {j+1}: {motivo_filtro} -> IGNORADO para FILTRO")
                else:
                    if tp_Tabela_atual in ['00', '18', '19', '20']:
                        valor_total_guia_calc_para_filtro += valor_procedimento_atual_para_soma
                        logging.debug(f"Guia '{nr_guia}', Proc {j+1} (Tab:{tp_Tabela_atual}, Cód:{cd_Servico_atual}), Vlr {valor_procedimento_atual_para_soma:.2f} SOMADO ao V_Filtro.")
                        print(f"       !!! DEBUG PRINT (XML Parser) !!! Guia '{nr_guia}', ProcExec {j+1}: Tabela {tp_Tabela_atual} ({cd_Servico_atual}) -> SOMADO ao FILTRO (Valor: {valor_procedimento_atual_para_soma:.2f})")
                    else:
                        logging.debug(f"Guia '{nr_guia}', Proc {j+1} (Tab:{tp_Tabela_atual}, Cód:{cd_Servico_atual}), Vlr {valor_procedimento_atual_para_soma:.2f} NÃO SOMADO ao V_Filtro (Tabela não é 00,18,19,20 ou ignorada).")
                        print(f"       !!! DEBUG PRINT (XML Parser) !!! Guia '{nr_guia}', ProcExec {j+1}: Tabela {tp_Tabela_atual} ({cd_Servico_atual}) -> NÃO SOMADO ao V_Filtro (Tabela não explicitamente considerada nem ignorada)")
                
                print(f"     !!! DEBUG PRINT (XML Parser) !!! Guia '{nr_guia}', ProcExec {j+1}: Valor TOTAL DESTE PROCEDIMENTO = {valor_procedimento_atual_para_soma:.2f}. Totais da GUIA -> Filtro: {valor_total_guia_calc_para_filtro:.2f}, Real: {valor_total_real_da_guia:.2f}")
            
            print(f"!!! DEBUG PRINT (XML Parser) !!! DETALHE GUIA (FIM): Guia '{nr_guia}' (FP: {numero_fatura_pai}), Benef: {codigo_beneficiario}, Nome: {nome_beneficiario}, V_Filtro: {valor_total_guia_calc_para_filtro:.2f}, V_Real: {valor_total_real_da_guia:.2f}, TipoIntern: {tipo_internacao_desc}")

            if valor_total_guia_calc_para_filtro >= valor_minimo_guia:
                guia_info = {
                    "fatura_pai": numero_fatura_pai,
                    "numero_guia": nr_guia,
                    "codigo_beneficiario": codigo_beneficiario,
                    "nome_beneficiario": nome_beneficiario,
                    "tipo_internacao": tipo_internacao_desc,
                    "valor_filtro": valor_total_guia_calc_para_filtro,
                    "valor_total_real": valor_total_real_da_guia
                }
                guias_internacao_filtradas.append(guia_info)
                print(f"!!! DEBUG PRINT (XML Parser) !!! GUIA ADICIONADA: Guia '{nr_guia}' (FP: {numero_fatura_pai}) ADICIONADA (Valor p/ Filtro: {valor_total_guia_calc_para_filtro:.2f})")
        
        return guias_internacao_filtradas

    except etree.XMLSyntaxError as exsyn:
        logging.error(f"O arquivo XML '{nome_base_arquivo}' (guias) está mal formado. Detalhes: {exsyn}")
        return []
    except Exception as e:
        logging.exception(f"Erro inesperado ao processar guias de internação em '{nome_base_arquivo}': {e}")
        return []

if __name__ == '__main__':
    logging.info("Executando xml_parser.py como script principal para teste.")
    
    CAMINHO_XML_EXEMPLO = 'SEU_ARQUIVO_XML_DE_TESTE.xml' 
    FATURA_PAI_EXEMPLO = 'FATURA_EXEMPLO_001'
    HM_TAB00_IGNORAR_EXEMPLO = {"2210101055", "2210101063"} 
    VALOR_CORTE = 25000.0

    if os.path.exists(CAMINHO_XML_EXEMPLO):
        print(f"\n--- Testando extração de guias do arquivo: {CAMINHO_XML_EXEMPLO} ---")
        print(f"--- Códigos HM Tabela 00 a ignorar para teste: {HM_TAB00_IGNORAR_EXEMPLO} ---")
        guias = extrair_guias_internacao_relevantes(
            CAMINHO_XML_EXEMPLO,
            FATURA_PAI_EXEMPLO,
            HM_TAB00_IGNORAR_EXEMPLO, 
            VALOR_CORTE
        )
        if guias:
            print(f"\n--- Guias Relevantes Encontradas ({len(guias)}) ---")
            for guia_idx, guia_item in enumerate(guias):
                print(f"Guia {guia_idx+1}: {json.dumps(guia_item, indent=2, ensure_ascii=False)}")
        else:
            print("\n--- Nenhuma guia relevante encontrada no arquivo de teste ou com os critérios. ---")
    else:
        print(f"Arquivo de teste '{CAMINHO_XML_EXEMPLO}' não encontrado. "
              "Adapte o bloco if __name__ == '__main__' com um caminho de XML válido e códigos de exemplo.")

    logging.info("Teste de xml_parser.py concluído.")