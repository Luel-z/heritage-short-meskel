# One command: `make film`  (on Windows without make: `python pipeline/run_all.py`)
PY ?= python

.PHONY: setup film film-gpu radio validate smoke

setup:
	$(PY) -m pip install -r requirements.txt

film:                ## the default: no GPU needed (Ken Burns shots, composed score)
	cd pipeline && $(PY) run_all.py

film-gpu:            ## also run the Kaggle stages (Wan 2.2 clips, ACE-Step candidates)
	cd pipeline && $(PY) run_all.py --gpu

radio:
	cd pipeline && $(PY) run_all.py --radio

validate:
	cd pipeline && $(PY) -c "from common import load_storyboard; load_storyboard(); print('storyboard.json valid')"

smoke:
	cd pipeline && $(PY) smoke_test.py
