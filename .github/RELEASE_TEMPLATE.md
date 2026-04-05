# Release Tag Convention

All releases must use semantic versioning tags prefixed with `v`.

## Format

```
v<MAJOR>.<MINOR>.<PATCH>
```

## Examples

| Tag       | When to use                                  |
|-----------|----------------------------------------------|
| `v0.0.1`  | First release / early development            |
| `v0.1.0`  | New feature added during initial development |
| `v1.0.0`  | First stable release                         |
| `v1.2.3`  | Patch release on a stable version            |
| `v2.0.0`  | Breaking change                              |

## Docker tags published per release

When you publish a release (e.g. `v1.2.3`), the workflow automatically
pushes the following tags to `ghcr.io/jakeward98/qbitread`:

| Docker tag    | Meaning                                    |
|---------------|--------------------------------------------|
| `1.2.3`       | Exact version — immutable, safe to pin     |
| `1.2`         | Latest patch for this minor version        |
| `1`           | Latest minor+patch for this major version  |
| `latest`      | Most recently published release            |
| `buildcache`  | Internal layer cache — do not use directly |

The same rules apply to pre-v1 versions. For `v0.0.1` the tags are
`0.0.1`, `0.0`, `0`, and `latest`.

## How to cut a release

1. Merge all changes to `main`.
2. On GitHub, go to **Releases → Draft a new release**.
3. In **Choose a tag**, type the new version (e.g. `v0.1.0`) and select
   **Create new tag on publish**.
4. Fill in the release title and notes.
5. Click **Publish release**.
6. The `Build and Publish Docker Image` workflow fires automatically.

## Pre-release handling

Currently all published releases (including pre-release tags like
`v1.0.0-beta.1`) will update the `latest` tag. If you want pre-releases
to not move `latest`, change `latest=true` to `latest=auto` in the
`flavor` block of `.github/workflows/docker-release.yml`. With
`latest=auto`, any tag containing a hyphen is treated as a pre-release
and will not update `latest`.

## Pulling the image

```bash
# Latest stable release
docker pull ghcr.io/jakeward98/qbitread:latest

# Specific version
docker pull ghcr.io/jakeward98/qbitread:0.0.1
```

Or update `docker-compose.yml` to use the pre-built image:

```yaml
services:
  qbitread:
    image: ghcr.io/jakeward98/qbitread:latest
    # Remove the 'build: .' line when using a pre-built image
```
