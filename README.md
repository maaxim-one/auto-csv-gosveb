# Генератор CSV из ZIP

Веб-приложение для автоматической генерации CSV-файлов из ZIP-архивов с документами (PDF, Word, Excel, изображения). Поддерживает конвертацию PNG/JPEG и Excel в PDF, разбиение архивов по 90 МБ и два режима экспорта: **Школа** и **Детский сад**.

## Возможности

- Загрузка ZIP-архивов с документами (PDF, DOC, DOCX, XLSX, XLS, PNG, JPG)
- Автоматическая конвертация изображений (PNG/JPEG → PDF)
- Автоматическая конвертация Excel (XLSX/XLS → PDF) со всеми листами
- Конвертация Excel через iLovePDF API (приоритет) или MS Excel (fallback)
- Генерация CSV с метадокументами (название, категория, дата, номер и др.)
- Редактирование данных в таблице перед скачиванием
- Два режима экспорта: **Школа** (`Number`) / **Детский сад** (`DocumentNumber`)
- Установка/снятие чекбоксов «Нормативный правовой документ» по категориям
- Автоматическое разбиение на несколько архивов при превышении 90 МБ
- Тёмная и светлая темы
- AJAX-интерфейс без перезагрузок страницы

## Переменные окружения (.env)

Создайте файл `.env` в корне проекта (или используйте `docker compose`):

```bash
# Обязательно: секретный ключ Flask
SECRET_KEY=ваш_надежный_ключ

# Опционально: ключи iLovePDF API (приоритетная конвертация Excel)
# Зарегистрируйтесь на https://developer.ilovepdf.com/signup
ILOVEPDF_PUBLIC_KEY=project_public_xxxxxxxxxxxxxxxx
ILOVEPDF_SECRET_KEY=secret_xxxxxxxxxxxxxxxx
```

### Описание переменных

| Переменная | Обязательность | Описание |
|---|---|---|
| `SECRET_KEY` | **Обязательно** | Секретный ключ Flask для сессий. Генерируется через `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ILOVEPDF_PUBLIC_KEY` | Опционально | Публичный ключ iLovePDF API. Бесплатный план: 250 файлов/месяц |
| `ILOVEPDF_SECRET_KEY` | Опционально | Секретный ключ iLovePDF API |

### Как получить ключи iLovePDF

1. Перейдите на https://developer.ilovepdf.com/signup
2. Зарегистрируйте аккаунт (бесплатно)
3. В консоли разработчика скопируйте **Project public key** и **Secret key**
4. Добавьте их в `.env` как `ILOVEPDF_PUBLIC_KEY` и `ILOVEPDF_SECRET_KEY`

## Приоритет конвертации Excel

При конвертации XLSX/XLS в PDF используется цепочка методов:

| Приоритет | Метод | Требования | Результат |
|---|---|---|---|
| 1 | **iLovePDF API** | Ключи API | Идеальное соответствие оригиналу |
| 2 | **Microsoft Excel** | Windows + MS Excel + pywin32 | Идеальное соответствие (нативный движок) |

Автоматический выбор: метод используется только если доступен. Например, на Linux без ключей iLovePDF Excel-файлы будут пропущены.

> **Важно:** При использовании MS Excel во время конвертирования файлов может кратковременно всплывать окно Microsoft Excel. Это нормальное поведение — приложение работает через COM-автоматизацию, и Excel необходимо открыть файл для экспорта в PDF. Оно закроется автоматически после завершения конвертации каждого файла.

> **Совет:** На Windows с установленным MS Excel конвертация будет идеальной без дополнительных ключей API. Если ключи iLovePDF настроены, они используются с приоритетом, и окно Excel не появляется.

## Запуск

### Через Docker

1. Клонируйте репозиторий:
```bash
git clone https://github.com/maaxim-one/auto-csv-gosveb.git
cd auto-csv-gosveb
```

2. Создайте файл `.env` (см. раздел "Переменные окружения" выше):
```bash
SECRET_KEY=ваш_надежный_ключ
ILOVEPDF_PUBLIC_KEY=project_public_xxxxxxxxxxxxxxxx
ILOVEPDF_SECRET_KEY=secret_xxxxxxxxxxxxxxxx
```

3. Соберите и запустите контейнер:
```bash
docker compose up --build
```

4. Откройте в браузере: **http://localhost:5000**

### Через Python напрямую

1. Клонируйте репозиторий:
```bash
git clone https://github.com/maaxim-one/auto-csv-gosveb.git
cd auto-csv-gosveb
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл `.env` или задайте переменные вручную:
```bash
export SECRET_KEY=ваш_надежный_ключ
export ILOVEPDF_PUBLIC_KEY=project_public_xxxxxxxxxxxxxxxx
export ILOVEPDF_SECRET_KEY=secret_xxxxxxxxxxxxxxxx
```

4. Запустите приложение:
```bash
python wsgi.py
```

5. Откройте в браузере: **http://localhost:5000**

### Продакшен

Для запуска в продакшене используйте gunicorn:

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Создайте файл `.env` со всеми переменными (или экспортируйте):
```bash
export SECRET_KEY=ваш_надежный_ключ
export ILOVEPDF_PUBLIC_KEY=project_public_xxxxxxxxxxxxxxxx
export ILOVEPDF_SECRET_KEY=secret_xxxxxxxxxxxxxxxx
```

3. Запустите gunicorn:
```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 300 app:app
```

**Через Docker Compose:**
```bash
docker compose up -d
```

Для передачи переменных через Docker Compose добавьте их в `docker-compose.yml`:
```yaml
environment:
  - SECRET_KEY=ваш_ключ
  - ILOVEPDF_PUBLIC_KEY=project_public_xxx
  - ILOVEPDF_SECRET_KEY=secret_xxx
