# EEG-AI-EXPERIMENTS

Эксперимент Neuro-SE на дисплейном ПК стенда (Windows). Участник видит код и называет номера строк с багами. Оператор сидит в отдельном окне браузера. Стимул, время реакций и метки LSL идут через PsychoPy. ЭЭГ читается по BrainVision RDA, взгляд — через EyeLink.

Рабочая папка — `neuro_se_experiment`. Команды ниже выполняются из неё, в командной строке или PowerShell.

## Что поставить

1. [Git for Windows](https://git-scm.com/download/win).
2. На Windows `start.bat` переключается на уже установленный Python 3.11 и заново собирает окружение. Для 3.12 у зависимости PsychoPy `pywinhook` нет готовой сборки, поэтому установка обрывается.
3. Для живого айтрекера — SR Research EyeLink Developers Kit. Пакета `pylink` в pip нет.
4. Сеть стенда уже такая: усилитель `100.1.1.3`, порт `51244` (RDA, 32-bit), трекер `100.1.1.1`.

Проверка интерпретатора:

```bat
py -3.11 --version
```

Должно быть `Python 3.11.x`.

## Окружение

```bat
git clone https://github.com/Fllarpell/EEG-AI-EXPERIMENTS.git
cd EEG-AI-EXPERIMENTS\neuro_se_experiment
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt
```

В начале строки появится `(.venv)`. Дальше все команды идут уже из этого окружения.

Живой трекер, после установки Developers Kit:

```bat
python -c "import pylink"
```

Команда должна молча завершиться. Если `pylink` встал в другой Python, его нужно поставить в этот `.venv`, а не в системный интерпретатор.

Если Windows спросит про брандмауэр для Python, разрешите сеть. Иначе LabRecorder не увидит LSL, а RDA не откроет усилитель.

## Запуск

В папке `neuro_se_experiment` запустите `start.bat`. Он создаёт окружение, ставит библиотеки, открывает пульт http://localhost:8765 и окно заданий с заглушками. Пробел начинает сессию.

Живые приборы, из командной строки в этой же папке:

```bat
start.bat live
```

Сначала откроются экраны камеры и калибровки EyeLink, затем окно заданий. Для `pylink` нужен EyeLink Developers Kit в этом же `.venv`.

Пульт отдельно:

```bat
.venv\Scripts\streamlit run operator_app.py --server.port 8765
```

Браузер: http://localhost:8765

Страница «Сессия» задаёт стиль строк, полный экран и заглушки, затем открывает окно заданий. Страница «Задания» правит код и фото, пока проба ещё на экране.

Проверка без приборов:

```bat
.venv\Scripts\python main.py
```

Живые ЭЭГ и айтрекер — те же галочки на странице сессии или сразу:

```bat
.venv\Scripts\python main.py --no-dummy-eeg --no-dummy-gaze
```

Пока заглушки включены, калибровки нет. С выключенной заглушкой айтрекера сначала открываются экраны камеры и калибровки. `C` калибрует, `V` проверяет, Escape закрывает это меню. Окно заданий появляется после выхода. Пробел начинает запись. Сессию останавливает кнопка на странице оператора.

Только усилитель, файлы лягут в текущую папку:

```bat
.venv\Scripts\python hardware\rda_client.py
```

## Куда пишется сессия

Папка `data\` в git не входит.

- `data\experiment.log` — соединение, каналы, маркеры усилителя, калибровка, каждое задание, каждое нажатие.
- `data\trials.csv` — ответы.
- `data\hardware\<сессия>\eeg\` — `datablocks.csv`, `properties.json`, `markers.csv`.
- `data\hardware\<сессия>\gaze\` — у заглушки `gaze.csv`, у EyeLink короткий `.edf`.

Потоки LSL: `NeuroSE_Markers`. У заглушек ещё `NeuroSE_EEG` и `NeuroSE_Gaze`. Живой трекер отдаёт файл EDF.
