# Historical dataset provenance

Every dataset considered for deployment needs an entry in a versioned JSON
manifest. Never infer storage, redistribution, display, licensing, or
attribution rights from public accessibility.

## Required record

Each entry records its identifier; classification; source and publisher;
source reference; acquisition timestamp; observation period; schema version;
artifact path and SHA-256; transformation version; attribution; storage and
public-display permissions; license/contract evidence; authorization status;
and publication decision.

Classifications are:

- `synthetic_demo`: project-generated data clearly labeled as synthetic.
- `authorized_historical`: real historical data with documented storage and
  public-display authorization.
- `unknown_rights`: data whose permission or provenance is incomplete.

`unknown_rights` must never set `publication_approved` to true. An authorized
historical entry must cite actual evidence; placeholders, assumptions, or a URL
to an accessible file are not evidence of redistribution rights.

## Workflow

1. Preserve the source artifact unchanged in an access-controlled location.
2. Calculate SHA-256 before transformation.
3. Record acquisition time, observation bounds, source, and evidence.
4. Version and document every normalization step; generate a separate digest
   for the deployable artifact.
5. Have an authorized person decide storage and public-display eligibility.
6. Run structural validation and the publication gate.
7. Bind the approved manifest digest to the release record.

```bash
cd backend
python -m app.scripts.validate_provenance ../provenance/deployment-manifest.json
python -m app.scripts.validate_provenance \
  ../provenance/deployment-manifest.json --require-publication-approved
```

The current manifest describes the exact deterministic synthetic staging
fixture loaded by `app.scripts.seed_staging_data`. Its digest, schema version,
instrument count, and price-observation count are verified before any database
operation. It does not establish authorization for any NEPSE-derived historical
dataset and must never be presented as market data.
