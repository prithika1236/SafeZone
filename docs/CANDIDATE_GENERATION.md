# Candidate PRP generation

Stage 7 generates deterministic optimization inputs. A candidate PRP is only a possible patrol positioning location; it is not selected, approved, active, assigned, or citizen-visible.

## MVP input and method

The generator consumes `RiskAreaObservation` objects produced from already aggregated/scored areas. It never treats every raw crime coordinate as a valid stopping point.

`risk_areas_from_results()` is the explicit adapter from Stage 6 `RiskResult` values. It preserves the scored location, model version, raw score, normalization state, and incident evidence count.

1. Reject observations outside configured operational bounds or below minimum risk.
2. Form deterministic single-link spatial clusters using the configured geodesic radius.
3. Calculate a spherical centroid weighted by local risk and evidence count.
4. Aggregate cluster risk as an evidence-weighted mean.
5. If approved road/network nodes are supplied, snap to the nearest node within the configured radius. By default, clusters without a reachable supplied node are excluded.
6. Deduplicate output points within a second configured geodesic radius.
7. Rank by descending local risk and stable candidate ID, then enforce the configured maximum count.

Stable IDs are derived from the generator version, sorted source-area IDs, final coordinate, and optional safe-node ID. Identical inputs and configuration therefore produce identical output regardless of input order.

## Suitability and extension interface

`SafeCandidateNode` represents a predefined operationally suitable location. `SafeCandidateNodeProvider` is the interface for a later approved road-network, parking/lay-by, or curated-node adapter. Stage 7 does not download or assume an external road dataset.

When no safe nodes are available, the MVP can return risk-area centroids with `operationally_verified=false`. These are planning candidates that require later operational validation; they must not be presented as road-safe. When a node is supplied and used, its identifier, metadata, and snap distance remain in the explanation.

## Candidate output

Each candidate contains:

- deterministic candidate ID;
- WGS84 location;
- local 0–1 risk;
- generation method and version;
- source risk-area IDs and metadata;
- evidence count and calculated centroid;
- suitability verification state;
- safe-node and spatial-deduplication traceability where applicable.

Exclusions—including candidates beyond the configured maximum—are returned with source IDs and reasons rather than silently discarded.

## Configuration and limitations

`CandidateGenerationConfig` controls clustering radius, deduplication radius, safe-node snap radius, minimum risk, minimum cluster size, maximum candidate count, safe-node requirement, and generator version.

Single-link clustering is deterministic and practical for the MVP, but it is quadratic in the number of risk areas and can connect chain-shaped clusters. The spherical centroid is geographically defensible but is not automatically a drivable or safe stopping point. A later road-safe provider should be supplied before operational use. Final selection and coverage optimization belong to Stage 8.
