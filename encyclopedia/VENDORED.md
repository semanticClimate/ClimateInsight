# Bundled semanticClimate Encyclopedia helpers

These modules are included so a ClimateInsight clone can build and serve its
Encyclopedia without another repository checkout.

Source: semanticClimate/encyclopedia, local integration snapshot taken on
13 November 2026. The source checkout's base commit was
`0ba0d13ba07c13e0e082dc42a2408e68fa256127`; the snapshot also includes its local
exchange, IPCC adapter, and entry-generation changes. It is not an unmodified
copy of that upstream commit.

The original Apache 2.0 license is retained in [LICENSE](LICENSE).
`vendor_manifest.json` records the imported modules and their source checksums.
The only local adjustment to those modules is `Resources.TEMP_DIR`, which uses
ClimateInsight's ignored `tmp/encyclopedia/` directory instead of `temp/`.

Included functionality:

- Lightweight reading and rendering of portable Encyclopedia entries.
- IPCC text preparation and keyword-count aggregation.
- Wikipedia enrichment, disambiguation, and normalized entry rendering.
- Supporting resource paths and HTML helpers.

The unrelated Encyclopedia application, chatbot, command-line entry point, and
download workflows are not bundled. Some shared source modules retain helpers
for those workflows; ClimateInsight does not invoke them. Third-party build
dependencies remain in `requirements-encyclopedia.txt`; runtime serving uses
the lightweight exchange module and `requirements.txt`.
