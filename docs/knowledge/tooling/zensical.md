---
title: Zensical documentation tooling
description: Current official behavior and limitations for Zensical configuration, builds, validation, navigation, search, Python API reference, publishing, and versioning.
topics: [zensical, documentation, static-site-generator, validation, search, mkdocstrings, github-pages, versioning]
checked_at: 2026-07-24
---

# Zensical Documentation Tooling

This document records mutable facts from Zensical's official documentation,
the Python Package Index, and the official documentation of integrated tools.
It does not decide whether Zensical is suitable for a particular project.

## Release And Compatibility Status

**Authoritative registry:** PyPI listed Zensical `0.0.51` as the current release
on the checked date. The distribution requires Python 3.10 or newer and is
classified as alpha.

Source: [Zensical on PyPI](https://pypi.org/project/zensical/).

**Official guidance:** Zensical says it can be used in production when all
features a project requires are implemented. It also says:

- feature parity with Material for MkDocs is incomplete;
- significant API changes are still being made under `0.0.x` versioning;
- user-facing configuration and CLI breakage is kept to a minimum; and
- there is no announced date for a `1.0.0` release.

Zensical can read `mkdocs.yml` as a transition mechanism. Its documentation
states that this compatibility will remain, although it may move to an optional
package. New projects are directed to the native `zensical.toml` format.

Sources:

- [Zensical frequently asked questions](https://zensical.org/docs/community/faqs/)
- [Zensical configuration basics](https://zensical.org/docs/setup/basics/)

## Configuration, Build, And Preview

The native configuration places current settings under `[project]`.
`site_name` is required. `docs_dir` and `site_dir` are relative to the
configuration file; `docs_dir` cannot currently be `.`. The default output
directory is `site`.

`zensical build` produces a static site. `zensical build --strict` enables
strict mode. `zensical serve` is documented only as a local preview server, not
as a production server.

Sources:

- [Zensical configuration basics](https://zensical.org/docs/setup/basics/)
- [Zensical build command](https://zensical.org/docs/usage/build/)
- [Zensical frequently asked questions](https://zensical.org/docs/community/faqs/#can-i-use-zensical-serve-in-production)

## Navigation, Search, And Link Validation

By default, Zensical derives navigation from the documentation folder and its
Markdown content. Configuration can instead declare an explicit navigation
tree, titles, sections, and external links.

Source:
[Zensical navigation](https://zensical.org/docs/setup/navigation/).

The built-in client-side search is enabled by default, works offline, and
indexes multiple languages. On the checked date, the search interface itself
was available only in English.

Source: [Zensical search](https://zensical.org/docs/setup/search/).

Internal Markdown links and anchors are validated during builds, and these
checks are enabled by default. Strict mode can abort a build when issues are
found. Zensical labels its other current validation checks, including
unresolved references and unused definitions, as deprecated in their current
form because of uncovered edge cases.

Source:
[Zensical validation](https://zensical.org/docs/setup/validation/).

## Python API Reference

Zensical describes its mkdocstrings integration as preliminary. It requires the
separate `mkdocstrings-python` dependency, does not currently support
mkdocstrings backlinks, and does not watch configured handler paths outside the
documentation project for changes.

Source:
[Zensical mkdocstrings integration](https://zensical.org/docs/setup/extensions/mkdocstrings/).

The Python handler uses Griffe to collect API data. Griffe visits Python source
statically and inspects modules dynamically when source cannot be parsed, such
as compiled extension modules. The handler documents two relevant controls:

- `allow_inspection` defaults to true and permits imports when source cannot be
  visited; if stubs exist, disabling inspection may avoid exposing inaccurate
  or low-level compiled members;
- `force_inspection` imports modules even when source is available, but its
  documentation warns against enabling it blindly and points to selective
  inspection or a Griffe extension instead.

Source:
[mkdocstrings-python general options](https://mkdocstrings.github.io/python/usage/configuration/general/).

Griffe's compiled-module guidance says dynamically inspected objects must
report their canonical defining module in `__module__`, rather than a public
re-export location. It specifically supports the common relationship between a
private compiled module and a same-named public module when the difference is
leading underscores.

Source:
[Griffe Python code guidance](https://mkdocstrings.github.io/griffe/guide/users/recommendations/python-code/#make-your-compiled-objects-tell-their-true-location).

**Methodological synthesis:** API-reference generation for a compiled Python
package has at least three independently testable surfaces: static declarations
or stubs, runtime inspection of the installed extension, and rendered public
navigation. Success on one surface does not prove the other two.

## Publishing

Zensical documents a GitHub Actions workflow that builds the static site,
uploads the configured `site_dir` as a Pages artifact, and deploys that
artifact. The repository's Pages source must be configured for GitHub Actions.
The Zensical documentation currently advises against CI caching because its
cache behavior is undergoing revision.

GitHub's own Pages documentation confirms that custom workflows use
`configure-pages`, `upload-pages-artifact`, and `deploy-pages`, and that the
deployment job needs `pages: write` and `id-token: write` permissions.

Sources:

- [Zensical publishing](https://zensical.org/docs/publish-your-site/)
- [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

## Documentation Versioning

Zensical's current multi-version support integrates a Zensical fork of `mike`
for GitHub Pages. Zensical describes this as a bridge until native versioning is
available. The fork is not published on PyPI and must be installed from its Git
repository.

Source:
[Zensical versioning](https://zensical.org/docs/setup/versioning/).

## Evidence Boundary

The facts above establish available features and documented limitations on the
checked date. They do not establish:

- that every required Markdown extension or customization is compatible;
- that generated reference accurately represents a particular compiled
  package;
- that a production deployment is reproducible or secure; or
- that Zensical is preferable to another documentation system.

Those claims require a project-specific feature inventory and direct build,
rendering, and deployment tests.
