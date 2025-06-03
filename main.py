# Conteúdo para: main.py

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QFile, QTextStream # Para carregar o tema escuro

# Importa a nossa classe da Janela Principal que vamos criar em seguida
from gui.main_window import MainWindow 

# Caminho para o arquivo de tema (stylesheet)
THEME_FILE = "gui/assets/dark_theme.qss"

if __name__ == '__main__':
    app = QApplication(sys.argv) # Cria a aplicação PyQt6

    # Tenta carregar e aplicar o tema escuro
    try:
        file = QFile(THEME_FILE)
        if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            stream = QTextStream(file)
            app.setStyleSheet(stream.readAll())
            file.close()
            print(f"INFO: Tema '{THEME_FILE}' carregado com sucesso.")
        else:
            print(f"AVISO: Não foi possível abrir o arquivo de tema: '{THEME_FILE}'. Usando tema padrão.")
    except Exception as e:
        print(f"ERRO: ao tentar carregar o tema '{THEME_FILE}': {e}")

    mainWindow = MainWindow() # Cria uma instância da nossa Janela Principal
    mainWindow.show() # Mostra a janela

    sys.exit(app.exec()) # Inicia o loop de eventos da aplicação e garante uma saída limpa