# Framework / Store Python Binding Boundary

When Framework depends on Voodoo Store:

1. inspect the exact current PyO3 surface;
2. verify parameter names, keyword-only behavior, defaults and return shapes;
3. do not infer Python behavior only from Rust APIs;
4. use public binding methods instead of internal encodings;
5. test supported Python versions;
6. preserve typed domain values and serialize only at wire boundaries.

Evolution pattern:

```text
Rust primitive
  -> public Rust API
  -> PyO3 binding
  -> Pythonic Store surface
  -> Runtime adapter
  -> application-facing Voodoo API
```

Do not skip layers by reaching into private Store encodings from Framework.
