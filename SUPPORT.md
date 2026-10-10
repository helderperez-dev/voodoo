# Support policy

Production Profile 1 supports Framework 3.2.x on the Python versions declared
by `pyproject.toml`, with one Runtime process owning one Voodoo Store writer.
Support requests should include the Framework/Store versions, operating system,
configuration profile, reproducible steps, and sanitized logs. Distributed
multi-writer, replication, and automatic failover behavior are outside this
profile.
