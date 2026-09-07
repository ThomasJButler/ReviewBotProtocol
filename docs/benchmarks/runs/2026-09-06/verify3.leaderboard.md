# verify3: 2 variants, model qwen3.5:9b, cross None

| variant                       | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev | inj_rep                       | x_add | x_refT | x_calls | score | tokens | sec  |
| ----------------------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | --- | ----------------------------- | ----- | ------ | ------- | ----- | ------ | ---- |
| verify:verify-strict-r2 (OUT) | 359   | 91    | 0   | 0/16   | 0.96   | 0.12     | 0.12    | 0.96 | 1.0 | 6/16 (reviewer 7, silenced 1) | -     | -      | -       | 0.923 | 2532   | 19.9 |
| verify:verify-strict (OUT)    | 299   | 91    | 0   | 0/16   | 0.933  | 0.12     | 0.12    | 0.96 | 1.0 | 2/16 (reviewer 7, silenced 5) | -     | -      | -       | 0.901 | 2450   | 19.7 |
