# The ACM class is vendored as sources and generated here, so the build
# does not depend on the local TeX distribution shipping acmart.
.PHONY: all class clean

all: class
	latexmk -pdf -interaction=nonstopmode paper.tex

class: acmart.cls

acmart.cls: acmart.ins acmart.dtx
	latex -interaction=nonstopmode acmart.ins >/dev/null

clean:
	latexmk -C 2>/dev/null || true
	rm -f paper.bbl paper.run.xml
