# Records

Empty. No model has been asked anything yet.

When runs happen, each writes `results/<alias>_c<ceiling>.jsonl`, one JSON
object per line, appended and flushed as it goes. Every record carries the
run alias, the exact `api_model` that answered, the cost ceiling it was
given, the SHA-256 of the prompt it was sent, and the raw reply, parsed or
not. Records are committed; they are the evidence.

Scoring is a separate step, so a metric can be recomputed from the same
replies without spending quota again:

```bash
python tools/score_records.py results/local_qwen_c1p25.jsonl
```

A run interrupted by a daily quota is resumed by repeating the same
command. The resume guard skips whatever is already answered, and a file
built in pieces is byte-identical to one built in a single run, which is
asserted in `tests/test_llm_pipeline.py`.

Partial runs never enter a table. `runner.require_complete` refuses a
record set that does not answer every scenario exactly once, and the
scoring tool calls it unless explicitly told to allow a partial file for
inspection.
