# markdown-r1re: 2 variants, model qwen3.5:9b, cross None

| variant      | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat | sev | inj_rep                      | x_add | x_refT | x_calls | score | tokens | sec  |
| ------------ | ----- | ----- | --- | ------ | ------ | -------- | ------- | --- | --- | ---------------------------- | ----- | ------ | ------- | ----- | ------ | ---- |
| code-on-docs | 699   | 18    | 0   | 0/2    | 0.286  | 0.0      | 0.0     | 0.5 | 1.0 | 2/2 (reviewer 1, silenced 0) | -     | -      | -       | 0.444 | 1443   | 7.9  |
| new          | 699   | 18    | 0   | 0/2    | 0.714  | 1.75     | 1.75    | 0.8 | 1.0 | 2/2 (reviewer 1, silenced 0) | -     | -      | -       | 0.333 | 1753   | 15.4 |
