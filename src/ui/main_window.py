import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget
from services.random_generator import generate_random_number

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Random Number Generator")
        self.setGeometry(100, 100, 300, 200)

        self.layout = QVBoxLayout()

        self.label = QLabel("Press the button to generate a random number.")
        self.layout.addWidget(self.label)

        self.button = QPushButton("Generate Random Number")
        self.button.clicked.connect(self.generate_number)
        self.layout.addWidget(self.button)

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

    def generate_number(self):
        num = generate_random_number(1, 100)
        self.label.setText(f"随机数: {num}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())