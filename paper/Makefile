# The ACM class is vendored as sources and generated here, so the build
# does not depend on the local TeX distribution shipping acmart.
#
#   make        the anonymised submission build, paper.pdf
#   make named  the preprint with the author block, paper-named.pdf
#   make both   one command, so the two cannot drift apart
#
# The two differ only in whether NAMEDBUILD is defined before the class
# is read. There is no line to edit and no branch to keep in step.
.PHONY: all named both class clean

all: class
	latexmk -pdf -interaction=nonstopmode paper.tex

named: class
	latexmk -pdf -interaction=nonstopmode -jobname=paper-named \
		-usepretex='\def\NAMEDBUILD{}' paper.tex

both: all named

class: acmart.cls

acmart.cls: acmart.ins acmart.dtx
	latex -interaction=nonstopmode acmart.ins >/dev/null

clean:
	latexmk -C 2>/dev/null || true
	latexmk -C -jobname=paper-named 2>/dev/null || true
	rm -f paper.bbl paper-named.bbl paper.run.xml paper-named.run.xml