```

Или используйте файл `.env` в корне проекта — Docker Compose подхватит его автоматически.

## Готовый exe

Скачайте готовый файл `wsgi.exe` на странице релиза. Для запуска дважды щёлкните по файлу и откройте **http://localhost:5000** в браузере.

**Настройка переменных для exe:**
- Создайте файл `.env` рядом с `wsgi.exe`
- Или задайте переменные через системные переменные Windows

**Сборка exe:**
```bash
py -m PyInstaller wsgi.spec --noconfirm
```
Готовый файл появится в папке `dist/`.

## Структура архива

Архив должен быть **ZIP-файлом** со следующей структурой:

```
archive.zip
├── Категория 1/
│   ├── документ.pdf
│   ├── скан.jpg
│   └── файл.docx
├── Категория 2/
│   ├── файл1.pdf
│   └── файл2.doc
└── loose_file.pdf
```

**Важные моменты:**

| Требование | Описание |
|---|---|
| Формат | Только `.zip` |
| Поддерживаемые файлы | `.pdf`, `.doc`, `.docx`, `.xlsx`, `.xls`, `.png`, `.jpg`, `.jpeg` |
| Категории | Папки верхнего уровня становятся категориями |
| Без категории | Файлы в корне архива получают категорию «Без категории» |
| Конвертация | PNG/JPEG и Excel автоматически конвертируются в PDF |
| Excel | Все листы конвертируются в PDF, кириллица поддерживается |
| Ограничение | Максимальный размер экспорта — 90 МБ на архив |

**Примеры:**

| Структура в архиве | Результат |
|---|---|
| `Приказы/приказ.pdf` | Категория: «Приказы» |
| `Документы/scan.jpg` | Категория: «Документы» (конвертируется в PDF) |
| `Данные/report.xlsx` | Категория: «Данные» (все листы конвертируются в PDF) |
| `report.docx` (в корне) | Категория: «Без категории» |

## Использование

1. Нажмите **«Обработать»** и загрузите ZIP-архив с документами
2. Отредактируйте данные в таблице (название, категория, дата, чекбокс)
3. Выберите режим экспорта: **Школа** или **Детский сад**
4. При необходимости снимите/поставьте чекбоксы «Нормативный правовой документ» по категориям
5. Нажмите **«Скачать архив»**
6. Скачайте готовый ZIP с CSV-файлом и документами

## Структура проекта

```
auto_csv/
├── wsgi.py                 # Точка входа (для gunicorn и PyInstaller)
├── app/
│   ├── __init__.py         # Фабрика приложения Flask
│   ├── config.py           # Конфигурация
│   ├── utils.py            # Вспомогательные функции
│   ├── services/
│   │   ├── csv.py          # Парсинг ZIP, генерация CSV, таблица
│   │   ├── excel.py        # Конвертация Excel → PDF
│   │   ├── image.py        # Конвертация изображений → PDF
│   │   └── job.py          # Файловое хранилище задач
│   └── http/
│       ├── controllers/
│       │   ├── page.py     # Маршруты: /, /upload, /clear
│       │   ├── download.py # Маршруты: /download_zip, /serve_download
│       │   └── api.py      # API: /api/convert_status, /api/version
│       └── middleware/
├── routes/
│   └── web.py              # Регистрация blueprint-ов
├── templates/
│   ├── index.html          # Главная страница
│   └── download_status.html # Статус конвертации
├── static/
│   ├── style.css           # Стили (светлая/тёмная тема)
│   └── app.js              # JavaScript (AJAX, прогресс)
├── tests/
│   ├── conftest.py         # Фикстуры pytest
│   ├── test_controllers.py # Тесты маршрутов
│   ├── test_services_*.py  # Тесты сервисов
│   └── test_utils.py       # Тесты утилит
├── requirements.txt        # Python-зависимости
├── wsgi.spec               # Конфигурация PyInstaller
├── run_build.bat           # Скрипт сборки exe
├── Dockerfile              # Docker-образ
├── docker-compose.yml      # Docker Compose
└── storage/                # Временные файлы (автоочистка)
```

## Требования

### Python зависимости
- Python 3.11+
- Flask 3.0.3+
- Pillow 10.0+
- packaging 21.0+
- ilovepdf 1.0+ (для конвертации Excel через API)
- pywin32 306+ (только Windows, для конвертации через MS Excel)
- gunicorn 21.0+ (для продакшена)

## Лицензия

MIT
