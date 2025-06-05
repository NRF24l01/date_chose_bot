# Используем официальный Python-образ как базовый
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код бота
COPY . .

# Указываем переменные окружения для python (например, не писать .pyc и не буферизовать вывод)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Запуск бота
CMD ["python", "bot.py"]