SPHINXBUILD = sphinx-build
SOURCEDIR   = .
BUILDDIR    = _build

.PHONY: help html clean

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)"

html:
	$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(BUILDDIR)/html"
	@echo "Build finished. HTML pages are in $(BUILDDIR)/html."

clean:
	rm -rf "$(BUILDDIR)"
