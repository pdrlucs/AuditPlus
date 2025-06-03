# core/hash_calculator.py (NOVA VERSÃO - LÓGICA MODERNA)

import hashlib
import logging
import re
from lxml import etree

# Configuração do logging para este módulo
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - (hash_calculator) - %(message)s')

def calcular_hash_moderno(xml_tree_root):
    """
    Calcula o hash MD5 de um arquivo PTU A500 seguindo a lógica moderna.

    Este método replica o processo do programa 'Ajusta-Layout-XML-PTU-A500.p':
    1.  Recebe um objeto lxml etree (a árvore XML já em memória).
    2.  Converte a árvore XML inteira para uma string de texto.
    3.  Usa Expressões Regulares (Regex) para remover todas as tags XML e
        espaços desnecessários, deixando apenas o conteúdo textual concatenado.
    4.  Calcula o hash MD5 sobre essa string limpa.

    Args:
        xml_tree_root: O elemento raiz da árvore XML (objeto lxml.etree._Element).

    Returns:
        str: O hash MD5 hexadecimal em letras minúsculas, ou None se ocorrer um erro.
    """
    if xml_tree_root is None:
        logging.error("A raiz da árvore XML fornecida é nula. Não é possível calcular o hash.")
        return None

    try:
        # Etapa 1: Converter a árvore XML em memória para uma string.
        # 'unicode' garante que obtemos uma string de texto, não bytes.
        # Usamos with_tail=False para não duplicar texto de nós aninhados.
        # 1. Serializa a árvore XML para bytes.
        xml_bytes = etree.tostring(xml_tree_root)

        # 2. Decodifica os bytes para uma string de texto usando a codificação 'latin-1'.
        xml_string = xml_bytes.decode('latin-1')

        # Etapa 2: Limpeza com Regex para replicar a lógica do Progress ABL.
        
        # 2.1. Remove a própria tag de hash antiga, caso exista, para não interferir no novo cálculo.
        # Isso torna a função re-executável com segurança.
        string_sem_hash_antigo = re.sub(r'<ptu:hash>.*?</ptu:hash>', '', xml_string, flags=re.IGNORECASE | re.DOTALL)
        
        # 2.2. Remove quebras de linha e espaços entre as tags (ex: '>  <' vira '><').
        string_sem_espacos = re.sub(r'>\s+<', '><', string_sem_hash_antigo)

        # 2.3. Remove TODAS as tags XML, deixando apenas o conteúdo.
        string_final_apenas_conteudo = re.sub(r'<[^>]+>', '', string_sem_espacos).strip()
        
        # 2.4. Trata entidades XML que podem ter sido convertidas para caracteres.
        # Embora o tostring deva lidar com isso, é uma garantia extra.
        string_final_apenas_conteudo = string_final_apenas_conteudo.replace('&', '&amp;')
        string_final_apenas_conteudo = string_final_apenas_conteudo.replace('<', '&lt;')
        string_final_apenas_conteudo = string_final_apenas_conteudo.replace('>', '&gt;')


        # Etapa 3: Calcular o hash MD5 sobre a string final.
        # Usamos 'latin1' (ISO-8859-1) que é o padrão de fato para estes sistemas legados.
        hash_resultado = hashlib.md5(string_final_apenas_conteudo.encode('latin1')).hexdigest()

        logging.info(f"Hash moderno calculado com sucesso: {hash_resultado}")
        return hash_resultado

    except Exception as e:
        logging.exception(f"Erro inesperado durante o cálculo do hash moderno: {e}")
        return None