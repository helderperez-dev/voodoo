# Testing and Release Gates

Framework changes should normally validate:

- Ruff format/lint
- mypy / typing boundary
- clean wheel/package install
- supported Python test matrices
- targeted integration tests
- CodeQL/security checks where configured

For Store convergence:

1. validate against the Store candidate only on a temporary branch;
2. publish Store through its official release pipeline;
3. replace Git SHA dependency with the released semantic version range;
4. rerun clean-install and full CI against the published package;
5. merge only after that matrix passes.

Do not manually create release artifacts merely to bypass the official release workflow.
