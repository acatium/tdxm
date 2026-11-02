UV ?= $(HOME)/.local/bin/uv
RUN = $(UV) run python -m shopfloor.run

.PHONY: gen check seed reset demo propose scenario apply archive
gen:  ## Regenerate everything in gen/ from the vocabulary
	$(UV) run python -m shopfloor.generate

check:  ## Every exit criterion that can be a test. Needs the instance (.env) and network for the validators.
	$(UV) run pytest -q

reset:  ## Remove everything the seed planted (about 25 minutes: task tables delete row by row)
	$(UV) run python -m shopfloor.seed.apply reset
	rm -f data/confirmations.yaml  # scenario stand-ins belong to one run; a stale file would pre-confirm the next

seed:  ## Plant the aged instance (about 4 minutes) and check it
	$(UV) run python -m shopfloor.seed.apply apply
	$(UV) run python -m shopfloor.seed.apply status

propose:  ## Phase 1 on a seeded instance: diagnose, then write every change as a proposal for a person
	$(RUN) diagnose
	$(RUN) cleanup --no-apply
	$(RUN) perturb
	$(RUN) policy
	$(RUN) proposals

apply:  ## Phase 2, after a person has written data/confirmations.yaml: apply what was confirmed, run, check, close
	$(RUN) cleanup
	$(RUN) after
	$(RUN) policy
	$(RUN) proposals
	$(RUN) enforcement
	$(RUN) live
	$(RUN) integration
	$(RUN) close
	$(MAKE) archive

scenario:  ## SCENARIO ONLY: the stand-in process owner confirms every open proposal (labelled in the file)
	$(RUN) scenario

demo: reset seed propose  ## From a blank instance to the proposals; then a person confirms, then make apply

archive:  ## Copy the run's evidence into results/run/
	mkdir -p results/run
	cp var/seed.json var/diagnosis.json var/gaps.json var/cleanup.json var/after.json var/policy.json var/proposals.yaml \
	   var/enforcement.json var/live.json var/integration.json var/close.json var/perturb.json results/run/
	cp data/confirmations.yaml results/run/confirmations.yaml
	head -c 200000 var/gaps.ocsf.jsonl > results/run/gaps.ocsf.sample.jsonl
