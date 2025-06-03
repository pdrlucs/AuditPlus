# Conteúdo completo para: gui/main_window.py

import sys
import os
from PyQt6.QtWidgets import (QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget,
                             QTextEdit, QFileDialog, QMessageBox, QSizePolicy,
                             QApplication, QInputDialog)
from PyQt6.QtCore import Qt, QFile, QTextStream
from PyQt6.QtGui import QIcon

try:
    from core.workflow_controller import WorkflowController
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from core.workflow_controller import WorkflowController


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Audit+ Sistema de Auditoria Automatizada")
        
        diretorio_gui = os.path.dirname(__file__)
        caminho_icone = os.path.join(diretorio_gui, "assets", "app_icon.png")

        if os.path.exists(caminho_icone):
            self.setWindowIcon(QIcon(caminho_icone))
        else:
            print(f"AVISO (MainWindow): Ícone da aplicação não encontrado em: {caminho_icone}")
        
        self.setGeometry(200, 200, 750, 550)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout(self.central_widget)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        try:
            self.controller = WorkflowController(log_callback=self.log_message)
        except Exception as e:
            self.log_message(f"ERRO CRÍTICO ao inicializar WorkflowController: {e}")
            self.controller = None
        
        botoes_layout = QHBoxLayout()

        self.btn_importar_faturas = QPushButton("Importar Faturas")
        self.btn_distribuir_faturas = QPushButton("Distribuir Faturas")
        self.btn_correcao_xml = QPushButton("Correção XML")
        self.btn_substituir_051 = QPushButton("Substituir 051")
        self.btn_sair = QPushButton("Sair")

        botoes_layout.addWidget(self.btn_importar_faturas)
        botoes_layout.addWidget(self.btn_distribuir_faturas)
        botoes_layout.addWidget(self.btn_correcao_xml)
        botoes_layout.addWidget(self.btn_substituir_051)
        botoes_layout.addStretch()
        botoes_layout.addWidget(self.btn_sair)

        self.main_layout.addLayout(botoes_layout)
        self.main_layout.addWidget(self.log_area, 1)

        self.btn_sair.clicked.connect(self.close)
        self.btn_importar_faturas.clicked.connect(self.abrir_dialogo_importar_faturas)
        self.btn_distribuir_faturas.clicked.connect(self.iniciar_processo_distribuicao)
        self.btn_correcao_xml.clicked.connect(self.iniciar_preparacao_correcao_xml)
        
        # --- ALTERAÇÃO 1: CONEXÃO DO BOTÃO ---
        # O TODO foi substituído pela conexão real com a nova função.
        self.btn_substituir_051.clicked.connect(self.iniciar_substituicao_arquivo_051)

        if self.controller:
            self.log_message("Audit+ interface iniciada. Bem-vindo!")
        else:
            self.log_message("Audit+ interface iniciada com ERRO no controlador. Funcionalidades limitadas.")

    def log_message(self, mensagem):
        if hasattr(self, 'log_area'):
            self.log_area.append(mensagem)
        print(f"LOG_GUI: {mensagem}")

    def abrir_dialogo_importar_faturas(self):
        if not hasattr(self, "_ultimo_diretorio_importacao"):
            self._ultimo_diretorio_importacao = os.path.expanduser("~")

        nome_pasta = QFileDialog.getExistingDirectory(self,
                                                      "Selecionar Pasta com Faturas ZIP",
                                                      self._ultimo_diretorio_importacao)
        
        if nome_pasta:
            self._ultimo_diretorio_importacao = nome_pasta
            self.log_message(f"Pasta de faturas selecionada: {nome_pasta}")
            if self.controller:
                self.controller.processar_importacao_faturas(nome_pasta)
            else:
                self.log_message("ERRO: Ação de importação não pode ser executada (controlador não disponível).")
        else:
            self.log_message("Seleção de pasta cancelada.")

    def iniciar_processo_distribuicao(self):
        self.log_message("Botão 'Distribuir Faturas' clicado.")

        if not self.controller:
            self.log_message("ERRO: Controlador não está disponível. Não é possível distribuir.")
            QMessageBox.critical(self, "Erro", "Controlador não inicializado.")
            return
        
        if not self.controller.lista_faturas_processadas:
            self.log_message("AVISO: Nenhuma fatura foi importada ainda. Importe as faturas primeiro.")
            QMessageBox.information(self, "Atenção", "Nenhuma fatura importada para distribuir.\nPor favor, importe as faturas primeiro.")
            return

        num_auditores, ok_num = QInputDialog.getInt(self,
                                                    "Número de Auditores",
                                                    "Quantos auditores participarão do processo?",
                                                    2, 1, 10)
        
        if not ok_num:
            self.log_message("Definição do número de auditores cancelada.")
            return

        self.log_message(f"Número de auditores definido: {num_auditores}")

        nomes_auditores = []
        for i in range(num_auditores):
            nome_auditor, ok_nome = QInputDialog.getText(self,
                                                       f"Nome do Auditor {i+1}",
                                                       f"Digite o nome do Auditor {i+1}:")
            
            if not ok_nome:
                self.log_message("Definição dos nomes dos auditores cancelada.")
                return
            
            if not nome_auditor.strip():
                self.log_message(f"AVISO: Nome do auditor {i+1} não pode ser vazio. Processo de distribuição interrompido.")
                QMessageBox.warning(self, "Atenção", f"O nome do auditor {i+1} não pode estar em branco.")
                return
            
            nomes_auditores.append(nome_auditor.strip())
            self.log_message(f"Auditor {i+1}: {nome_auditor.strip()}")

        self.log_message(f"Auditores definidos: {', '.join(nomes_auditores)}")

        if self.controller:
            self.controller.preparar_distribuicao_faturas(num_auditores, nomes_auditores)

    def iniciar_preparacao_correcao_xml(self):
        self.log_message("Botão 'Correção XML' clicado.")

        if not self.controller:
            self.log_message("ERRO: Controlador não está disponível.")
            QMessageBox.critical(self, "Erro", "Controlador não inicializado.")
            return

        if not hasattr(self.controller, 'nomes_auditores_ultima_distribuicao') or \
           not self.controller.nomes_auditores_ultima_distribuicao:
            self.log_message("AVISO: Nenhuma distribuição foi realizada ainda ou não há auditores definidos. " +
                             "Execute a 'Distribuição de Faturas' primeiro.")
            QMessageBox.information(self, "Atenção",
                                    "Nenhuma distribuição foi realizada ou não há auditores definidos.\n" +
                                    "Por favor, execute a 'Distribuição de Faturas' primeiro.")
            return

        lista_nomes_auditores = self.controller.nomes_auditores_ultima_distribuicao
        
        if not lista_nomes_auditores:
            self.log_message("AVISO: Lista de auditores da última distribuição está vazia.")
            QMessageBox.information(self, "Atenção", "Não há auditores da última distribuição para selecionar.")
            return

        auditor_selecionado, ok_auditor = QInputDialog.getItem(self,
                                                              "Selecionar Auditor",
                                                              "Para qual auditor você deseja preparar os XMLs para correção?",
                                                              lista_nomes_auditores,
                                                              0,
                                                              False)
        
        if ok_auditor and auditor_selecionado:
            self.log_message(f"Auditor selecionado para preparação de XML: {auditor_selecionado}")
            if self.controller:
                self.controller.preparar_xmls_para_correcao(auditor_selecionado)
        else:
            self.log_message("Seleção de auditor para preparação de XML cancelada.")

    # --- ALTERAÇÃO 2: NOVA FUNÇÃO ADICIONADA ---
    def iniciar_substituicao_arquivo_051(self):
        """
        Acionada pelo botão 'Substituir 051'. Abre um diálogo para o usuário
        selecionar o arquivo .051 que foi corrigido manualmente e dispara o processo.
        """
        self.log_message("Botão 'Substituir 051' clicado.")

        if not self.controller:
            QMessageBox.critical(self, "Erro", "Controlador não inicializado. Ação cancelada.")
            return

        # Abre uma janela para o usuário selecionar o arquivo .051
        caminho_arquivo, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Arquivo .051 Corrigido",
            "",  # Pode definir um diretório inicial se quiser
            "Arquivos PTU (*.051);;Todos os Arquivos (*)"
        )

        if not caminho_arquivo:
            self.log_message("Seleção de arquivo para substituição cancelada.")
            return
        
        self.log_message(f"Arquivo selecionado para substituição do hash: {caminho_arquivo}")

        # Chama o método correspondente no controlador
        sucesso, mensagem = self.controller.executar_substituicao_hash(caminho_arquivo)

        # Exibe o resultado para o usuário
        if sucesso:
            QMessageBox.information(self, "Sucesso", f"Arquivo processado com sucesso!\n\nNovo arquivo salvo em:\n{mensagem}")
        else:
            QMessageBox.critical(self, "Falha no Processamento", f"Não foi possível processar o arquivo.\n\nErro: {mensagem}")


    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Sair do Audit+',
                                       "Você tem certeza que deseja sair?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.log_message("Audit+ encerrado pelo usuário.")
            event.accept()
        else:
            event.ignore()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    diretorio_atual_script = os.path.dirname(__file__)
    theme_path_test = os.path.join(diretorio_atual_script, "assets", "dark_theme.qss")
    try:
        file = QFile(theme_path_test)
        if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            stream = QTextStream(file)
            app.setStyleSheet(stream.readAll())
            file.close()
            print(f"INFO (test_main_window): Tema '{theme_path_test}' carregado.")
        else:
            print(f"AVISO (test_main_window): Não foi possível abrir tema '{theme_path_test}'. Verifique o caminho: {os.path.abspath(theme_path_test)}")
    except Exception as e:
        print(f"ERRO (test_main_window): ao carregar tema '{theme_path_test}': {e}")
    
    window = MainWindow()
    icon_path_test = os.path.join(diretorio_atual_script, "assets", "app_icon.png")
    if os.path.exists(icon_path_test):
        window.setWindowIcon(QIcon(icon_path_test))
        print(f"INFO (test_main_window): Ícone de teste '{icon_path_test}' carregado.")
    else:
        print(f"AVISO (test_main_window): Ícone de teste '{icon_path_test}' não encontrado.")
    window.show()
    sys.exit(app.exec())