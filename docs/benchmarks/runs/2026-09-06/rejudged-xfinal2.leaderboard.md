# xfinal2: 1 variants, model qwen3.5:9b, cross gemma4:12b

| variant               | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev  | inj_rep                         | x_add | x_refT | x_calls | score | tokens | sec  |
| --------------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | ---- | ------------------------------- | ----- | ------ | ------- | ----- | ------ | ---- |
| cross:gap-hunter-a-r2 | 699   | 182   | 0   | 0/32   | 0.94   | 0.56     | 0.06    | 0.95 | 0.99 | 19/32 (reviewer 10, silenced 0) | 0.0   | 4      | 182/182 | 0.797 | 3122   | 33.9 |
