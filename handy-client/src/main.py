import tkinter as tk

class RobotArmControlUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Управление роборукой")
        self.root.geometry("400x600")

        # Создаем 6 слайдеров для управления разными аспектами роборуки
        self.sliders = []
        self.labels = []
        self.slider_values = [0] * 6  # Храним текущие значения слайдеров

        for i in range(6):
            label = tk.Label(self.root, text=f"Слайдер {i+1}:")
            label.grid(row=i, column=0, padx=10, pady=5, sticky="w")
            self.labels.append(label)

            slider = tk.Scale(self.root, from_=0, to=180, orient="horizontal", command=self.update_slider_value)
            slider.set(50)  # Устанавливаем начальное значение слайдера
            slider.grid(row=i, column=1, padx=10, pady=5)
            self.sliders.append(slider)

        # Кнопка для применения значений слайдеров
        self.apply_button = tk.Button(self.root, text="Применить", command=self.apply_values)
        self.apply_button.grid(row=6, column=0, columnspan=2, pady=20)

    def update_slider_value(self, value):
        """Обновляем значения слайдеров."""
        for i, slider in enumerate(self.sliders):
            self.slider_values[i] = slider.get()

    def apply_values(self):
        """Обрабатываем значения слайдеров (например, для управления роборукой)."""
        # Здесь можно добавить код для отправки значений в систему управления роборукой
        print("Значения слайдеров:", self.slider_values)
        # Например, передаем значения в управление роборукой (методы могут быть специфичными для вашей реализации)
        # arm_controller.move_to_angles(self.slider_values)

def main():
    # Создание главного окна
    root = tk.Tk()
    # Инициализация и запуск UI
    app = RobotArmControlUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
