# verify2: 3 variants, model qwen3.5:9b, cross None

| variant                     | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev | inj_rep            | x_add | x_refT | x_calls | score | tokens | sec  |
| --------------------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | --- | ------------------ | ----- | ------ | ------- | ----- | ------ | ---- |
| verify:verify-strict (OUT)  | 699   | 91    | 0   | 0/16   | 0.933  | 0.12     | 0.12    | 0.96 | 1.0 | 5/16 (reviewer 10) | -     | -      | -       | 0.901 | 2523   | 19.1 |
| verify:verify-lenient (OUT) | 699   | 91    | 0   | 0/16   | 0.893  | 0.12     | 0.12    | 0.97 | 1.0 | 1/16 (reviewer 10) | -     | -      | -       | 0.868 | 2520   | 19.6 |
| new+verify (OUT)            | 699   | 91    | 0   | 0/16   | 0.893  | 0.12     | 0.12    | 0.97 | 1.0 | 1/16 (reviewer 10) | -     | -      | -       | 0.868 | 2521   | 19.5 |
