# EEG-AI-EXPERIMENTS

Эксперимент Neuro-SE: участник видит код, называет номера строк с багами, оператор управляет сессией из отдельного окна. Стимул, время реакций и метки LSL идут через PsychoPy. ЭЭГ и айтрекер подключаются теми же блоками старта и остановки, что и на стенде: BrainVision RDA и EyeLink.

Рабочая папка — `neuro_se_experiment`. Все команды ниже выполняются из неё.

## Что нужно

- Python **3.12**. На 3.13 PsychoPy не ставится.
- Для живого айтрекера — SR Research EyeLink Developers Kit. Библиотеки `pylink` нет в pip.
- Сеть стенда: усилитель `100.1.1.3:51244` (RDA, 32-bit), трекер `100.1.1.1`.

## macOS

```bash
brew install python@3.12
git clone https://github.com/Fllarpell/EEG-AI-EXPERIMENTS.git
cd EEG-AI-EXPERIMENTS/neuro_se_experiment
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
```

Если `python --version` показывает 3.13, это другой интерпретатор. Окружение уже собрано командой выше, дальше вызывайте `.venv/bin/python`.

## Windows

Поставьте Python 3.12 с [python.org](https://www.python.org/downloads/) и отметьте Add python.exe to PATH.

```bat
git clone https://github.com/Fllarpell/EEG-AI-EXPERIMENTS.git
cd EEG-AI-EXPERIMENTS\neuro_se_experiment
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt
```

На дисплейном ПК EyeLink поставьте Developers Kit и добейтесь, чтобы `python -c "import pylink"` в этом же `.venv` проходил. Если набор поставил `pylink` в другой Python, этот пакет нужно сделать доступным именно активированному 3.12.

## Запуск

Пульт оператора:

```bash
# macOS / Linux, из neuro_se_experiment
.venv/bin/streamlit run operator_app.py --server.port 8765
```

```bat
.venv\Scripts\streamlit run operator_app.py --server.port 8765
```

Откройте http://localhost:8765. Страница «Сессия» выбирает стиль строк, полный экран и заглушки, затем открывает окно заданий. Страница «Задания» правит код и фото: файл перечитывается во время идущей пробы.

Проверка без приборов, прямо из консоли:

```bash
.venv/bin/python main.py
```

Живые ЭЭГ и айтрекер:

```bash
.venv/bin/python main.py --no-dummy-eeg --no-dummy-gaze
```

Те же флаги есть на странице сессии. Пока заглушки включены, калибровки нет и вместо приборов пишутся синтетические потоки.

С выключенной заглушкой айтрекера сначала открываются экраны камеры и калибровки EyeLink. `C` — калибровка, `V` — проверка, Escape закрывает это меню. Окно заданий появляется после выхода из меню. Пробел начинает запись. Останавливает сессию кнопка на странице оператора.

Только усилитель, в текущую папку:

```bash
.venv/bin/python hardware/rda_client.py
```

## Куда пишется сессия

Каталог `data/` в git не входит.

- `data/experiment.log` — соединение, каналы, маркеры усилителя, калибровка, каждое задание, каждое нажатие.
- `data/trials.csv` — ответы.
- `data/hardware/<сессия>/eeg/` — `datablocks.csv`, `properties.json`, `markers.csv`.
- `data/hardware/<сессия>/gaze/` — для заглушки `gaze.csv`, для EyeLink короткий `.edf`.

Потоки LSL: `NeuroSE_Markers`, а у заглушек ещё `NeuroSE_EEG` и `NeuroSE_Gaze`. Живой трекер отдаёт файл EDF.
