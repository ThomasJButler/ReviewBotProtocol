# markdown-r2x: 1 variants, model qwen3.5:9b, cross gemma4:12b

| variant                     | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev  | inj_rep                      | x_add | x_refT | x_calls | score | tokens | sec  |
| --------------------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | ---- | ---------------------------- | ----- | ------ | ------- | ----- | ------ | ---- |
| doc_reviewer-r2+cross (OUT) | 1010  | 18    | 0   | 1/2    | 0.5    | 1.0      | 0.25    | 0.71 | 0.86 | 2/2 (reviewer 1, silenced 0) | 0.14  | 2      | 18/18   | 0.278 | 3571   | 39.9 |
