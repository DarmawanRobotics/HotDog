# Dharma documentation: draw.io diagrams, the technical manual and the paper.
#
#   make            diagrams (when draw.io is installed), then the manual and the paper
#   make diagrams   export diagrams/*.drawio to diagrams/pdf (cropped) and diagrams/svg
#   make manual     build/manual/dharma_manual.pdf
#   make paper      build/paper/dharma.pdf
#   make pdf        manual and paper, copied to pdf/ (the committed PDFs)
#   make reference  regenerate manual/generated (SRC: dir with the dharma_* checkouts)
#   make clean      remove build/ (the exported diagrams are kept: they are committed)
#
# The exported diagrams and pdf/ are committed, so LaTeX builds without draw.io. Without draw.io on PATH the
# diagram step is skipped with a note. Headless export needs xvfb-run.

DRAWIO ?= drawio
XVFB ?= xvfb-run -a
LATEXMK ?= latexmk
LATEXFLAGS ?= -pdf -interaction=nonstopmode -halt-on-error -file-line-error

SOURCES := $(wildcard diagrams/*.drawio)
NAMES := $(notdir $(basename $(SOURCES)))
PDFS := $(addprefix diagrams/pdf/,$(addsuffix .pdf,$(NAMES)))
SVGS := $(addprefix diagrams/svg/,$(addsuffix .svg,$(NAMES)))
HAVE_DRAWIO := $(shell command -v $(DRAWIO) 2>/dev/null)

COMMON := authors.tex macros.tex
MANUAL_TEX := manual/dharma_manual.tex $(wildcard manual/chapters/*.tex manual/generated/*.tex)
PAPER_TEX := paper/dharma.tex $(wildcard paper/sections/*.tex) paper/references.bib

.PHONY: all diagrams manual paper pdf reference clean

all: diagrams manual paper

ifneq ($(HAVE_DRAWIO),)
diagrams: $(PDFS) $(SVGS)

diagrams/pdf/%.pdf: diagrams/%.drawio
	@mkdir -p $(@D)
	$(XVFB) $(DRAWIO) --no-sandbox -x -f pdf --crop -o $@ $< 2>/dev/null

diagrams/svg/%.svg: diagrams/%.drawio
	@mkdir -p $(@D)
	$(XVFB) $(DRAWIO) --no-sandbox -x -f svg --svg-theme light -o $@ $< 2>/dev/null
	@# drop the PNG fallbacks of the HTML labels (browsers render the labels themselves)
	sed -i -E 's#<image [^>]*xlink:href="data:image/png;base64,[^"]*"/>##g' $@
else
diagrams:
	@echo "$(DRAWIO) not found: using the committed diagrams/pdf and diagrams/svg"
endif

manual: build/manual/dharma_manual.pdf

paper: build/paper/dharma.pdf

build/manual/dharma_manual.pdf: $(MANUAL_TEX) $(COMMON) $(PDFS)
	cd manual && BIBINPUTS=../paper: $(LATEXMK) $(LATEXFLAGS) -outdir=../build/manual dharma_manual.tex

build/paper/dharma.pdf: $(PAPER_TEX) $(COMMON) $(PDFS)
	cd paper && $(LATEXMK) $(LATEXFLAGS) -outdir=../build/paper dharma.tex

# the PDFs committed in pdf/, readable on GitHub without a LaTeX installation
pdf: manual paper
	@mkdir -p pdf
	cp build/manual/dharma_manual.pdf pdf/dharma_manual.pdf
	cp build/paper/dharma.pdf pdf/dharma_paper.pdf

SRC ?= ../..
reference:
	python3 manual/tools/reference.py --src $(SRC)

clean:
	rm -rf build
