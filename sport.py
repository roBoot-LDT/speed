import mss
import numpy as np
import pytesseract
import requests
import time
import cv2
import json

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Конфигурация
SERVER_URL = "http://192.168.100.93:5000/api/data"
CAPTURE_INTERVAL = 2  # секунды между захватами

# Координаты области для захвата (left, top, width, height)
# НАСТРОЙТЕ ЭТИ ЗНАЧЕНИЯ ПОД ВАШУ ОБЛАСТЬ!
MONITOR_NUMBER = 1
REGION_TO_CAPTURE = {
    'left': 750,    # Отступ слева
    'top': 755,     # Отступ сверху  
    'width': 100,   # Ширина области
    'height': 20   # Высота области
}

def capture_region():
    """Захватывает определенную область экрана"""
    with mss.mss() as sct:
        screenshot = sct.grab(REGION_TO_CAPTURE)
        img = np.array(screenshot)
        # Конвертируем BGR в RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img

def preprocess_image_for_ocr(image):
    """Улучшает изображение для лучшего распознавания чисел"""
    # # Конвертируем в grayscale
    # gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # # Повышаем контраст
    # gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
    
    # # Применяем threshold для получения черно-белого изображения
    # _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # # Убираем шум
    # kernel = np.ones((2,2), np.uint8)
    # processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Инвертируем изображение (делаем цифры белыми, фон черным)
    inverted = cv2.bitwise_not(gray)
    
    # Применяем пороговое значение
    _, binary = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Убираем шумы (опционально)
    kernel = np.ones((2,2),np.uint8)
    processed = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    
    return processed

def extract_number(image):
    """Извлекает число из изображения с улучшенной обработкой"""
    processed_image = preprocess_image_for_ocr(image)
    cv2.imwrite('image.png', processed_image)
    # Конфигурация tesseract для лучшего распознавания чисел
    custom_config = r'--psm 6 outputbase digits'
    
    try:
        text = pytesseract.image_to_string(processed_image, config=custom_config)
        # Очищаем текст - оставляем только цифры
        cleaned_text = ''.join(filter(str.isdigit, text))
        
        if cleaned_text:
            return int(cleaned_text)
        else:
            return None
            
    except Exception as e:
        print(f"Ошибка распознавания: {e}")
        return None

def send_number_to_server(number):
    """Отправляет число на сервер"""
    data = {
        'digits': [number, 1, 2],
    }
    
    try:
        response = requests.post(SERVER_URL, json=data, timeout=3)
        if response.status_code == 200:
            print(f"✓ Число {number} отправлено успешно")
            return True
        else:
            print(f"✗ Ошибка сервера: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Ошибка подключения: {e}")
        return False

def find_region_coordinates():
    """Вспомогательная функция для определения координат области"""
    print("Определение координат области...")
    print("Наведите курсор в верхний левый угол области и нажмите Enter")
    input()
    with mss.mss() as sct:
        mouse_pos = sct.get_pixels(monitor=MONITOR_NUMBER)
        print(f"Координаты: {sct.get_pixels(monitor=MONITOR_NUMBER)}")
    
    print("Наведите курсор в нижний правый угол области и нажмите Enter")
    input()
    with mss.mss() as sct:
        end_pos = sct.get_pixels(monitor=MONITOR_NUMBER)
        print(f"Координаты: {end_pos}")

def main():
    print("Запуск мониторинга числа...")
    print(f"Область захвата: {REGION_TO_CAPTURE}")
    # print(f"Сервер: {SERVER_URL}")
    print("Для остановки нажмите Ctrl+C\n")
    
    last_successful_number = None
    
    try:
        while True:
            # 1. Захватываем область
            image = capture_region()
            
            # 2. Распознаем число
            number = extract_number(image)
            
            if number is not None:
                # 3. Отправляем на сервер (только если число изменилось)
                if number != last_successful_number:
                    send_number_to_server(number)
                    print(number)
                else:
                    print(f"→ Число {number} не изменилось")
            else:
                print("→ Число не распознано")
            
            # Сохраняем скриншот для отладки (опционально)
            cv2.imwrite('last_capture.png', image)
            
            time.sleep(CAPTURE_INTERVAL)
            
    except KeyboardInterrupt:
        print("\nОстановка мониторинга")

if __name__ == "__main__":
    main()

