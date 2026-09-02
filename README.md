# OZIbridge — разведцентр данных OZI (команда)

Продукт 3 из трёх. Читает ТУ ЖЕ Google-таблицу, что наполняет OZIkids.
Отвечает только команде (белый список ADMIN_IDS).

## Команды
Операции: /leads (кнопки статусов) · /stats · /today · /find
Рост: /deficit · /funnel · /demand
Продукт: /lost · /pairs
Соцанализ/гранты: /access · /demandprofile
DBA/ÖZEN: /profiles · /export · /hexagon

## Деплой (как OZIkids)
1. GitHub → новый репозиторий, залить файлы.
2. Render → Blueprint → env: BRIDGE_TOKEN (OZIbridge), ADMIN_IDS, SHEET_ID, GOOGLE_CREDENTIALS (те же, что у OZIkids).
3. UptimeRobot НЕ нужен — webhook будит бота сам. Старый монитор удалите/на паузу (экономия часов).

## Данные
Читает листы: События, Лиды, Родители-Дети, Центры. Пишет только Статус лида (кнопки).
Регуляторная граница: экспорт обезличен (без имён/телефонов).
