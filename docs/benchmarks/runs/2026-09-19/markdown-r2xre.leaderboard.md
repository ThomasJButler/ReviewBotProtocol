# markdown-r2xre: 1 variants, model qwen3.5:9b, cross gemma4:12b

| variant                     | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev  | inj_rep                      | x_add | x_refT | x_calls | score | tokens | sec  |
| --------------------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | ---- | ---------------------------- | ----- | ------ | ------- | ----- | ------ | ---- |
| doc_reviewer-r2+cross (OUT) | 1010  | 18    | 0   | 1/2    | 0.571  | 1.0      | 0.25    | 0.75 | 0.88 | 2/2 (reviewer 1, silenced 0) | 0.14  | 4      | 18/18   | 0.333 | 1849   | 15.0 |
