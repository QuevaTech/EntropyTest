# Submissions

One directory per researcher, one file per attempt:

```
submissions/
└── <github-handle>/
    ├── method.md          # what you did, frozen before you saw the eval stream
    ├── predict.py         # or scores.jsonl for Level 2
    └── results.json       # written by tools/referee.py — this is the verdict
```

`results.json` is produced by the referee, not by you:

```bash
python tools/referee.py l1 --predictions predictions.bin --stream eval.bin --out results.json
```

A pull request without `results.json` is not a submission. A `results.json` that
does not reproduce from your frozen method is a failed submission, and it still
goes into the Hall of Fame under "no finding".
