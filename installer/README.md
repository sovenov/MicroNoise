# Установщик MicroNoise (Inno Setup)

Конфиг для [Inno Setup 6](https://jrsoftware.org/isdl.php), который собирает один
файл `MicroNoise Setup.exe` из готовой сборки `dist\MicroNoise`.

## Что делает установщик

- Ставит программу в `%LOCALAPPDATA%\Programs\MicroNoise` (без прав
  администратора для самой программы).
- Показывает `MicroNoise 1.2.0` в «Программах и компонентах» Windows;
  название приложения остаётся `MicroNoise`.
- Создаёт ярлык в меню **«Пуск»** и, по галочке, на **рабочем столе**.
- На странице **«Выбор дополнительных задач»** показывает галочки установки
  **виртуального аудиокабеля**:
  - **VB-CABLE** (рекомендуется);
  - **Virtual Audio Cable (VAC)**.
- Если галочка отмечена, то **в конце установки MicroNoise** автоматически
  запускается установщик выбранного кабеля. Эти установщики ставят системный
  драйвер, поэтому **сами запросят права администратора (UAC)**. Если отмечены
  обе — они запускаются по очереди.
- Кабели распаковываются во временную папку только при отмеченной галочке и
  удаляются после установки; в саму папку программы они не копируются.

## Предварительно

1. Установить **Inno Setup 6**.
2. Собрать программу, чтобы существовала папка `dist\MicroNoise`
   (`build.bat` в корне репозитория).
3. Отдельно получить дистрибутивы VB-CABLE и Virtual Audio Cable у их
   разработчиков. Сторонние установщики не хранятся в Git. Распаковать полные
   комплекты в локальную папку `virtual_cables_setup\` в корне проекта:

   ```text
   virtual_cables_setup/
     VB-CABLE_45/                       VBCABLE_Setup_x64.exe, INF/SYS/CAT и остальные файлы
     Virtual_Audio_Cable_VAC_4.71_Lite/  setup64.exe, x64/, x86/ и остальные файлы
   ```

   Названия подпапок соответствуют путям в `MicroNoise.iss`. Один EXE без
   соседних файлов драйвера не подходит. Скопировать комплекты в готовую сборку
   (команда из корня проекта):

   ```bat
   xcopy /E /I /Y virtual_cables_setup dist\MicroNoise\virtual_cables_setup
   ```

   Для текущего скрипта нужны оба комплекта; `build.bat` их не скачивает и
   не копирует. При другой версии кабелей проверить пути в `MicroNoise.iss`.

## Сборка установщика

```bat
installer\build_installer.cmd
```

или вручную:

```bat
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\MicroNoise.iss
```

Результат — `installer_output\MicroNoise Setup.exe`.

## Файлы

```
installer\
  MicroNoise.iss        конфиг Inno Setup
  build_installer.cmd   поиск ISCC.exe и компиляция
  README.md             этот файл
```

## Заметки

- Пути в `MicroNoise.iss` заданы относительно папки `installer\`
  (`SourceDir = ..\dist\MicroNoise`), поэтому не переносите `.iss` отдельно от
  репозитория без правки путей.
- Запускаются 64-битные установщики кабелей (`VBCABLE_Setup_x64.exe`,
  `setup64.exe`), т.к. программа 64-битная.
- Интерфейс мастера доступен на русском и английском (выбор языка в начале).

## Другая папка сборки

`SourceDir` можно переопределить через ISCC. Укажите абсолютный путь к готовой
папке приложения с добавленной `virtual_cables_setup`:

```bat
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "/DSourceDir=C:\path\to\MicroNoise" installer\MicroNoise.iss
```

Готовые EXE, журналы и промежуточные комплекты остаются локально в игнорируемых
Git каталогах `installer_output/`, `build/` и `dist/`. Для публикации готовой
программы используйте GitHub Releases.
