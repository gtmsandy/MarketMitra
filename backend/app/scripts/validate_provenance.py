"""Validate deployment dataset provenance without external dependencies."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

_CLASSIFICATIONS = {
    "synthetic_demo",
    "authorized_historical",
    "unknown_rights",
}
_REQUIRED_FIELDS = {
    "dataset_identifier",
    "classification",
    "source",
    "publisher",
    "source_reference",
    "acquisition_timestamp",
    "observation_period",
    "schema_version",
    "artifact_path",
    "sha256",
    "transformation_version",
    "attribution_requirements",
    "storage_permission",
    "redistribution_public_display_permission",
    "license_or_contract_evidence_reference",
    "authorization_status",
    "publication_approved",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _artifact_path(manifest_path: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    if path.is_absolute():
        return path
    return (manifest_path.parent / path).resolve()


def validate_manifest(
    manifest_path: Path, *, require_publication_approved: bool = False
) -> list[str]:
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Unable to read provenance manifest: {exc}"]

    if not isinstance(manifest, dict):
        return ["manifest root must be an object"]
    if manifest.get("manifest_version") != 1:
        errors.append("manifest_version must be 1")
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        return errors + ["datasets must be a non-empty list"]

    identifiers: set[str] = set()
    for index, dataset in enumerate(datasets):
        prefix = f"datasets[{index}]"
        if not isinstance(dataset, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = sorted(_REQUIRED_FIELDS - dataset.keys())
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(missing)}")
            continue

        identifier = dataset["dataset_identifier"]
        if not isinstance(identifier, str) or not identifier.strip():
            errors.append(f"{prefix}.dataset_identifier must be non-empty")
        elif identifier in identifiers:
            errors.append(f"{prefix}.dataset_identifier must be unique")
        else:
            identifiers.add(identifier)

        classification = dataset["classification"]
        if classification not in _CLASSIFICATIONS:
            errors.append(f"{prefix}.classification is invalid")

        digest = dataset["sha256"]
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            errors.append(f"{prefix}.sha256 must be a lowercase SHA-256 digest")
        elif not isinstance(dataset["artifact_path"], str):
            errors.append(f"{prefix}.artifact_path must be a non-empty string")
        else:
            artifact = _artifact_path(manifest_path, dataset["artifact_path"])
            try:
                actual_digest = sha256(artifact.read_bytes()).hexdigest()
            except OSError as exc:
                errors.append(f"{prefix}.artifact_path is unreadable: {exc}")
            else:
                if actual_digest != digest:
                    errors.append(f"{prefix} SHA-256 mismatch")

        approved = dataset["publication_approved"] is True
        authorization = dataset["authorization_status"]
        if classification == "unknown_rights" and approved:
            errors.append(f"{prefix} unknown_rights data cannot be publication approved")
        if classification == "authorized_historical" and approved and (
            dataset["storage_permission"] != "granted"
            or dataset["redistribution_public_display_permission"] != "granted"
        ):
            errors.append(
                f"{prefix} authorized_historical data requires explicit granted "
                "storage and display permissions"
            )
        expected_authorization = {
            "synthetic_demo": "approved_synthetic",
            "authorized_historical": "approved_historical",
        }.get(classification)
        if approved and authorization != expected_authorization:
            errors.append(f"{prefix}.authorization_status does not match classification")
        if classification == "authorized_historical" and approved:
            raw_evidence = dataset["license_or_contract_evidence_reference"]
            evidence = raw_evidence.strip().lower() if isinstance(raw_evidence, str) else ""
            if evidence in {"", "unknown", "none", "n/a", "tbd", "placeholder"}:
                errors.append(f"{prefix} requires a concrete license or contract reference")
        if require_publication_approved and (
            not approved
            or authorization not in {"approved_synthetic", "approved_historical"}
        ):
            errors.append(f"{prefix} is not approved for publication")

        period = dataset["observation_period"]
        if not isinstance(period, dict) or not {"start", "end", "notes"} <= period.keys():
            errors.append(f"{prefix}.observation_period requires start, end, and notes")

        for field in _REQUIRED_FIELDS - {
            "publication_approved",
            "observation_period",
        }:
            if not isinstance(dataset[field], str) or not dataset[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--require-publication-approved", action="store_true")
    args = parser.parse_args()
    errors = validate_manifest(
        args.manifest,
        require_publication_approved=args.require_publication_approved,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"Validated provenance manifest: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
