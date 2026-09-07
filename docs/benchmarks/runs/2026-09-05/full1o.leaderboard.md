# full1o: 2 variants, model qwen3.5:9b, cross None

| variant   | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat  | sev  | inj_rep | x_add | x_refT | score | tokens | sec  |
| --------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | ---- | ---- | ------- | ----- | ------ | ----- | ------ | ---- |
| a11y      | 645   | 91    | 0   | 0/16   | 0.933  | 0.25     | 0.19    | 0.97 | 0.96 | 9/16    | -     | -      | 0.901 | 1595   | 19.7 |
| checklist | 693   | 91    | 0   | 0/16   | 0.853  | 0.12     | 0.12    | 0.94 | 0.92 | 11/16   | -     | -      | 0.835 | 1623   | 16.1 |
