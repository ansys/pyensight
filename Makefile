DATE = $(shell date +'%Y%m%d%H%')

doctest: codespell

codespell:
	python pybuild.py precommit

flake8:
	python pybuild.py precommit

generate:
	python pybuild.py codegen

build:
	python pybuild.py build
	rm -rf build

build-nightly: build

install:
	pip uninstall ansys-ensight -y
	pip install dist/*.whl

install-dev:
	pip uninstall ansys-ensight -y
	pip install -e .

pull-docker:
	bash .ci/pull_ensight_image.sh


test:
	python pybuild.py test


smoketest:
	python -c "from ansys.pyensight.core import LocalLauncher, DockerLauncher"

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
