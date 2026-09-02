# Розробка RCooLeR Colored Contour Icons

## Збірка

Потрібні Python 3.10+, Pillow 12 та Python 2.7 для компіляції необов’язкового
runtime-fallback. Приклад:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m colored_contour_icons.build `
  --game-root 'D:\Games\World_of_Tanks' `
  --output "$PWD\build" `
  --include-atlases
```

Параметр `--include-atlases` створює окремий add-on лише з `battleAtlas`.
`vehicleMarkerAtlas`, маркери над технікою, Python і SWF до нього не входять.

## Підготовка до нового клієнта

Номер клієнта читається з `version.xml`; папки `mods/<версія>` є лише резервним
джерелом, якщо метаданих немає. Пакети `gui-part*.pkg` обробляються за номером
частини, а не лексикографічно. Генератор відкриває кожен GUI-пакет один раз під
час обходу контурів.

Для попередньої перевірки потрібна окрема реконструйована копія нового клієнта:
`version.xml`, `res/packages/scripts.pkg` та GUI-пакети з контурами й
`battleAtlas.xml`/`battleAtlas.dds`. Не підставляйте атлас попереднього патча.

RC-збірку можна створити без зміни стабільної версії мода або наявних релізів:

```powershell
$env:PYTHONPATH = "$PWD\src"
$candidateClient = 'D:\staging\WoT-2.4.0.0'
$candidateOutput = "$PWD\build\candidate-2.4.0.0"
py -3 -m colored_contour_icons.build `
  --game-root $candidateClient --output $candidateOutput `
  --include-atlases --mod-version 0.3.4-rc.1

py -3 tools\audit_candidate.py `
  --baseline 'D:\Games\World_of_Tanks' --candidate $candidateClient `
  --core "$candidateOutput\com.rcooler.colored_contour_icons_0.3.4-rc.1.wotmod" `
  --addon "$candidateOutput\com.rcooler.colored_contour_icons_battle_atlas_0.3.4-rc.1_wg2.4.0.0.wotmod" `
  --output "$candidateOutput\compatibility-audit.json"
py -3 -m pytest -q
```

Аудит порівнює визначення машин, PNG та геометрію атласу; перевіряє прозорість
і розмір **кожної** іконки, вихідні хеші XML/DDS, незмінність заголовка DDS,
XML та всіх DXT5-блоків поза контурами. Також перевіряються CRC, `ZIP_STORED`
і відсутність Python/SWF/`vehicleMarkerAtlas`. Запускайте без `python -O`.

Готовий тестовий ZIP має містити два `.wotmod` у `mods/<нова версія клієнта>/`.
Зовнішніх залежностей або конфігів для цього комплекту не потрібно. RC-архіви
зберігайте лише в окремій папці `build/candidate-*`, не замінюючи `releases/`
і стабільні посилання в README.

Після виходу патча спочатку повторіть `colored_contour_icons.verify_atlas`
вже з остаточно встановленим клієнтом. Якщо хеш XML або DDS відрізняється від
попереднього завантаження, перебудуйте пакет. Після цього вручну перевірте
запуск, усі режими бойових «вух», TAB, живі/знищені машини, кольори класів,
варіанти зі стандартним XVM і без нього та відсутність змін маркерів/мінікарти.
Спеціальні подієві спрайти, яких немає серед окремих клієнтських PNG-контурів,
залишаються рідними; їх не підміняємо здогадними зображеннями.

## Походження формату

Реалізація читання BXML заснована на описі формату з GPL-3.0 проєкту
[TankIconMaker / WotDataLib](https://github.com/ktkr3d/TankIconMaker), який
посилається на World of Tanks Mod Tools від KatzSmile. Проєкт поширюється за
умовами GNU GPL v3.
