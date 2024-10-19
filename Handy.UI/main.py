import serial
import time


def main():
    port_name = '/dev/tty.usbserial-110'
    baud_rate = 9600

    try:
        serial_port = serial.Serial(port_name, baud_rate, timeout=1)
        print("Порт открыт. Готов к отправке команд.")

        while True:
            command = input("Введите команду в формате <индекс сервопривода> <значение угла> (например, 1 90): ")

            if not command.strip():
                continue

            serial_port.write(command.encode('utf-8'))
            print(f"Команда отправлена: {command}")

            time.sleep(1)

    except serial.SerialException as e:
        print(f"Ошибка: {e}")

    finally:
        if serial_port.is_open:
            serial_port.close()
        print("Порт закрыт.")


if __name__ == "__main__":
    main()
