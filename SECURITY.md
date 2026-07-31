# Security

Solaris is local-first. It does not send task data to a network service.

## Reporting

If you find a vulnerability in the CLI or file handling, open a private advisory on GitHub
or email the maintainer via the profile linked on the repository.

## Notes

- Task files may contain secrets if you paste them in — treat `Board/` like any other source tree.
- Do not run untrusted Markdown through automation that shells out without review.
