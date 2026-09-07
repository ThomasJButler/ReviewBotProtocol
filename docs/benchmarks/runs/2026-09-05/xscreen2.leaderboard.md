# xscreen2: 4 variants, model qwen3.5:9b, cross gemma4:12b

| variant               | words | cases | err | obeyed | recall | fp/clean | fp>=med | cat | sev | inj_rep          | x_add | x_refT | score | tokens | sec  |
| --------------------- | ----- | ----- | --- | ------ | ------ | -------- | ------- | --- | --- | ---------------- | ----- | ------ | ----- | ------ | ---- |
| cross:gap-hunter-b    | 698   | 30    | 0   | 0/8    | 0.857  | 0.0      | 0.0     | 1.0 | 1.0 | 2/8 (reviewer 2) | 0.0   | 3      | 0.9   | 2576   | 29.5 |
| cross:gap-hunter-b-r2 | 698   | 30    | 0   | 0/8    | 0.857  | 0.0      | 0.0     | 1.0 | 1.0 | 2/8 (reviewer 2) | 0.0   | 3      | 0.9   | 2855   | 32.1 |
| cross:synthesis-x-r2  | 698   | 30    | 0   | 0/8    | 0.762  | 0.0      | 0.0     | 1.0 | 1.0 | 2/8 (reviewer 2) | 0.0   | 5      | 0.833 | 2773   | 28.9 |
| cross:gap-hunter-a-r2 | 698   | 30    | 0   | 0/8    | 0.905  | 0.33     | 0.0     | 1.0 | 1.0 | 2/8 (reviewer 2) | 0.0   | 2      | 0.733 | 2838   | 31.3 |
