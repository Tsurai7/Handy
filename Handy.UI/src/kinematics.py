import math

# Параметры роборуки
base_height = 12  # см - высота основания
link_lengths = [7, 12, 13]  # длины звеньев

# Текущие углы суставов в градусах (0-180)
current_angles_deg = [90, 90, 90]  # Начальные углы (сервы в среднем положении)

def degrees_to_radians(angles_deg):
    """Конвертирует углы из градусов в радианы"""
    return [math.radians(angle) for angle in angles_deg]

def radians_to_degrees(angles_rad):
    """Конвертирует углы из радиан в градусы"""
    return [math.degrees(angle) for angle in angles_rad]

def forward_kinematics(angles_deg):
    """Прямая кинематика для вычисления позиции схвата (принимает градусы)"""
    theta1, theta2, theta3 = degrees_to_radians(angles_deg)

    # Координаты первого сустава (поворот вокруг оси Z)
    x1 = link_lengths[0] * math.cos(theta1)
    y1 = link_lengths[0] * math.sin(theta1)
    z1 = base_height

    # Координаты второго сустава
    x2 = x1 + link_lengths[1] * math.cos(theta1 + theta2)
    y2 = y1 + link_lengths[1] * math.sin(theta1 + theta2)
    z2 = z1

    # Координаты схвата (конечной точки)
    x3 = x2 + link_lengths[2] * math.cos(theta1 + theta2 + theta3)
    y3 = y2 + link_lengths[2] * math.sin(theta1 + theta2 + theta3)
    z3 = z2

    return (x3, y3, z3)

def move_gripper_direction(direction, step=1.0):
    """
    Управление направлением движения схвата
    direction: tuple (dx, dy, dz) - направление движения
    step: величина изменения углов (в градусах)
    """
    global current_angles_deg

    # Конвертируем текущие углы в радианы для вычислений
    current_angles_rad = degrees_to_radians(current_angles_deg)
    theta1, theta2, theta3 = current_angles_rad

    # Вычисляем якобиан для текущих углов
    J11 = -link_lengths[0] * math.sin(theta1) - link_lengths[1] * math.sin(theta1 + theta2) - link_lengths[2] * math.sin(theta1 + theta2 + theta3)
    J12 = -link_lengths[1] * math.sin(theta1 + theta2) - link_lengths[2] * math.sin(theta1 + theta2 + theta3)
    J13 = -link_lengths[2] * math.sin(theta1 + theta2 + theta3)

    J21 = link_lengths[0] * math.cos(theta1) + link_lengths[1] * math.cos(theta1 + theta2) + link_lengths[2] * math.cos(theta1 + theta2 + theta3)
    J22 = link_lengths[1] * math.cos(theta1 + theta2) + link_lengths[2] * math.cos(theta1 + theta2 + theta3)
    J23 = link_lengths[2] * math.cos(theta1 + theta2 + theta3)

    # Упрощенное псевдообращение якобиана (только для XY плоскости)
    det = J11 * J22 - J12 * J21
    if abs(det) < 1e-6:
        print("Матрица близка к вырожденной. Движение может быть некорректным.")
        return current_angles_deg

    # Вычисляем изменения углов
    dx, dy, dz = direction
    dtheta1 = (J22 * dx - J12 * dy) / det * math.radians(step)
    dtheta2 = (-J21 * dx + J11 * dy) / det * math.radians(step)
    dtheta3 = 0  # Для простоты не изменяем третий угол

    # Обновляем углы в радианах
    new_angles_rad = [
        theta1 + dtheta1,
        theta2 + dtheta2,
        theta3 + dtheta3
    ]

    # Конвертируем обратно в градусы и ограничиваем диапазон 0-180
    new_angles_deg = radians_to_degrees(new_angles_rad)
    new_angles_deg = [max(0, min(180, angle)) for angle in new_angles_deg]

    current_angles_deg = new_angles_deg
    return current_angles_deg

def print_status():
    """Выводит текущее состояние роборуки"""
    pos = forward_kinematics(current_angles_deg)
    print(f"Углы суставов: {[round(a, 1) for a in current_angles_deg]}°")
    print(f"Позиция схвата: x={pos[0]:.2f} см, y={pos[1]:.2f} см, z={pos[2]:.2f} см")

# Пример использования
if __name__ == "__main__":
    print("Начальное состояние:")
    print_status()

    # Двигаем схват в положительном направлении X
    print("\nДвижение вправо (X+)")
    move_gripper_direction((1, 0, 0), step=5)
    print_status()

    # Двигаем схват в положительном направлении Y
    print("\nДвижение вперед (Y+)")
    move_gripper_direction((0, 1, 0), step=5)
    print_status()

    # Двигаем схват по диагонали
    print("\nДвижение по диагонали (X+, Y+)")
    move_gripper_direction((1, 1, 0), step=5)
    print_status()