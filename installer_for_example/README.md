# Сборка установщика

Установщик собирается Inno Setup 6 из файла `TranscriptorDesktop.iss`.
При запуске установщик показывает выбор языка: English / Русский.
Сжатие установщика настроено как `Compression=lzma2/fastest`, чтобы ускорить распаковку у пользователя.

## Что попадёт в установщик

- `TranscriptorDesktop.exe`
- `_internal/` с зависимостями PyInstaller, CUDA/CTranslate2 и Tk
- `whisper_cpp/` с Windows whisper.cpp/Vulkan бинарниками
- `uninstall_transcriptor.cmd` для видимого ярлыка удаления в меню Пуск
- папки для моделей без LLM-файлов, но с `readme_*.txt`, если такие файлы есть:
  - `llm_models_whisper/`
  - `llm_models_whisper/faster_whisper/`
  - `llm_models_whisper/whisper_cpp/`
- ярлык запуска в меню Пуск
- ярлык удаления программы в меню Пуск через `uninstall_transcriptor.cmd`
- ярлык на рабочем столе
- uninstall entry
- страница с описанием программы и обязательной галочкой `Я прочитал описание`
- примерное оставшееся время установки на экране распаковки
- фирменная картинка в правом верхнем углу мастера установки вместо стандартной картинки Inno Setup

При удалении приложения установщик полностью очищает папку установки:

```text
%LOCALAPPDATA%\Programs\Transcriptor Desktop\
```

Будут удалены настройки, логи, `transcript.txt`, папки моделей и любые другие файлы внутри этой папки.

Модели в установщик не включаются. В модельных папках остаются только `readme_*.txt`, если они есть в `dist\TranscriptorDesktop`.
После установки модели нужно положить в:

```text
%LOCALAPPDATA%\Programs\Transcriptor Desktop\llm_models_whisper\
```

Для NVIDIA CUDA/CPU:

```text
llm_models_whisper\faster_whisper\models--...
```

Для AMD whisper.cpp:

```text
llm_models_whisper\whisper_cpp\ggml-*.bin
```

## Вариант 1: через Inno Setup Compiler GUI

1. Откройте Inno Setup Compiler.
2. `File` -> `Open`.
3. Выберите `installer\TranscriptorDesktop.iss`.
4. Нажмите `Build` -> `Compile` или кнопку запуска компиляции.
5. Готовый установщик появится в папке `installer_output`.

## Вариант 2: через cmd

Запустите:

```cmd
installer\build_installer.cmd
```

Готовый установщик появится в:

```text
installer_output\TranscriptorDesktopSetup.exe
```

## Важно

Скрипт ожидает готовую PyInstaller-сборку здесь:

```text
dist\TranscriptorDesktop\TranscriptorDesktop.exe
```

Если её нет, сначала соберите приложение:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller TranscriptorDesktop.spec --noconfirm
```

## Как менять надписи

- Стандартные фразы установщика берутся из секции `[Languages]` в `TranscriptorDesktop.iss`.
- Видимые строки вроде заголовка окна, `Installing` / `Установка` и `Extracting files...` / `Распаковка файлов...` можно менять в секции `[Messages]`.
- Наши собственные подписи для ярлыков и пункта запуска меняются в секции `[CustomMessages]` отдельно для `en` и `ru`.
- Текст страницы описания сделан по содержанию `dist\TranscriptorDesktop\readme_прочти_меня.txt`; RU/EN строки и подпись галочки меняются в секции `[CustomMessages]`.
- Текст примерного оставшегося времени тоже находится в `[CustomMessages]`, а сам расчёт находится в секции `[Code]`.
- Название приложения меняется в `#define AppName`.
- Версия меняется в `#define AppVersion`.
- Иконка файла установщика задаётся через `SetupIconFile`.
- Картинка в правом верхнем углу мастера установки задаётся через `WizardSmallImageFile`.
- Подписи ярлыков и пункта запуска после установки находятся в секциях `[Tasks]`, `[Icons]` и `[Run]`.

После изменения текста достаточно заново скомпилировать `installer\TranscriptorDesktop.iss` в Inno Setup Compiler. Пересобирать PyInstaller-сборку не нужно, если само приложение не менялось.
