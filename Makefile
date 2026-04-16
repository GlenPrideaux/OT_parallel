MAKEFLAGS += -rR --warn-undefined-variables
.SUFFIXES:
SHELL = /bin/sh

PYTHON := python3
PY_FLAGS := 

DEPS_DIR := build/

TARGETS := bible.pdf bible_be.pdf

BRENTON_DEPS := data/brenton_phrase_rules.tsv data/brenton_word_subs.tsv data/verblist.csv

BRENTON_SRC := $(wildcard source/eng-Brenton_usfm/*.usfm)
BRENTON_DST := $(patsubst source/eng-Brenton_usfm/%,build/eng-Brenton-updated_usfm/%,$(BRENTON_SRC))
BRENTON_JSON := $(patsubst source/eng-Brenton_usfm/%.usfm,build/json/Brenton/%.json,$(BRENTON_SRC))

WEB_SRC := $(wildcard source/eng-web_usfm/*.usfm)
WEB_JSON := $(patsubst source/eng-web_usfm/%.usfm,build/json/WEB/%.json,$(WEB_SRC))

WEBBE_SRC := $(wildcard source/eng-webbe_usfm/*.usfm)
WEBBE_JSON := $(patsubst source/eng-webbe_usfm/%.usfm,build/json/WEBBE/%.json,$(WEBBE_SRC))

PRIDEAUX_SRC := $(wildcard source/eng-Prideaux_usfm/*.usfm)
PRIDEAUX_JSON := $(patsubst source/eng-Prideaux_usfm/%.usfm,build/json/Prideaux/%.json,$(PRIDEAUX_SRC))

MAPPING := $(patsubst source/eng-web_usfm/%.usfm,build/mapping/%.csv,$(WEB_SRC))

UPDATE_BRENTON := scripts/01_update_brenton.py
RULES_REVIEW := build/rules_review
PARSE_USFM := scripts/02_parse_usfm.py
SCRIPT_DEFINITIONS := scripts/definitions.py
MAKE_MAPPING_SKEL := scripts/03_make_mapping_skeleton.py
MAKE_INDEX := scripts/04_make_index.py
BUILD_INDEX := build/index
INDEX_CSV := index.csv
MAKE_MASTER_INDEX := scripts/05_make_master_index.py
LATEXMK := max_print_line=1000 latexmk -cd -g -xelatex -interaction=nonstopmode -halt-on-error -auxdir=../build/tex/ -outdir=..
BUILD_PARALLEL_CSV := scripts/06_build_parallel_csv.py
CSV_TO_TEX := scripts/07_csv_to_parallel_tex.py
CSV_US := build/csv/US
CSV_BE := build/csv/BE
TEX_US := tex/US
TEX_BE := tex/BE

all: $(TARGETS)
brenton_updated: $(BRENTON_DST)

build/eng-Brenton-updated_usfm build/rules_review build/json/Brenton build/json/WEB build/json/WEBBE build/json/Prideaux build/mapping build/index build/tex $(CSV_US) $(CSV_BE) $(TEX_US) $(TEX_BE) :
	mkdir -p $@
build/index/% : 
	mkdir -p $@

build/eng-Brenton-updated_usfm/%.usfm: source/eng-Brenton_usfm/%.usfm $(UPDATE_BRENTON) $(SCRIPT_DEFINITIONS) $(BRENTON_DEPS) | $(RULES_REVIEW) build/eng-Brenton-updated_usfm
	$(PYTHON) $(UPDATE_BRENTON) $< -o $@ --review $(RULES_REVIEW) -p -q $(PY_FLAGS)

XREFS := build/xref.tsv

$(XREFS): data/002xref.tsv scripts/00_build_web_xrefs.py
	$(PYTHON) scripts/00_build_web_xrefs.py $(PY_FLAGS)

.SECONDEXPANSION:


build/json/Brenton/%.json: \
  $$(if $$(wildcard source/eng-Brenton-updated_usfm/$$*.usfm),\
      source/eng-Brenton-updated_usfm/$$*.usfm,\
      build/eng-Brenton-updated_usfm/$$*.usfm) \
  $(PARSE_USFM) $(SCRIPT_DEFINITIONS) | build/json/Brenton
	$(PYTHON) $(PARSE_USFM) $< -o $@ $(PY_FLAGS)
build/json/WEB/%.json: source/eng-web_usfm/%.usfm $(PARSE_USFM) $(SCRIPT_DEFINITIONS) $(XREFS) | build/json/WEB 
	$(PYTHON) $(PARSE_USFM) $< -o $@ -x $(XREFS) $(PY_FLAGS)
build/json/WEBBE/%.json: source/eng-webbe_usfm/%.usfm $(PARSE_USFM) $(SCRIPT_DEFINITIONS) $(XREFS) | build/json/WEBBE 
	$(PYTHON) $(PARSE_USFM) $< -o $@ -x $(XREFS) $(PY_FLAGS)
build/json/Prideaux/%.json: source/eng-Prideaux_usfm/%.usfm $(PARSE_USFM) $(SCRIPT_DEFINITIONS) | build/json/Prideaux 
	$(PYTHON) $(PARSE_USFM) $< -o $@ $(PY_FLAGS)

brenton_json: $(BRENTON_JSON)
web_json: $(WEB_JSON)
webbe_json: $(WEBBE_JSON)
prideaux_json: $(PRIDEAUX_JSON)
json: $(BRENTON_JSON) $(WEB_JSON) $(WEBBE_JSON) $(PRIDEAUX_JSON)

build/mapping/%.csv: build/json/WEB/%.json $(MAKE_MAPPING_SKEL) $(SCRIPT_DEFINITIONS) | build/mapping
	$(PYTHON) $(MAKE_MAPPING_SKEL) $< -o $@ $(PY_FLAGS)

mapping: $(MAPPING)

# Index files are dependent on the json files existing, because we're mapping the book name to the file location,
# but we don't really care how old they are since we don't expect the file names to change, so we make the JSON
# files order-only-dependencies. That way updating the json files (or their dependencies) won't trigger an
# unnecessary index rebuild, but building the indices will trigger a build of the JSON files if they're missing.
$(BUILD_INDEX)/Brenton/$(INDEX_CSV): $(MAKE_INDEX) $(SCRIPT_DEFINITIONS) | $(BUILD_INDEX)/Brenton $(BRENTON_JSON) 
	$(PYTHON) $(MAKE_INDEX) build/eng-Brenton-updated_usfm --alternate source/eng-Brenton-updated_usfm --json build/json/Brenton -o $@ $(PY_FLAGS)
$(BUILD_INDEX)/web/$(INDEX_CSV): $(MAKE_INDEX) $(SCRIPT_DEFINITIONS) | $(BUILD_INDEX)/web $(WEB_JSON) 
	$(PYTHON) $(MAKE_INDEX) source/eng-web_usfm --json build/json/WEB -o $@ $(PY_FLAGS)
$(BUILD_INDEX)/webbe/$(INDEX_CSV):  $(MAKE_INDEX) $(SCRIPT_DEFINITIONS) | $(BUILD_INDEX)/webbe $(WEBBE_JSON) 
	$(PYTHON) $(MAKE_INDEX) source/eng-webbe_usfm --json build/json/WEBBE -o $@ $(PY_FLAGS)
$(BUILD_INDEX)/Prideaux/$(INDEX_CSV):  $(MAKE_INDEX) $(SCRIPT_DEFINITIONS) | $(BUILD_INDEX)/Prideaux $(WEBBE_JSON) 
	$(PYTHON) $(MAKE_INDEX) source/eng-Prideaux_usfm --json build/json/Prideaux -o $@ $(PY_FLAGS)

INDICES := \
	$(BUILD_INDEX)/Brenton/$(INDEX_CSV) \
	$(BUILD_INDEX)/web/$(INDEX_CSV) \
	$(BUILD_INDEX)/webbe/$(INDEX_CSV) \
	$(BUILD_INDEX)/Prideaux/$(INDEX_CSV) 

# I've removed the dependencies for index.mk since otherwise any clean will mean a total rebuild of all JSON files
# and that's entirely unnecessary as index.mk will hardly ever change (probably never).
# In the event that it does need to be rebuilt, first make indices then make -B index.mk
index.mk:
	$(PYTHON) $(MAKE_MASTER_INDEX) -o index.mk $(PY_FLAGS)
indices: $(INDICES)

# If index.mk exists, include it. It has no dependencies at this point so there is nothing to trigger a rebuild
# and the file will be included as-is.
INDEX_EXISTS := $(wildcard index.mk)
ifdef INDEX_EXISTS
include index.mk
# But if index.mk does *not* exist, give it dependencies on the other index files so they will be built first,
# if they are not already up to date, then attempt to include it, which should trigger a build using the recipe above.
# (We leave the recipe outside the conditional so make -B index.mk knows how to force a rebuild.)
else
$(info Include file index.mk not found ... rebuilding indices.)
index.mk: $(INDICES)
include index.mk
endif

book_var = $(BOOK_$(1))
book_name = $(subst _, ,$(word 2,$(subst -, ,$(1))))
web_file = $(word 2,$(BOOK_$(1)))
webbe_file = $(word 3,$(BOOK_$(1)))
brenton_file = $(word 4,$(BOOK_$(1)))
prideaux_file = $(word 5,$(BOOK_$(1)))
mapping_file = $(basename $(notdir $(call web_file,$(1)))).csv
mapping_path = $(if $(wildcard data/mapping/$(call mapping_file,$(1))),\
    data/mapping/$(call mapping_file,$(1)),\
    build/mapping/$(call mapping_file,$(1)))

testlist := 002-Genesis 003-Exodus 004-Leviticus 005-Numbers 006-Deuteronomy 007-Joshua 008-Judges 009-Ruth 010-1_Samuel 011-2_Samuel
the_list := $(foreach book, $(testlist), $(call mapping_path,$(book)))
listbooks:
	@echo $(testlist)
	@echo $(the_list)

$(CSV_US)/%_parallel.csv: $$(call web_file,$$*) $$(call brenton_file,$$*) $$(call prideaux_file,$$*) $$(call mapping_path,$$*) \
	$(BUILD_PARALLEL_CSV) $(SCRIPT_DEFINITIONS) | $(CSV_US)
	$(PYTHON) $(BUILD_PARALLEL_CSV) "$(call book_name,$(subst _parallel.csv,,$@))" -q -o $@ -W $(call web_file,$*) -B $(call brenton_file,$*) -P "$(call prideaux_file,$*)" -M $(call mapping_path,$*)
$(CSV_BE)/%_parallel_be.csv: $$(call webbe_file,$$*) $$(call brenton_file,$$*) $$(call prideaux_file,$$*) $$(call mapping_path,$$*) \
	$(BUILD_PARALLEL_CSV) $(SCRIPT_DEFINITIONS) | $(CSV_BE)
	$(PYTHON) $(BUILD_PARALLEL_CSV) "$(call book_name,$(subst _parallel_be.csv,,$@))" --output $@ -b -W $(call webbe_file,$*) -B $(call brenton_file,$*) -P "$(call prideaux_file,$*)" -M $(call mapping_path,$*)

PARALLEL_CSVS := $(foreach book,$(OT),$(CSV_US)/$(book)_parallel.csv)
PARALLEL_BE_CSVS := $(foreach book,$(OT),$(CSV_BE)/$(book)_parallel_be.csv)

$(TEX_US)/%.tex: $(CSV_US)/%.csv $(CSV_TO_TEX) $(SCRIPT_DEFINITIONS) | $(TEX_US)
	$(PYTHON) $(CSV_TO_TEX) $< "$(call book_name,$(subst _parallel.tex,,$@))" --output $@ $(PY_FLAGS)
$(TEX_BE)/%.tex: $(CSV_BE)/%_be.csv $(CSV_TO_TEX) $(SCRIPT_DEFINITIONS) $(TEX_BE)
	$(PYTHON) $(CSV_TO_TEX) $< "$(call book_name,$(subst _parallel.tex,,$@))" --output $@ $(PY_FLAGS)

PARALLEL_TEXS := $(foreach book,$(OT),$(TEX_US)/$(book)_parallel.tex)
PARALLEL_BE_TEXS := $(foreach book,$(OT),$(TEX_BE)/$(book)_parallel.tex)

parallel_csv: $(PARALLEL_CSVS) $(PARALLEL_BE_CSVS)
parallel_tex: $(PARALLEL_TEXS) $(PARALLEL_BE_TEXS)

TEXS := \
	tex/preamble.tex \
	tex/copyright.tex \
	tex/daniel.tex \
	tex/esther.tex \
	tex/intro.tex \
	tex/jeremiah.tex \
	tex/jjr.tex \
	tex/kcen.tex \
	tex/moses.tex \
	tex/poetry.tex \
	tex/prophets.tex \
	tex/samuel.tex \
	tex/the_twelve.tex \
	tex/title.tex

# trying to be clever and have mklatex generate dependencies, but
# it isn't working because the generated paths are relative to tex/
# so they don't work when included here.
# I'm scrapping the idea and just make the pdf files dependent on the explicitly named
# tex files $(TEXS) as well as all the $(PARALLEL_TEX) or $(PARALLEL_TEX_BE) files

# Renewed the idea, but simpler. We won't include all the usepackage sources, only included tex files
GET_TEX_DEPS := scripts/08_get_tex_deps.py
BIBLE_DEPS := $(shell $(PYTHON) $(GET_TEX_DEPS) tex/bible.tex)
BIBLE_BE_DEPS := $(shell $(PYTHON) $(GET_TEX_DEPS) tex/bible.tex -b)

bible.pdf: $(BIBLE_DEPS) | build/tex
	$(LATEXMK) tex/bible.tex
bible_be.pdf: $(BIBLE_BE_DEPS) | build/tex
	$(LATEXMK) -xelatex="xelatex %O '\def\usebritish{}\input{%S}'" -jobname=bible_be tex/bible.tex

%_be.pdf: $$(shell $$(PYTHON) $$(GET_TEX_DEPS) tex/$$*.tex -b)  tex/xfootnotes.sty | build/tex
	$(LATEXMK) -xelatex="xelatex %O '\def\usebritish{}\input{%S}'" -jobname=$*_be tex/$*.tex
%.pdf: $$(shell $$(PYTHON) $$(GET_TEX_DEPS) tex/$$*.tex) tex/xfootnotes.sty | build/tex
	$(LATEXMK) tex/$*.tex

clean: 
	rm -rf build/*
cleaner:
	rm -rf build/*
	rm -rf tex/US tex/BE

cleancounts:
	rm -f build/rules_review/*.csv


.PHONY: brenton_updated clean brenton_json web_json webbe_json mapping indices parallel_csv parallel_tex cleancounts all tex_deps cleaner

