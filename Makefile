# Simple makefile to simplify repetitive build env management tasks under posix

CODESPELL_DIRS ?= ./pyensight
CODESPELL_SKIP ?= "*.pyc,*.xml,*.txt,*.gif,*.png,*.jpg,*.js,*.html,*.doctree,*.ttf,*.woff,*.woff2,*.eot,*.mp4,*.inv,*.pickle,*.ipynb,flycheck*,./.git/*,./.hypothesis/*,*.yml,./docs/build/*,./docs/images/*,./dist/*,*~,.hypothesis*,./docs/source/examples/*,*cover,*.dat,*.mac,\#*,PKG-INFO,*.mypy_cache/*,*.xml,*.aedt,*.svg"
CODESPELL_IGNORE ?= "ignore_words.txt"


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

install:
	pip uninstall ansys-ensight -y
	pip install dist/*.whl

install-dev:
	pip uninstall ansys-ensight -y
	pip install -e .

smoketest:
	python -c "from ansys.pyensight import LocalLauncher, DockerLauncher"

clean:
	rm -rf dist build
	rm -rf src/ansys/api
	rm -rf src/*.egg-info
	rm -f codegen/ensight.proto
	rm -f codegen/ensight_api.xml
	rm -f src/ansys/pyensight/ensight_api.py
