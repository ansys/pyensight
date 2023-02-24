# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    = 
SPHINXBUILD   = sphinx-build
SOURCEDIR     = source
BUILDDIR      = build

.PHONY: html Makefile

# Put it first so that "make" without argument is like "make html".
html:
	python pybuild.py docs

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)


# customized clean due to examples gallery
clean:
	rm -rf build
	rm -rf $(SOURCEDIR)/_autosummary
	rm -rf $(SOURCEDIR)/_examples
