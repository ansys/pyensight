CODESPELL_DIRS ?= ./pyensight
CODESPELL_SKIP ?= "*.pyc,*.xml,*.txt,*.gif,*.png,*.jpg,*.js,*.html,*.doctree,*.ttf,*.woff,*.woff2,*.eot,*.mp4,*.inv,*.pickle,*.ipynb,flycheck*,./.git/*,./.hypothesis/*,*.yml,./docs/build/*,./docs/images/*,./dist/*,*~,.hypothesis*,./docs/source/examples/*,*cover,*.dat,*.mac,\#*,PKG-INFO,*.mypy_cache/*,*.xml,*.aedt,*.svg"
CODESPELL_IGNORE ?= "ignore_words.txt"
DATE = $(shell date +'%Y%m%d')

doctest: codespell

codespell:
	echo "Running codespell"
	codespell $(CODESPELL_DIRS) -S $(CODESPELL_SKIP) # -I $(CODESPELL_IGNORE)

flake8:
	echo "Running flake8"
	flake8 .

generate:
	python codegen/generate.py

build:
	python codegen/generate.py
	python -m build --wheel
	rm -rf build

build-nightly: build

install:
	pip uninstall ansys-ensight -y
	pip install dist/*.whl

install-dev:
	pip uninstall ansys-ensight -y
	pip install -e .

test:
	pytest -rvx --setup-show --cov=ansys.pyensight --cov-report html:coverage-html --cov-report term --cov-config=.coveragerc

smoketest:
	python -c "from ansys.pyensight import LocalLauncher, DockerLauncher"

clean:
	rm -rf dist build
	rm -rf src/ansys/api
	rm -rf **/*.egg-info
	rm -rf coverage-html
	rm -f codegen/ensight.proto
	rm -f codegen/ensight_api.xml
	rm -f src/ansys/pyensight/ensight_api.py
	rm -f src/ansys/pyensight/ens_*.py
	rm -f src/ansys/pyensight/build_info.py
	find . -name \*.pyc -delete
