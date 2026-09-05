# Records

Every reply any model has given, as it gave it. Records are committed
because they are the evidence: the tables and the figure are recomputed
from these files, so a number in the paper can be traced to the raw reply
that produced it without spending quota again.

## What is here

51 files carrying 408 answered decodes. Each writes
`results/<alias>_c<ceiling>[_k<sample>].jsonl`, one JSON object per line,
appended and flushed as it goes. Every record carries the run alias, the
exact `api_model` that answered, the cost ceiling it was given, the
temperature, the SHA-256 of the prompt it was sent, and the raw reply,
parsed or not.

At k = 5 and temperature 0.7, forty decodes to a cell:

| model | 1.1 | 1.25 | 1.5 | 2.0 |
| --- | --- | --- | --- | --- |
| local_qwen | 40 | 40 | 40 | 40 |
| groq_llama70b | 40 | 40 | 40 | 40 |
| gemini_flash | - | 40 | - | 40 |

A dash is a cell that has not been run. `local_qwen_c1p25.jsonl` holds
eight more decodes, one per world at temperature zero, which is a
different question and is never pooled with the rest.

The two Gemini cells are the outstanding runs. Gemini is the one model of
the three whose spending moves with the stated budget, and at two
ceilings that is a contrast rather than a curve; the other two ceilings
would make it four points against the same eight worlds.

## Running the outstanding cells

The runtime config is `configs/models.json`, which is not committed
because it names environment variables and is a local matter. Copy
`configs/models.example.json` and keep only what you are running. The
adapter checks every alias against `configs/model_manifest.json` before a
request is made and refuses a config whose `model` disagrees with it, so
a run cannot quietly call a different checkpoint from the committed ones.

The key goes in the environment, not in the config or on the command
line:

```bash
export GEMINI_API_KEY=...        # the name the config's api_key_env gives
```

Ask for nothing first, and read what it says it would do:

```bash
python tools/run_models.py --config configs/models.json \
    --only gemini_flash --ceiling 1.1 --k 5 --temperature 0.7 --dry-run
```

A cell already answered reports `8 already answered, 0 to ask`, which is
also how you check a config reproduces an existing run before trusting it
with a new one. Then drop `--dry-run`, once per ceiling:

```bash
python tools/run_models.py --config configs/models.json \
    --only gemini_flash --ceiling 1.1 --k 5 --temperature 0.7
python tools/run_models.py --config configs/models.json \
    --only gemini_flash --ceiling 1.5 --k 5 --temperature 0.7
```

That is 80 requests, eight worlds by five samples by two ceilings.

Expect it to take more than one sitting, and pace it. Measured on 5
September 2026, the free tier answers five requests a minute for this
model with a daily ceiling on top of that, so forty decodes is not a
single run. Two things about `--limit` matter here: it caps requests per
`k` file rather than per invocation, so `--limit 4` at `--k 5` asks for
twenty requests and not four, and a refused scenario costs two requests
because the Gemini backend retries once. `--limit 1` with a sleep of
about a hundred seconds between passes is five requests per pass and
stays under the limit.

Nothing is lost when it stops. A failed request is recorded as evidence
and retried rather than counted as answered, the resume guard skips
whatever is already answered, and a file built across two days is
byte-identical to one built in a single run, which
`tests/test_llm_pipeline.py` asserts.

Commit what has answered rather than holding it until a cell is full,
and name the unfinished files in `results/IN_PROGRESS`. CI requires
every committed record file to answer every scenario, and that listing
is the declared exception: a file named there may be incomplete and is
held to every other invariant, while a finished run left on the list
fails the build so the declaration cannot go stale. Remove the names as
the cells fill.

## After a run

Scoring is a separate step, so a metric can be recomputed from the same
replies without spending quota again:

```bash
python tools/score_records.py results/gemini_flash_c1p1_k1.jsonl
python tools/ceiling_sweep.py --alias gemini_flash
```

Then the generated tables and the figure, which are never edited by hand:

```bash
python tools/build_paper_results.py
python tools/build_paper_figures.py
```

Partial runs never enter a table. `runner.require_complete` refuses a
record set that does not answer every scenario exactly once, and the
scoring tool calls it unless explicitly told to allow a partial file for
inspection.
