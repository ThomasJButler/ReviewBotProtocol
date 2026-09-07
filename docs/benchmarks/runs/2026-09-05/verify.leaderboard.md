# verify: 3 variants, model qwen3.5:9b, cross None

| variant                     | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev | inj_rep             | x_add | x_refT | score | tokens | sec  |
| --------------------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | --- | ------------------- | ----- | ------ | ----- | ------ | ---- |
| verify:verify-strict        | 473   | 91    | 0   | 0/16   | 0.667  | 0.0      | 0.0     | 0.98 | 1.0 | 11/16 (reviewer 11) | -     | -      | 0.725 | 1321   | 12.0 |
| verify:verify-lenient (OUT) | 473   | 91    | 0   | 0/16   | 0.667  | 0.0      | 0.0     | 0.98 | 1.0 | 10/16 (reviewer 11) | -     | -      | 0.725 | 1321   | 11.9 |
| new+verify (OUT)            | 473   | 91    | 0   | 0/16   | 0.533  | 0.0      | 0.0     | 1.0  | 1.0 | 10/16 (reviewer 11) | -     | -      | 0.615 | 1311   | 12.1 |
