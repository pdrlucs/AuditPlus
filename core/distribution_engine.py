# Conteúdo para: core/distribution_engine.py

def distribuir_faturas_entre_auditores(lista_faturas_processadas, nomes_auditores):
    """
    Distribui as faturas processadas entre os auditores de forma equilibrada
    por valor total e, secundariamente, por quantidade.

    Argumentos:
        lista_faturas_processadas (list): Uma lista de dicionários, onde cada dicionário
                                          representa uma fatura e deve conter pelo menos
                                          as chaves 'nome_zip' (ou outra para identificar a fatura)
                                          e 'valor_total_documento' (como string ou float).
        nomes_auditores (list): Uma lista com os nomes dos auditores.

    Retorna:
        dict: Um dicionário onde as chaves são os nomes dos auditores e os valores
              são dicionários contendo 'faturas' (lista de faturas atribuídas),
              'total_valor' e 'total_quantidade'.
              Retorna None se a entrada for inválida.
    """
    if not lista_faturas_processadas or not nomes_auditores:
        print("ERRO (distribution_engine): Lista de faturas ou nomes de auditores vazia.")
        return None

    # Inicializa o plano de distribuição
    plano_distribuicao = {}
    for nome_auditor in nomes_auditores:
        plano_distribuicao[nome_auditor] = {
            'faturas': [],      # Lista dos dicionários de fatura
            'total_valor': 0.0,
            'total_quantidade': 0
        }

    # Converte o valor das faturas para float e lida com possíveis erros
    faturas_com_valor_numerico = []
    for fatura in lista_faturas_processadas:
        try:
            valor_str = fatura.get('valor_total_documento', "0.0")
            # Tenta substituir vírgula por ponto, caso o valor venha no formato brasileiro
            valor_str_corrigido = valor_str.replace(',', '.') if isinstance(valor_str, str) else valor_str
            valor = float(valor_str_corrigido)
            
            # Cria uma cópia da fatura para não modificar a original diretamente e adiciona o valor numérico
            fatura_copia = fatura.copy()
            fatura_copia['valor_numerico'] = valor 
            faturas_com_valor_numerico.append(fatura_copia)
        except ValueError:
            print(f"AVISO (distribution_engine): Valor '{fatura.get('valor_total_documento')}' da fatura '{fatura.get('nome_zip', 'Desconhecida')}' não é um número válido. Será tratada como valor 0.")
            fatura_copia = fatura.copy()
            fatura_copia['valor_numerico'] = 0.0 # Atribui 0 se a conversão falhar
            faturas_com_valor_numerico.append(fatura_copia)
        except Exception as e:
            print(f"ERRO (distribution_engine): Erro inesperado ao processar valor da fatura '{fatura.get('nome_zip', 'Desconhecida')}': {e}. Será tratada como valor 0.")
            fatura_copia = fatura.copy()
            fatura_copia['valor_numerico'] = 0.0
            faturas_com_valor_numerico.append(fatura_copia)


    # Ordena as faturas pelo valor_numerico em ordem decrescente (da mais cara para a mais barata)
    faturas_ordenadas = sorted(faturas_com_valor_numerico, key=lambda f: f['valor_numerico'], reverse=True)

    # Distribui as faturas
    for fatura_obj in faturas_ordenadas:
        # Encontra o auditor com o menor valor total acumulado
        # Se houver empate no valor, desempata pela menor quantidade de faturas
        auditor_escolhido = min(nomes_auditores, 
                                key=lambda nome_aud: (plano_distribuicao[nome_aud].get('total_valor', 0.0), 
                                                      plano_distribuicao[nome_aud].get('total_quantidade', 0)))
        
        # Atribui a fatura ao auditor escolhido
        plano_distribuicao[auditor_escolhido]['faturas'].append(fatura_obj) # Adiciona o objeto fatura inteiro
        plano_distribuicao[auditor_escolhido]['total_valor'] += fatura_obj['valor_numerico']
        plano_distribuicao[auditor_escolhido]['total_quantidade'] += 1
        
    return plano_distribuicao

# --- Bloco de Teste (para executar 'python core/distribution_engine.py' diretamente) ---
if __name__ == '__main__':
    print("Testando o motor de distribuição...")
    
    # Dados de exemplo para teste
    faturas_exemplo = [
        {'nome_zip': 'FaturaA.zip', 'caminho_zip_original': 'path/A', 'valor_total_documento': '1500.50', 'numero_fatura': 'A001'},
        {'nome_zip': 'FaturaB.zip', 'caminho_zip_original': 'path/B', 'valor_total_documento': '300.00', 'numero_fatura': 'B001'},
        {'nome_zip': 'FaturaC.zip', 'caminho_zip_original': 'path/C', 'valor_total_documento': '1200.75', 'numero_fatura': 'C001'},
        {'nome_zip': 'FaturaD.zip', 'caminho_zip_original': 'path/D', 'valor_total_documento': '800.00', 'numero_fatura': 'D001'},
        {'nome_zip': 'FaturaE.zip', 'caminho_zip_original': 'path/E', 'valor_total_documento': '850.25', 'numero_fatura': 'E001'},
        {'nome_zip': 'FaturaF.zip', 'caminho_zip_original': 'path/F', 'valor_total_documento': '300.00', 'numero_fatura': 'F001'}, # Valor igual a B
        {'nome_zip': 'FaturaG.zip', 'caminho_zip_original': 'path/G', 'valor_total_documento': 'X100.00', 'numero_fatura': 'G001'}, # Valor inválido
    ]
    auditores_exemplo = ["Pedro", "Colega"]

    resultado_distribuicao = distribuir_faturas_entre_auditores(faturas_exemplo, auditores_exemplo)

    if resultado_distribuicao:
        print("\nResultado da Distribuição:")
        for auditor, dados in resultado_distribuicao.items():
            print(f"\nAuditor: {auditor}")
            print(f"  Total de Faturas: {dados['total_quantidade']}")
            print(f"  Valor Total: {dados['total_valor']:.2f}")
            print(f"  Faturas Atribuídas (Nome ZIP):")
            for fat in dados['faturas']:
                print(f"    - {fat['nome_zip']} (Valor: {fat['valor_numerico']:.2f})")
    else:
        print("Não foi possível realizar a distribuição.")