# RSS-Reel — Bundled SearxNG Source Mirror

This repository is the **corresponding source code** for the SearxNG
component bundled in commercial distributions of **RSS-Reel**, as required by
the GNU Affero General Public License version 3 (AGPL-3.0), Section 6(d).

## What this is

A snapshot of the **Windows port of SearxNG** (originally from
[mbaozi/SearXNGforWindows](https://github.com/mbaozi/SearXNGforWindows)) as
bundled in RSS-Reel installer packages. SearxNG is a free internet metasearch
engine. The full AGPL-3.0 license text is in [LICENSE](LICENSE).

This repository exists solely to satisfy AGPL-3.0 Section 6 source-availability
requirements for the SearxNG component. RSS-Reel itself is **not** in this
repository.

## Version

- SearxNG `VERSION_STRING`: `2025.05.13`
- Windows port `VERSION_TAG`: `v0.1.1`
- Upstream sync (per the Windows-port README): commit
  `5d99373bc65c7087ee743a1fe44897bad6065338`

## Upstream sources

- SearxNG upstream:        <https://github.com/searxng/searxng>
- Windows port upstream:   <https://github.com/mbaozi/SearXNGforWindows>

## RSS-Reel and SearxNG

RSS-Reel is proprietary software, sold commercially. RSS-Reel and SearxNG are
independent programs combined only by aggregation:

- SearxNG runs as a separate subprocess (its own Python runtime, its own port
  `5001` bound to `127.0.0.1`).
- RSS-Reel communicates with SearxNG only via SearxNG's standard HTTP API.
- RSS-Reel does not modify SearxNG's source code. Users configure SearxNG's
  `settings.yml` through the RSS-Reel Admin GUI (toggling engines), which is
  data, not code.
- The bundled SearxNG is not exposed over any network. It listens only on
  `127.0.0.1:5001` and is not mapped to the Tor hidden service (per AGPL-3.0
  Section 13).

This is the standard "mere aggregation" model described in the GNU GPL FAQ,
and RSS-Reel itself is therefore not subject to AGPL-3.0.

## License

GNU Affero General Public License version 3 (AGPL-3.0) — see [LICENSE](LICENSE).

The original Chinese-language README from `mbaozi/SearXNGforWindows` is
preserved in [README_UPSTREAM_CN.md](README_UPSTREAM_CN.md).
